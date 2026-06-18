'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:50:00
@Description：calculation 阶段实现 — 把 graph 产物聚合成 CalculationReport：
              tag 分布（含百分比）、入/出度 top-10、pagerank / betweenness top-10、
              按模块（文件）分组的 tag 分布。
              pyknp.pipeline.calculation 包入口 __init__.py 只 re-export run(...)。
'''
from collections import Counter, defaultdict

from pyknp.model.edge import CallEdge
from pyknp.model.run import CalculationReport
from pyknp.model.tag import Tag


def run(
    location_ids: list[str],
    edges: list[CallEdge],
    propagated_tags: dict[str, list[Tag]],
    file_of: dict[str, str],
    pagerank: dict[str, float],
    betweenness: dict[str, float],
) -> CalculationReport:
    in_degree: Counter[str] = Counter()
    out_degree: Counter[str] = Counter()
    for e in edges:
        if e.callee_location_id is None:
            continue
        in_degree[e.callee_location_id] += 1
        out_degree[e.caller_location_id] += 1

    tag_dist: Counter[Tag] = Counter()
    module_tag_dist: dict[str, Counter[Tag]] = defaultdict(Counter)
    for loc, tags in propagated_tags.items():
        for tag in tags:
            tag_dist[tag] += 1
            mod = file_of.get(loc, "")
            module_tag_dist[mod][tag] += 1

    total = max(len(location_ids), 1)
    tag_pct = {tag: count / total for tag, count in tag_dist.items()}

    return CalculationReport(
        total_functions=len(location_ids),
        total_edges=len([e for e in edges if e.callee_location_id is not None]),
        tag_distribution=dict(tag_dist),
        tag_distribution_pct=tag_pct,
        in_degree_top10=sorted(in_degree.items(), key=lambda kv: -kv[1])[:10],
        out_degree_top10=sorted(out_degree.items(), key=lambda kv: -kv[1])[:10],
        pagerank_top10=sorted(pagerank.items(), key=lambda kv: -kv[1])[:10],
        betweenness_top10=sorted(betweenness.items(), key=lambda kv: -kv[1])[:10],
        module_tag_distribution={mod: dict(c) for mod, c in module_tag_dist.items()},
    )
