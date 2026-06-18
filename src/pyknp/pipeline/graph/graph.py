'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:48:00
@Description：graph 阶段实现 — 用 location_id 作为节点主键构建 networkx.DiGraph，
              G.reverse() 提供 callee→caller 反向视图（O(E)），
              对每个 tag 沿反向视图 BFS 把 callee 的 tag 加到所有 transitive caller。
              传播只增不减：propagated_tags ⊇ direct_tags。
              pyknp.pipeline.graph 包入口 __init__.py 只 re-export run(...)。
'''
from collections import defaultdict

import networkx as nx

from pyknp.model.edge import CallEdge
from pyknp.model.tag import Tag
from pyknp.model.tag_evidence import TagEvidence


def run(
    location_ids: list[str],
    edges: list[CallEdge],
    direct_tags: dict[str, list[Tag]] | dict[str, list[TagEvidence]],
) -> tuple[nx.DiGraph, dict[str, list[Tag]]]:
    G = nx.DiGraph()
    for loc in location_ids:
        G.add_node(loc)

    for edge in edges:
        if edge.callee_location_id is None:
            if not G.has_node(edge.caller_location_id):
                G.add_node(edge.caller_location_id)
            continue
        if not G.has_node(edge.caller_location_id):
            G.add_node(edge.caller_location_id)
        if not G.has_node(edge.callee_location_id):
            G.add_node(edge.callee_location_id)
        G.add_edge(edge.caller_location_id, edge.callee_location_id)

    # 把 direct_tags（可能是 list[Tag] 或 list[TagEvidence]）归一化为 set[Tag]
    direct_tagset: dict[str, set[Tag]] = defaultdict(set)
    for loc, evidence in direct_tags.items():
        if not G.has_node(loc):
            G.add_node(loc)
        for ev in evidence:
            if isinstance(ev, Tag):
                direct_tagset[loc].add(ev)
            else:
                direct_tagset[loc].add(ev.tag)

    # 反向视图：callee → caller
    G_rev = G.reverse()

    all_tags: set[Tag] = set()
    for tags in direct_tagset.values():
        all_tags.update(tags)

    propagated: dict[str, set[Tag]] = {node: set() for node in G.nodes}
    for node, tags in direct_tagset.items():
        propagated[node].update(tags)

    for tag in all_tags:
        start_nodes = {n for n, ts in direct_tagset.items() if tag in ts}
        for start in start_nodes:
            for caller in nx.descendants(G_rev, start):
                propagated[caller].add(tag)

    propagated_list: dict[str, list[Tag]] = {
        node: sorted(tags, key=lambda t: t.value) for node, tags in propagated.items()
    }
    return G, propagated_list
