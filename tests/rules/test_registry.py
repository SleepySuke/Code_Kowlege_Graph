'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:40:00
@Description：RuleRegistry 契约测试 — 注册、聚合 evidence、不因单规则异常炸全流程。
'''
from pyknp.model.function import FunctionNode
from pyknp.model.tag import Tag
from pyknp.model.tag_evidence import TagEvidence
from pyknp.rules import RuleRegistry
from pyknp.rules.base import Rule, RuleContext


class _AlwaysNetworkRule(Rule):
    @property
    def id(self) -> str:
        return "test.always_network"

    @property
    def tag(self) -> Tag:
        return Tag.NETWORK

    def check(self, ctx: RuleContext) -> TagEvidence | None:
        return TagEvidence(
            tag=self.tag,
            function_id=ctx.function.location_id or "",
            rule_id=self.id,
            evidence="test",
        )


def test_registry_collects_registered_rules():
    registry = RuleRegistry()
    registry.register(_AlwaysNetworkRule())
    assert len(registry.rules) == 1


def test_registry_run_all_aggregates_evidence():
    registry = RuleRegistry()
    registry.register(_AlwaysNetworkRule())

    fn = FunctionNode(
        ref_id="demo.mod.foo",
        qualified_name_in_file="foo",
        file="demo/mod.py",
        start_line=1,
        end_line=2,
        parameters=[],
        decorators=[],
        source_hash="abc",
        location_id="demo/mod.py:1",
    )
    ctx = RuleContext(
        function=fn,
        module_imports={"requests"},
        call_expressions=[("requests", "get")],
        decorators=[],
        source_text="",
    )
    results = registry.run_all(ctx)
    assert len(results) == 1
    assert results[0].rule_id == "test.always_network"
