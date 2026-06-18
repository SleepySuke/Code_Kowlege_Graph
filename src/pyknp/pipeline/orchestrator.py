'''
@Author ：suke
@Version ：1.1
@Date ：2026-06-16 01:52:00
@Description：pipeline orchestrator — 串联 ast → resolve → tagging → graph →
              calculation 五个 stage，捕获 stage 异常聚合到 errors，输出
              PipelineRunResult；空项目或顶层异常都落到 FAILED 状态。
              pagerank / betweenness 在此处用 networkx 计算（calculation 保持纯转换）。
              每个 stage 的 wall-clock 耗时在 run 结束时汇总输出到 logger（INFO）。
'''
import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx

from pyknp.model.edge import CallEdge
from pyknp.model.function import FunctionNode
from pyknp.model.run import CalculationReport, PipelineRunResult, RunStatus
from pyknp.model.tag import Tag
from pyknp.model.tag_evidence import TagEvidence
from pyknp.pipeline.ast import run as ast_run
from pyknp.pipeline.calculation import run as calc_run
from pyknp.pipeline.graph import run as graph_run
from pyknp.pipeline.resolve import run as resolve_run
from pyknp.pipeline.tagging import run as tagging_run

logger = logging.getLogger(__name__)


def _empty_report() -> CalculationReport:
    return CalculationReport(
        total_functions=0, total_edges=0,
        tag_distribution={}, tag_distribution_pct={},
        in_degree_top10=[], out_degree_top10=[],
        pagerank_top10=[], betweenness_top10=[],
        module_tag_distribution={},
    )


def _check_invariants(
    functions: list[FunctionNode],
    edges: list[CallEdge],
    direct_tags: dict[str, list[TagEvidence]],
    propagated_tags: dict[str, list[Tag]],
    report: CalculationReport,
) -> list[str]:
    """spec §6 四项关键不变量的运行时校验；返回错误描述列表（空表示全通过）。"""
    errs: list[str] = []

    # 1. 每个 FunctionNode 在 resolve 完成后必有 location_id
    missing_loc = [fn.ref_id for fn in functions if fn.location_id is None]
    if missing_loc:
        errs.append(f"invariant 1 violated: functions without location_id: {missing_loc}")

    # 2. 每条 CallEdge 的 caller_location_id 必须能在 FunctionNode 列表里查到
    known_locs = {fn.location_id for fn in functions if fn.location_id}
    orphan_callers = [
        f"{e.caller_location_id}@line{e.call_line}"
        for e in edges
        if e.caller_location_id not in known_locs
    ]
    if orphan_callers:
        errs.append(f"invariant 2 violated: edges with unknown caller: {orphan_callers}")

    # 3. propagated_tags ⊇ direct_tags（传播只增不减）
    for loc, ev_list in direct_tags.items():
        direct = {ev.tag for ev in ev_list}
        propagated = set(propagated_tags.get(loc, []))
        diff = direct - propagated
        if diff:
            errs.append(f"invariant 3 violated at {loc}: direct ⊄ propagated (missing {diff})")

    # 4. tag_distribution 各 tag 计数 = 该 tag 在 propagated_tags 中出现的 function 数
    for tag, count in report.tag_distribution.items():
        actual = sum(1 for tags in propagated_tags.values() if tag in set(tags))
        if count != actual:
            errs.append(
                f"invariant 4 violated for {tag}: count={count} actual={actual}"
            )
    return errs


class _StageTimer:
    """记录每个 stage 的 wall-clock 耗时。"""

    def __init__(self) -> None:
        self.timings: dict[str, float] = {}

    def time(self, name: str) -> Any:
        @contextmanager
        def _ctx() -> Iterator[None]:
            t0 = time.perf_counter()
            try:
                yield
            finally:
                self.timings[name] = time.perf_counter() - t0
        return _ctx()

    def log_summary(self, run_id: str, status: str) -> None:
        if not self.timings:
            return
        parts = [f"{k}={v:.2f}s" for k, v in self.timings.items()]
        total = sum(self.timings.values())
        logger.info(
            "pipeline %s %s — stages: %s | total=%.2fs",
            run_id, status, " ".join(parts), total,
        )


def run_pipeline(
    project_root: Path,
    project_name: str = "uploaded",
    run_id: str | None = None,
) -> PipelineRunResult:
    run_id = run_id or uuid.uuid4().hex[:12]
    started_at = datetime.now(timezone.utc)
    errors: list[str] = []
    timer = _StageTimer()

    try:
        py_files = list(project_root.rglob("*.py"))
        if not py_files:
            errors.append("no python files found in uploaded project")
            timer.log_summary(run_id, "FAILED(empty)")
            return PipelineRunResult(
                run_id=run_id,
                status=RunStatus.FAILED,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                project_name=project_name,
                functions=[],
                edges=[],
                direct_tags={},
                propagated_tags={},
                calculation=_empty_report(),
                errors=errors,
            )

        with timer.time("ast"):
            functions, imports = ast_run(project_root)
        with timer.time("resolve"):
            edges, _location_map = resolve_run(project_root, functions, imports)
        with timer.time("tagging"):
            direct_tags = tagging_run(project_root, functions, imports)

        location_ids = [fn.location_id for fn in functions if fn.location_id]
        with timer.time("graph"):
            G, propagated_tags = graph_run(location_ids, edges, direct_tags)

        with timer.time("centrality"):
            if G.number_of_nodes() > 0:
                pagerank = nx.pagerank(G, max_iter=200)
                betweenness = nx.betweenness_centrality(G)
            else:
                pagerank = {}
                betweenness = {}

        file_of = {fn.location_id: fn.file for fn in functions if fn.location_id}
        with timer.time("calculation"):
            report = calc_run(location_ids, edges, propagated_tags, file_of, pagerank, betweenness)

        # spec §6 关键不变量运行时校验
        invariant_errors = _check_invariants(functions, edges, direct_tags, propagated_tags, report)
        if invariant_errors:
            errors.extend(invariant_errors)
            timer.log_summary(run_id, "FAILED(invariant)")
            return PipelineRunResult(
                run_id=run_id,
                status=RunStatus.FAILED,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                project_name=project_name,
                functions=functions,
                edges=edges,
                direct_tags=direct_tags,
                propagated_tags=propagated_tags,
                calculation=report,
                errors=errors,
            )

        timer.log_summary(run_id, "SUCCESS")
        return PipelineRunResult(
            run_id=run_id,
            status=RunStatus.SUCCESS,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            project_name=project_name,
            functions=functions,
            edges=edges,
            direct_tags=direct_tags,
            propagated_tags=propagated_tags,
            calculation=report,
            errors=errors,
        )
    except Exception as exc:
        errors.append(f"orchestrator error: {type(exc).__name__}: {exc}")
        timer.log_summary(run_id, "FAILED(exception)")
        return PipelineRunResult(
            run_id=run_id,
            status=RunStatus.FAILED,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            project_name=project_name,
            functions=[],
            edges=[],
            direct_tags={},
            propagated_tags={},
            calculation=_empty_report(),
            errors=errors,
        )
