'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:28:00
@Description：FunctionNode 契约，函数级 AST 节点；AST 阶段填基础字段，
              resolve 阶段回填 location_id。
'''
from pydantic import BaseModel


class FunctionNode(BaseModel):
    ref_id: str
    qualified_name_in_file: str
    file: str
    start_line: int
    end_line: int
    parameters: list[str]
    decorators: list[str]
    source_hash: str
    location_id: str | None = None
