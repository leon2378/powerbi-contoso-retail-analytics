import shutil

import pytest

import set_model_source as sms


@pytest.fixture
def definition(tmp_path):
    """A copy of the model's expressions.tmdl, so the repository file is never touched."""
    shutil.copy(sms.DEFAULT_DEFINITION / "expressions.tmdl", tmp_path / "expressions.tmdl")
    return tmp_path


def text(definition):
    return (definition / "expressions.tmdl").read_bytes().decode("utf-8")


def mode(definition):
    lines, _ = sms.read(definition / "expressions.tmdl")
    return sms.current_mode(lines)


def test_fabric_then_reset_round_trip(definition):
    sms.apply(definition, "fabric", sql_endpoint="abc.datawarehouse.fabric.microsoft.com", lakehouse="lh_test")
    fabric = text(definition)
    assert mode(definition) == "fabric"
    assert 'expression SqlEndpoint = "abc.datawarehouse.fabric.microsoft.com"' in fabric
    assert 'expression LakehouseName = "lh_test"' in fabric
    assert f'expression DataRoot = "{sms.UNUSED}"' in fabric
    # Each mode may reference only its own source, or the service would demand a gateway.
    assert "Sql.Database(SqlEndpoint, LakehouseName)" in fabric and "File.Contents" not in fabric

    sms.apply(definition, "reset")
    local = text(definition)
    assert mode(definition) == "local"
    assert f'expression DataRoot = "{sms.PLACEHOLDER_DATA_ROOT}"' in local
    assert f'expression SqlEndpoint = "{sms.PLACEHOLDER_SQL_ENDPOINT}"' in local
    assert "File.Contents" in local and "Sql.Database" not in local


def test_local_points_at_the_given_marts_folder(definition, tmp_path):
    marts = tmp_path / "marts"
    sms.apply(definition, "local", data_root=marts)
    assert f'expression DataRoot = "{marts.resolve()}"' in text(definition)


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_reset_is_idempotent_and_keeps_line_endings(definition, newline):
    path = definition / "expressions.tmdl"
    content = path.read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\n", newline)
    path.write_bytes(content.encode("utf-8"))

    sms.apply(definition, "reset")
    once = path.read_bytes()
    sms.apply(definition, "reset")
    assert path.read_bytes() == once
    assert (b"\r\n" in once) == (newline == "\r\n")


def test_fabric_mode_needs_an_endpoint(definition):
    with pytest.raises(SystemExit):
        sms.apply(definition, "fabric")


def test_set_parameter_doubles_quotes():
    lines = ['expression Greeting = "hi" meta [IsParameterQuery=true, Type="Text"]']
    sms.set_parameter(lines, "Greeting", 'say "hi"')
    assert lines == ['expression Greeting = "say ""hi""" meta [IsParameterQuery=true, Type="Text"]']


def test_set_parameter_fails_for_an_unknown_name():
    with pytest.raises(SystemExit):
        sms.set_parameter(['expression Other = "x" meta [IsParameterQuery=true]'], "Missing", "y")
