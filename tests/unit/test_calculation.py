'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:50:00
@Description：calculation 阶段契约测试 — 基础统计、tag 分布、模块聚合、top-N 排序。
'''
from pyknp.model.edge import CallEdge, ResolvedVia
from pyknp.model.run import CalculationReport
from pyknp.model.tag import Tag
from pyknp.pipeline.calculation import run as calc_run


def test_calculation_basic_stats():
    location_ids = ["pkg/a.py:1", "pkg/b.py:1", "pkg/b.py:5"]
    edges = [
        CallEdge(caller_location_id="pkg/a.py:1", callee_location_id="pkg/b.py:1",
                 callee_ref_id_attempt="x", call_line=2, resolved_via=ResolvedVia.JEDI_GOTO),
        CallEdge(caller_location_id="pkg/a.py:1", callee_location_id="pkg/b.py:5",
                 callee_ref_id_attempt="y", call_line=3, resolved_via=ResolvedVia.JEDI_GOTO),
    ]
    propagated_tags = {
        "pkg/a.py:1": [Tag.NETWORK],
        "pkg/b.py:1": [Tag.NETWORK],
        "pkg/b.py:5": [],
    }
    file_of = {
        "pkg/a.py:1": "pkg/a.py",
        "pkg/b.py:1": "pkg/b.py",
        "pkg/b.py:5": "pkg/b.py",
    }
    pagerank = {"pkg/a.py:1": 0.5, "pkg/b.py:1": 0.3, "pkg/b.py:5": 0.2}
    betweenness = {"pkg/a.py:1": 0.0, "pkg/b.py:1": 0.5, "pkg/b.py:5": 0.0}

    report = calc_run(location_ids, edges, propagated_tags, file_of, pagerank, betweenness)

    assert isinstance(report, CalculationReport)
    assert report.total_functions == 3
    assert report.total_edges == 2
    assert report.tag_distribution[Tag.NETWORK] == 2
    assert report.module_tag_distribution["pkg/b.py"][Tag.NETWORK] == 1
    total_pr = sum(v for _, v in report.pagerank_top10)
    assert 0.99 <= total_pr <= 1.01


def test_calculation_top_includes_max_degree():
    location_ids = ["a:1", "b:1", "c:1"]
    edges = [
        CallEdge(caller_location_id="b:1", callee_location_id="a:1",
                 callee_ref_id_attempt="x", call_line=1, resolved_via=ResolvedVia.JEDI_GOTO),
        CallEdge(caller_location_id="c:1", callee_location_id="a:1",
                 callee_ref_id_attempt="x", call_line=1, resolved_via=ResolvedVia.JEDI_GOTO),
    ]
    propagated_tags = {loc: [] for loc in location_ids}
    file_of = {loc: "x.py" for loc in location_ids}
    pagerank = {loc: 1.0 / 3 for loc in location_ids}
    betweenness = {loc: 0.0 for loc in location_ids}

    report = calc_run(location_ids, edges, propagated_tags, file_of, pagerank, betweenness)
    top_in = dict(report.in_degree_top10)
    assert top_in["a:1"] == 2
