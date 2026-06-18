'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:28:00
@Description：TagEvidence 契约，记录一条 tag 命中的规则 id 与可读证据字符串。
'''
from pydantic import BaseModel

from pyknp.model.tag import Tag


class TagEvidence(BaseModel):
    tag: Tag
    function_id: str
    rule_id: str
    evidence: str
