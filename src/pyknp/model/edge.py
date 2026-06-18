'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:28:00
@Description：CallEdge 与 ResolvedVia 契约；resolve 阶段只产出正向边
              （caller → callee），location_id 用作物理标识。
'''
from enum import Enum

from pydantic import BaseModel


class ResolvedVia(str, Enum):
    IMPORT_FAST_PATH = "import_fast_path"
    JEDI_GOTO = "jedi_goto"
    UNRESOLVED = "unresolved"


class CallEdge(BaseModel):
    caller_location_id: str
    callee_location_id: str | None
    callee_ref_id_attempt: str
    call_line: int
    resolved_via: ResolvedVia
