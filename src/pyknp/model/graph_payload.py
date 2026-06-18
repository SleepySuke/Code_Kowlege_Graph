'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:32:00
@Description：API 友好的图负载契约（GraphNode / GraphEdge / GraphPayload），
              供前端 vis-network 直接渲染。
'''
from pydantic import BaseModel

from pyknp.model.edge import ResolvedVia
from pyknp.model.tag import Tag


class GraphNode(BaseModel):
    location_id: str
    ref_id: str
    label: str
    file: str
    tags: list[Tag]
    in_degree: int
    out_degree: int
    pagerank: float
    node_type: str = "function"  # function / method / property / fixture / http_endpoint / nested
    qualified_name_in_file: str = ""  # 完整链，前端 tooltip / 详情用


class GraphEdge(BaseModel):
    source: str
    target: str
    resolved_via: ResolvedVia


class GraphPayload(BaseModel):
    run_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    tag_distribution: dict[Tag, int]
