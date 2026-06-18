'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:40:00
@Description：规则框架抽象层 — RuleContext（函数 + imports + calls + 装饰器
              + 源码）+ Rule 抽象基类（id / tag / check）。
'''
from abc import ABC, abstractmethod
from dataclasses import dataclass

from pyknp.model.function import FunctionNode
from pyknp.model.tag import Tag
from pyknp.model.tag_evidence import TagEvidence


@dataclass
class RuleContext:
    function: FunctionNode
    module_imports: set[str]
    call_expressions: list[tuple[str | None, str]]  # (module_or_None, name)
    decorators: list[str]
    source_text: str


class Rule(ABC):
    @property
    @abstractmethod
    def id(self) -> str: ...

    @property
    @abstractmethod
    def tag(self) -> Tag: ...

    @abstractmethod
    def check(self, ctx: RuleContext) -> TagEvidence | None: ...
