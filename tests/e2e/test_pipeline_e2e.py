'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 02:02:00
@Description：E2E 契约 + golden 回归 — 跑完整 pipeline 对 fixture 项目，
              断言关键不变量与 golden 快照（可用 --update-golden 刷新）。
'''
import json
from pathlib import Path

import pytest

from pyknp.model.tag import Tag
from pyknp.pipeline.orchestrator import run_pipeline

GOLDEN_DIR = Path(__file__).parent / "golden"
GOLDEN_PATH = GOLDEN_DIR / "sample_project.json"


def test_pipeline_e2e_function_count(fixture_project_root: Path):
    result = run_pipeline(fixture_project_root, project_name="sample")
    assert result.status.value == "success"
    expected_refs = {
        "sample.net_utils.fetch",
        "sample.db_utils.query_user",
        "sample.fs_utils.read_config",
        "sample.proc_utils.run_cmd",
        "sample.math_utils.compute_matrix",
        "sample.web_api.get_user",
        "sample.test_something.sample_data",
        "sample.models.User.email",
        "sample.main.handle_request",
        "sample.re_export.call_via_alias",
    }
    found_refs = {fn.ref_id for fn in result.functions}
    missing = expected_refs - found_refs
    assert not missing, f"missing functions: {missing}"


def test_pipeline_e2e_re_export_alias_resolves_to_original_location(fixture_project_root: Path):
    """spec §3/§4 re-export 场景：通过 alias 调用 fetch，callee 边应指向
    net_utils.fetch 的物理位置（而非 re_export.fetch_url 的字面位置）。
    验证 jedi goto 而非字面 file:line。"""
    result = run_pipeline(fixture_project_root, project_name="sample")
    caller = next(f for f in result.functions if f.ref_id == "sample.re_export.call_via_alias")
    callee = next(f for f in result.functions if f.ref_id == "sample.net_utils.fetch")
    edges_from_alias = [
        e for e in result.edges
        if e.caller_location_id == caller.location_id
        and e.callee_ref_id_attempt == "fetch_url"
    ]
    assert edges_from_alias, "expected at least one edge from call_via_alias to fetch_url"
    # 至少有一条边应解析到 net_utils.fetch 的物理位置
    assert any(
        e.callee_location_id == callee.location_id and e.resolved_via.value != "unresolved"
        for e in edges_from_alias
    ), f"edges did not resolve to net_utils.fetch: {edges_from_alias}"


def test_pipeline_e2e_all_eight_tags_present(fixture_project_root: Path):
    result = run_pipeline(fixture_project_root, project_name="sample")
    all_tags: set[Tag] = set()
    for ev_list in result.direct_tags.values():
        for ev in ev_list:
            all_tags.add(ev.tag)
    assert all_tags == set(Tag), f"missing tags: {set(Tag) - all_tags}"


def test_pipeline_e2e_propagation_to_main(fixture_project_root: Path):
    """handle_request should have all 5 resource tags propagated."""
    result = run_pipeline(fixture_project_root, project_name="sample")
    main_fn = next(f for f in result.functions if f.ref_id == "sample.main.handle_request")
    propagated = set(result.propagated_tags.get(main_fn.location_id, []))
    for expected in {Tag.NETWORK, Tag.FILESYSTEM, Tag.DATABASE, Tag.SUBPROCESS, Tag.COMPUTE_HEAVY}:
        assert expected in propagated, f"missing {expected} on handle_request"


def test_pipeline_e2e_invariant_propagated_superset_of_direct(fixture_project_root: Path):
    result = run_pipeline(fixture_project_root, project_name="sample")
    for loc, ev_list in result.direct_tags.items():
        direct_tags = {ev.tag for ev in ev_list}
        propagated = set(result.propagated_tags.get(loc, []))
        assert direct_tags.issubset(propagated), f"violation at {loc}"


def test_pipeline_e2e_golden_regression(fixture_project_root: Path, pytestconfig):
    """结构化 golden 比对 — 跑 `pytest --update-golden` 刷新快照。"""
    result = run_pipeline(fixture_project_root, project_name="sample")
    summary = {
        "total_functions": len(result.functions),
        "total_edges": len(result.edges),
        "tag_distribution": {k.value: v for k, v in result.calculation.tag_distribution.items()},
        "ref_ids": sorted(fn.ref_id for fn in result.functions),
        "propagated_tags_by_ref": {
            fn.ref_id: sorted(t.value for t in result.propagated_tags.get(fn.location_id, []))
            for fn in result.functions
        },
    }

    if pytestconfig.getoption("--update-golden"):
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        GOLDEN_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True))
        pytest.skip("golden updated")
    else:
        assert GOLDEN_PATH.exists(), "golden missing; run with --update-golden"
        golden = json.loads(GOLDEN_PATH.read_text())
        assert summary == golden
