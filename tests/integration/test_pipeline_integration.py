'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 03:30:00
@Description：stage-to-stage 集成测试 — 不走 orchestrator，直接串多个 stage 验证
              它们之间的契约（location_id 一致性、edge 自洽性、propagated⊇direct）。
              区别于 unit（单 stage 手工输入）与 e2e（经 orchestrator 跑全流程）。
'''
from pathlib import Path

from pyknp.model.edge import ResolvedVia
from pyknp.model.tag import Tag
from pyknp.pipeline.ast import run as ast_run
from pyknp.pipeline.graph import run as graph_run
from pyknp.pipeline.resolve import run as resolve_run
from pyknp.pipeline.tagging import run as tagging_run


def _make_project(tmp_path: Path) -> Path:
    """构造一个跨模块调用的最小项目，触发 jedi goto（非 fast path）。"""
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "callee.py").write_text(
        "import requests\n"
        "def helper(url):\n"
        "    return requests.get(url)\n"
    )
    (pkg / "caller.py").write_text(
        "import demo.callee as callee\n"
        "def use(url):\n"
        "    return callee.helper(url)\n"
    )
    return tmp_path


def test_ast_to_resolve_location_id_consistency(tmp_path: Path):
    """ast 产出的 functions → resolve 必须给每个 fn 填上 location_id，
    且 location_id 形如 '<file>:<line>'。"""
    project = _make_project(tmp_path)
    functions, imports = ast_run(project)
    edges, _ = resolve_run(project, functions, imports)

    # 每个 function 都有 location_id
    assert all(fn.location_id is not None for fn in functions)
    # location_id 格式
    for fn in functions:
        assert ":" in fn.location_id
        file_part, line_part = fn.location_id.rsplit(":", 1)
        assert file_part.endswith(".py")
        assert int(line_part) >= 1


def test_resolve_to_graph_edge_self_consistency(tmp_path: Path):
    """resolve 产出的 edges → graph 必须能消费，且 graph 的节点集合 ⊇
    所有 edge 的 caller_location_id（spec §6 invariant 2）。"""
    project = _make_project(tmp_path)
    functions, imports = ast_run(project)
    edges, _ = resolve_run(project, functions, imports)
    location_ids = [fn.location_id for fn in functions if fn.location_id]
    G, propagated = graph_run(location_ids, edges, {})

    # 所有 resolved edge 的 caller 必须在图里
    for e in edges:
        assert G.has_node(e.caller_location_id)
    # propagated 覆盖所有节点
    assert set(propagated.keys()) >= set(G.nodes)


def test_tagging_to_graph_propagated_superset(tmp_path: Path):
    """tagging → graph 后，propagated_tags ⊇ direct_tags（spec §6 invariant 3）。"""
    project = _make_project(tmp_path)
    functions, imports = ast_run(project)
    resolve_run(project, functions, imports)
    direct_tags = tagging_run(project, functions, imports)
    location_ids = [fn.location_id for fn in functions if fn.location_id]
    edges, _ = resolve_run(project, functions, imports)
    _, propagated = graph_run(location_ids, edges, direct_tags)

    for loc, ev_list in direct_tags.items():
        direct = {ev.tag for ev in ev_list}
        prop = set(propagated.get(loc, []))
        assert direct.issubset(prop), f"{loc}: direct {direct} ⊄ propagated {prop}"


def test_full_flow_finds_cross_module_edge_via_jedi(tmp_path: Path):
    """dotted call（callee.helper）跳过 fast path 走 jedi goto，
    应解析到 callee.py:helper 的物理位置。"""
    project = _make_project(tmp_path)
    functions, imports = ast_run(project)
    edges, _ = resolve_run(project, functions, imports)

    caller = next(f for f in functions if f.ref_id == "demo.caller.use")
    callee = next(f for f in functions if f.ref_id == "demo.callee.helper")

    cross_edges = [
        e for e in edges
        if e.caller_location_id == caller.location_id
        and e.callee_location_id == callee.location_id
    ]
    assert cross_edges, "expected caller.use → callee.helper edge"
    assert cross_edges[0].resolved_via in {ResolvedVia.JEDI_GOTO, ResolvedVia.IMPORT_FAST_PATH}


def test_full_flow_propagates_network_tag_to_caller(tmp_path: Path):
    """callee.helper 有 NETWORK 直接 tag → 经 graph 传播到 caller.use。"""
    project = _make_project(tmp_path)
    functions, imports = ast_run(project)
    edges, _ = resolve_run(project, functions, imports)
    direct_tags = tagging_run(project, functions, imports)
    location_ids = [fn.location_id for fn in functions if fn.location_id]
    _, propagated = graph_run(location_ids, edges, direct_tags)

    caller = next(f for f in functions if f.ref_id == "demo.caller.use")
    assert Tag.NETWORK in set(propagated.get(caller.location_id, [])), (
        "NETWORK should propagate from callee.helper to caller.use"
    )
