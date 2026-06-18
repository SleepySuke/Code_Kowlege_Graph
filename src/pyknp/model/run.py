'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:30:00
@Description：运行级契约 — RunStatus 枚举、CalculationReport 聚合指标、
              PipelineRunResult 端到端结果、RunSummary 列表项。
'''
from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from pyknp.model.edge import CallEdge
from pyknp.model.function import FunctionNode
from pyknp.model.tag import Tag
from pyknp.model.tag_evidence import TagEvidence


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class CalculationReport(BaseModel):
    total_functions: int
    total_edges: int
    tag_distribution: dict[Tag, int]
    tag_distribution_pct: dict[Tag, float]
    in_degree_top10: list[tuple[str, int]]
    out_degree_top10: list[tuple[str, int]]
    pagerank_top10: list[tuple[str, float]]
    betweenness_top10: list[tuple[str, float]]
    module_tag_distribution: dict[str, dict[Tag, int]]


class PipelineRunResult(BaseModel):
    run_id: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None
    project_name: str
    functions: list[FunctionNode]
    edges: list[CallEdge]
    direct_tags: dict[str, list[TagEvidence]]
    propagated_tags: dict[str, list[Tag]]
    calculation: CalculationReport
    errors: list[str]


class RunSummary(BaseModel):
    run_id: str
    project_name: str
    status: RunStatus
    started_at: datetime
    total_functions: int
    total_edges: int
