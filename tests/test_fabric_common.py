import pytest

import fabric_common as fc


class FakeResponse:
    def __init__(self, status_code=200, body=None, headers=None):
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}
        self.content = b"" if body is None else b"{}"
        self.text = str(body)

    def json(self):
        return self._body


class FakeCredential:
    def get_token(self, scope):
        return type("Token", (), {"token": "t"})()


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(fc.time, "sleep", lambda seconds: None)


def client(handler):
    c = fc.FabricClient(credential=FakeCredential())
    c.request = handler
    return c


# --- semantic model refresh ----------------------------------------------------------------------

def refresh_api(statuses, post_headers, calls):
    """Fake Power BI API: one dataset, a refresh that runs through `statuses`, and a refresh
    history whose newest entry is an earlier refresh that already completed."""
    statuses = iter(statuses)

    def handler(method, url, scope=fc.FABRIC_SCOPE, **kwargs):
        calls.append((method, url))
        if url.endswith("/datasets"):
            return FakeResponse(body={"value": [{"name": "ContosoRetail", "id": "ds1"}]})
        if method == "POST":
            return FakeResponse(202, headers=post_headers)
        if "$top=1" in url:
            return FakeResponse(body={"value": [{"status": "Completed"}]})
        return FakeResponse(body={"status": next(statuses), "startTime": "t0", "endTime": "t1",
                                  "messages": [{"message": "boom"}]})
    return handler


def test_refresh_polls_its_own_refresh_until_completed(capsys):
    calls = []
    location = "https://api.powerbi.com/v1.0/myorg/groups/ws/datasets/ds1/refreshes/r1"
    c = client(refresh_api(["Unknown", "InProgress", "Completed"], {"Location": location}, calls))
    c.refresh_semantic_model("ws", "ContosoRetail")
    polled = [url for method, url in calls if method == "GET" and "/refreshes" in url]
    assert polled == [location] * 3
    assert "Refresh completed" in capsys.readouterr().out


def test_refresh_falls_back_to_the_request_id_header():
    calls = []
    c = client(refresh_api(["Completed"], {"x-ms-request-id": "r2"}, calls))
    c.refresh_semantic_model("ws", "ContosoRetail")
    assert calls[-1][1].endswith("/datasets/ds1/refreshes/r2")


@pytest.mark.parametrize("status", ["Failed", "Cancelled", "TimedOut"])
def test_refresh_raises_when_it_does_not_complete(status):
    c = client(refresh_api(["InProgress", status], {"Location": "https://x/refreshes/r3"}, []))
    with pytest.raises(RuntimeError, match=f"Refresh {status}.*boom"):
        c.refresh_semantic_model("ws", "ContosoRetail")


def test_refresh_of_an_unknown_model_fails():
    c = client(lambda method, url, **kwargs: FakeResponse(body={"value": []}))
    with pytest.raises(RuntimeError, match="not found"):
        c.refresh_semantic_model("ws", "ContosoRetail")


# --- low-level requests and long-running operations ----------------------------------------------

class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)

    def request(self, method, url, **kwargs):
        return self.responses.pop(0)


def test_request_retries_when_throttled():
    c = fc.FabricClient(credential=FakeCredential())
    c.session = FakeSession([FakeResponse(429, headers={"Retry-After": "1"}), FakeResponse(200, body={"ok": True})])
    assert c.request("GET", "https://api").json() == {"ok": True}


def test_request_raises_on_client_errors():
    c = fc.FabricClient(credential=FakeCredential())
    c.session = FakeSession([FakeResponse(403, body="forbidden")])
    with pytest.raises(RuntimeError, match="403"):
        c.request("GET", "https://api")


def test_wait_for_operation_polls_until_it_succeeds():
    responses = iter([FakeResponse(body={"status": "Running"}), FakeResponse(body={"status": "Succeeded"})])
    c = client(lambda method, url, **kwargs: next(responses))
    c.wait_for_operation(FakeResponse(202, headers={"Location": "https://op"}))
    assert next(responses, None) is None


def test_wait_for_operation_raises_when_the_operation_fails():
    c = client(lambda method, url, **kwargs: FakeResponse(body={"status": "Failed"}))
    with pytest.raises(RuntimeError, match="Failed"):
        c.wait_for_operation(FakeResponse(202, headers={"Location": "https://op"}))


def test_wait_for_operation_returns_at_once_for_synchronous_responses():
    c = client(lambda method, url, **kwargs: pytest.fail("should not poll"))
    c.wait_for_operation(FakeResponse(201, body={}))


def test_lakehouse_tables_uri_with_and_without_schemas():
    base = fc.Lakehouse("lh", "lh_contoso", "ws", None, None, None)
    assert base.tables_uri == "abfss://ws@onelake.dfs.fabric.microsoft.com/lh/Tables"
    with_schema = fc.Lakehouse("lh", "lh_contoso", "ws", None, None, "dbo")
    assert with_schema.tables_uri == "abfss://ws@onelake.dfs.fabric.microsoft.com/lh/Tables/dbo"
