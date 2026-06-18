'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:52:00
@Description：orchestrator 契约测试 — 端到端跑 5 阶段、空项目失败、run_id 唯一。
'''
import time
from pathlib import Path

from pyknp.model.run import RunStatus
from pyknp.model.tag import Tag
from pyknp.pipeline.orchestrator import run_pipeline


def test_orchestrator_runs_full_pipeline(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "import requests\n"
        "def fetch(url):\n"
        "    return requests.get(url)\n"
    )

    result = run_pipeline(tmp_path, project_name="demo")

    assert result.status == RunStatus.SUCCESS
    assert result.finished_at is not None
    assert len(result.functions) == 1
    assert result.calculation.total_functions == 1
    fetch_fn = result.functions[0]
    assert fetch_fn.location_id in result.propagated_tags
    tags = set(result.propagated_tags[fetch_fn.location_id])
    assert Tag.NETWORK in tags


def test_orchestrator_handles_empty_project(tmp_path: Path):
    (tmp_path / "empty.txt").write_text("not python")
    result = run_pipeline(tmp_path, project_name="empty")
    assert result.status == RunStatus.FAILED
    assert any("no python" in e.lower() for e in result.errors)


def test_orchestrator_run_id_unique():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        sub = td_path / "x"
        sub.mkdir()
        (sub / "__init__.py").write_text("")
        (sub / "m.py").write_text("def f(): return 1\n")
        r1 = run_pipeline(td_path, project_name="x")
        time.sleep(0.01)
        r2 = run_pipeline(td_path, project_name="x")
        assert r1.run_id != r2.run_id
