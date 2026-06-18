'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:44:00
@Description：FixtureRule — 装饰器末位名 == fixture 且模块 import 了 pytest
              时打 FIXTURE tag。双因子匹配以避免误命中自定义 fixture 函数。
'''
from pyknp.model.tag import Tag
from pyknp.model.tag_evidence import TagEvidence
from pyknp.rules.base import Rule, RuleContext


class FixtureRule(Rule):
    @property
    def id(self) -> str:
        return "fixture.decorator"

    @property
    def tag(self) -> Tag:
        return Tag.FIXTURE

    def check(self, ctx: RuleContext) -> TagEvidence | None:
        if "fixture" not in ctx.decorators:
            return None
        if "pytest" not in ctx.module_imports:
            return None
        return TagEvidence(
            tag=self.tag,
            function_id=ctx.function.location_id or "",
            rule_id=self.id,
            evidence="decorators: [fixture]\n  imports pytest",
        )
