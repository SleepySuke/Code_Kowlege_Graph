'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:48:00
@Description：graph 阶段契约测试 — 正向边构建、反向视图、标签正向传播幂等。
'''
from pyknp.model.edge import CallEdge, ResolvedVia
from pyknp.model.tag import Tag
from pyknp.pipeline.graph import run as graph_run


def _edge(caller: str, callee: str) -> CallEdge:
    return CallEdge(
        caller_location_id=caller,
        callee_location_id=callee,
        callee_ref_id_attempt="x",
        call_line=1,
        resolved_via=ResolvedVia.JEDI_GOTO,
    )


def test_graph_builds_and_propagates_tags():
    location_ids = ["a:1", "b:1", "c:1"]
    edges = [
        _edge("c:1", "b:1"),  # c calls b
        _edge("b:1", "a:1"),  # b calls a
    ]
    direct_tags = {"a:1": [Tag.NETWORK]}  # only a has direct NETWORK tag

    G, propagated = graph_run(location_ids, edges, direct_tags)

    # propagated should contain NETWORK on a, b, and c (transitive callers)
    assert Tag.NETWORK in set(propagated["a:1"])
    assert Tag.NETWORK in set(propagated["b:1"])
    assert Tag.NETWORK in set(propagated["c:1"])


def test_graph_propagation_idempotent():
    location_ids = ["a:1", "b:1"]
    edges = [_edge("b:1", "a:1")]
    direct_tags = {"a:1": [Tag.DATABASE]}

    _, propagated1 = graph_run(location_ids, edges, direct_tags)
    # Re-run with propagated tags as new direct_tags → should be stable
    _, propagated2 = graph_run(location_ids, edges, propagated1)
    assert set(propagated1["b:1"]) == set(propagated2["b:1"])


def test_graph_includes_unresolved_callers():
    location_ids = ["a:1"]
    edges = [
        CallEdge(
            caller_location_id="a:1",
            callee_location_id=None,  # unresolved
            callee_ref_id_attempt="ghost",
            call_line=2,
            resolved_via=ResolvedVia.UNRESOLVED,
        )
    ]
    direct_tags = {}
    G, propagated = graph_run(location_ids, edges, direct_tags)
    assert list(G.nodes) == ["a:1"]


def test_graph_adds_unresolved_caller_not_in_location_list():
    """unresolved 边的 caller 不在 location_ids 中时应被加入图。"""
    edges = [
        CallEdge(
            caller_location_id="ghost_caller:1",
            callee_location_id=None,
            callee_ref_id_attempt="x",
            call_line=1,
            resolved_via=ResolvedVia.UNRESOLVED,
        )
    ]
    G, _ = graph_run([], edges, {})
    assert "ghost_caller:1" in G.nodes


def test_graph_adds_caller_and_callee_not_in_location_list():
    """resolved 边的 caller/callee 都不在 location_ids 中时也应被加入图。"""
    edges = [
        CallEdge(
            caller_location_id="caller:1",
            callee_location_id="callee:1",
            callee_ref_id_attempt="x",
            call_line=1,
            resolved_via=ResolvedVia.JEDI_GOTO,
        )
    ]
    G, _ = graph_run([], edges, {})
    assert "caller:1" in G.nodes
    assert "callee:1" in G.nodes
    assert G.has_edge("caller:1", "callee:1")


def test_graph_adds_direct_tag_location_not_in_graph():
    """direct_tags 的 location_id 不在图中时也应被加入。"""
    from pyknp.model.tag_evidence import TagEvidence

    ev = TagEvidence(tag=Tag.NETWORK, function_id="ghost:1", rule_id="r", evidence="e")
    _, propagated = graph_run([], [], {"ghost:1": [ev]})
    assert "ghost:1" in propagated
    assert Tag.NETWORK in set(propagated["ghost:1"])
