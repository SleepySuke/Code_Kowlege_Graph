'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:44:00
@Description：PropertyRule — 装饰器末位名 == property 时打 PROPERTY tag。
              内置 property 无需模块 import 上下文。
'''
from pyknp.model.tag import Tag
from pyknp.model.tag_evidence import TagEvidence
from pyknp.rules.base import Rule, RuleContext


class PropertyRule(Rule):
    @property
    def id(self) -> str:
        return "property.decorator"

    @property
    def tag(self) -> Tag:
        return Tag.PROPERTY

    def check(self, ctx: RuleContext) -> TagEvidence | None:
        if "property" not in ctx.decorators:
            return None
        return TagEvidence(
            tag=self.tag,
            function_id=ctx.function.location_id or "",
            rule_id=self.id,
            evidence="decorators: [property]",
        )
