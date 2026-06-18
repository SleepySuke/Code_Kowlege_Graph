'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:54:00
@Description：RunStore 契约测试 — 写入 / 读取 / 列表 / 缺失返回 None。
'''
from datetime import datetime, timezone
from pathlib import Path

from pyknp.model.run import CalculationReport, PipelineRunResult, RunStatus, RunSummary
from pyknp.storage.run_store import RunStore


def _empty_report() -> CalculationReport:
    return CalculationReport(
        total_functions=0, total_edges=0,
        tag_distribution={}, tag_distribution_pct={},
        in_degree_top10=[], out_degree_top10=[],
        pagerank_top10=[], betweenness_top10=[],
        module_tag_distribution={},
    )


def _make_result(run_id: str = "abc123") -> PipelineRunResult:
    return PipelineRunResult(
        run_id=run_id,
        status=RunStatus.SUCCESS,
        started_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
        finished_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
        project_name="demo",
        functions=[], edges=[],
        direct_tags={}, propagated_tags={},
        calculation=_empty_report(),
        errors=[],
    )


def test_run_store_write_and_read(tmp_path: Path):
    store = RunStore(tmp_path)
    result = _make_result("r1")
    store.write(result)

    loaded = store.read("r1")
    assert loaded is not None
    assert loaded.run_id == "r1"
    assert loaded.project_name == "demo"


def test_run_store_list_returns_summaries(tmp_path: Path):
    store = RunStore(tmp_path)
    store.write(_make_result("r1"))
    store.write(_make_result("r2"))

    summaries = store.list()
    assert len(summaries) == 2
    ids = {s.run_id for s in summaries}
    assert ids == {"r1", "r2"}
    assert all(isinstance(s, RunSummary) for s in summaries)


def test_run_store_read_missing_returns_none(tmp_path: Path):
    store = RunStore(tmp_path)
    assert store.read("nonexistent") is None
