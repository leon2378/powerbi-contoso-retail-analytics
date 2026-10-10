import shutil

import pytest
import yaml

import deploy_fabric as df
import set_model_source as sms


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A minimal copy of the project: the build only needs the two item folders."""
    model = tmp_path / "powerbi" / "ContosoRetail.SemanticModel"
    (model / "definition").mkdir(parents=True)
    shutil.copy(sms.DEFAULT_DEFINITION / "expressions.tmdl", model / "definition" / "expressions.tmdl")
    (model / ".pbi").mkdir()
    (model / ".pbi" / "cache.abf").write_bytes(b"Desktop's local data cache")
    report = tmp_path / "powerbi" / "ContosoRetail.Report"
    report.mkdir()
    (report / "definition.pbir").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(df, "ROOT", tmp_path)
    return tmp_path


def test_build_switches_a_copy_to_fabric_and_binds_the_connection(project):
    out = df.build("TEST", "abc.datawarehouse.fabric.microsoft.com", "lh_test", "conn-guid")

    assert out == project / "build" / "fabric" / "TEST"
    assert not (out / "ContosoRetail.SemanticModel" / ".pbi").exists()
    built = (out / "ContosoRetail.SemanticModel" / "definition" / "expressions.tmdl").read_text(encoding="utf-8")
    assert "Sql.Database(SqlEndpoint, LakehouseName)" in built
    assert '"abc.datawarehouse.fabric.microsoft.com"' in built and '"lh_test"' in built
    assert yaml.safe_load((out / "parameter.yml").read_text(encoding="utf-8")) == {
        "semantic_model_binding": {
            "models": [{"semantic_model_name": "ContosoRetail", "connection_id": {"TEST": "conn-guid"}}]
        }
    }
    # The repository copy stays in local mode.
    source = (project / "powerbi" / "ContosoRetail.SemanticModel" / "definition" / "expressions.tmdl")
    assert "File.Contents" in source.read_text(encoding="utf-8")


def test_build_without_a_connection_writes_no_parameter_file(project):
    out = df.build("DEV", "abc.datawarehouse.fabric.microsoft.com", "lh_test", None)
    assert not (out / "parameter.yml").exists()


def test_build_replaces_an_earlier_build(project):
    stale = project / "build" / "fabric" / "DEV" / "stale.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("old", encoding="utf-8")
    df.build("DEV", "abc.datawarehouse.fabric.microsoft.com", "lh_test", None)
    assert not stale.exists()
