'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:44:00
@Description：PropertyRule 契约测试 — @property 命中、其他装饰器不命中。
'''
from pyknp.model.function import FunctionNode
from pyknp.rules.base import RuleContext
from pyknp.rules.property_rule import PropertyRule


def _fn() -> FunctionNode:
    return FunctionNode(
        ref_id="demo.Mod.x", qualified_name_in_file="Mod.x",
        file="demo/mod.py", start_line=1, end_line=2,
        parameters=["self"], decorators=[], source_hash="abc",
        location_id="demo/mod.py:1",
    )


def test_property_rule_matches_property_decorator():
    ctx = RuleContext(
        function=_fn(),
        module_imports=set(),
        call_expressions=[],
        decorators=["property"],
        source_text="",
    )
    assert PropertyRule().check(ctx) is not None


def test_property_rule_does_not_match_other_decorators():
    ctx = RuleContext(
        function=_fn(),
        module_imports=set(),
        call_expressions=[],
        decorators=["staticmethod"],
        source_text="",
    )
    assert PropertyRule().check(ctx) is None
