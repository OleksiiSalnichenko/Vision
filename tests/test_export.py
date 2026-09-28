"""`scripts/export_openvino.py`: the checks around the export, not the export.

The conversion itself takes a model load and half a minute, so every test here
replaces the one call that performs it. What is under test is what happens
around it: which weights are accepted, when the script declines to work, and
that an existing export is left alone unless `--force` says otherwise.
"""

import importlib.util

import pytest

from conftest import PROJECT_ROOT

MISSING_WEIGHTS_MESSAGE = "run scripts/fetch_models.py first"
EXIT_USAGE = 2


@pytest.fixture
def export_script(monkeypatch):
    """The script as a module, with the real export replaced by a trap."""
    spec = importlib.util.spec_from_file_location(
        "export_openvino", PROJECT_ROOT / "scripts" / "export_openvino.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.exported = []

    def fake_export(weights, imgsz):
        folder = weights.with_name(weights.stem + "_openvino_model")
        folder.mkdir()
        (folder / f"{weights.stem}.xml").write_text("<net/>", encoding="utf-8")
        module.exported.append((weights, imgsz))
        return folder

    monkeypatch.setattr(module, "export", fake_export)
    return module


def test_missing_pt_asks_for_fetch_models(export_script, tmp_path, capsys):
    code = export_script.main(["--weights", str(tmp_path / "missing.pt")])

    assert code == EXIT_USAGE
    assert MISSING_WEIGHTS_MESSAGE in capsys.readouterr().err
    assert export_script.exported == []


def test_weights_that_are_not_a_pt_file_are_refused(export_script, tmp_path, capsys):
    onnx = tmp_path / "yolo26n.onnx"
    onnx.write_bytes(b"not a model")

    code = export_script.main(["--weights", str(onnx)])

    assert code == EXIT_USAGE
    assert ".pt" in capsys.readouterr().err
    assert export_script.exported == []


def test_existing_export_is_skipped(export_script, tmp_path, capsys):
    pt = tmp_path / "yolo26n.pt"
    pt.write_bytes(b"weights")
    folder = tmp_path / "yolo26n_openvino_model"
    folder.mkdir()
    (folder / "yolo26n.xml").write_text("<net/>", encoding="utf-8")

    code = export_script.main(["--weights", str(pt)])

    assert code == 0
    assert f"skip: {folder}" in capsys.readouterr().out
    assert export_script.exported == []


def test_force_replaces_an_existing_export(export_script, tmp_path, capsys):
    pt = tmp_path / "yolo26n.pt"
    pt.write_bytes(b"weights")
    folder = tmp_path / "yolo26n_openvino_model"
    folder.mkdir()
    (folder / "yolo26n.xml").write_text("<old/>", encoding="utf-8")
    (folder / "stale.bin").write_bytes(b"old")

    code = export_script.main(["--weights", str(pt), "--force"])

    assert code == 0
    assert [weights for weights, _ in export_script.exported] == [pt]
    assert not (folder / "stale.bin").exists()
    out = capsys.readouterr().out
    assert "exported:" in out
    assert "FP32" in out


def test_config_pointing_at_the_export_exports_from_the_pt_beside_it(
    export_script, tmp_path, write_config, monkeypatch
):
    """OpenVINO is the default model, so a bare run must not refuse its own config."""
    pt = tmp_path / "yolo26n.pt"
    pt.write_bytes(b"weights")
    folder = tmp_path / "yolo26n_openvino_model"
    monkeypatch.setattr(
        export_script, "CONFIG_PATH", write_config({"model.weights": str(folder)})
    )

    code = export_script.main([])

    assert code == 0
    assert [weights for weights, _ in export_script.exported] == [pt]
    assert (folder / "yolo26n.xml").is_file()


def test_half_written_export_is_redone_without_force(export_script, tmp_path):
    """A folder with no `.xml` is what an interrupted export leaves behind."""
    pt = tmp_path / "yolo26n.pt"
    pt.write_bytes(b"weights")
    (tmp_path / "yolo26n_openvino_model").mkdir()

    code = export_script.main(["--weights", str(pt)])

    assert code == 0
    assert [weights for weights, _ in export_script.exported] == [pt]
