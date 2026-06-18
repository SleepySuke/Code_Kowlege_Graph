'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:44:00
@Description：FixtureRule 契约测试 — @pytest.fixture 双因子（装饰器 + pytest 导入）。
'''
from pyknp.model.function import FunctionNode
from pyknp.rules.base import RuleContext
from pyknp.rules.fixture import FixtureRule


def _fn() -> FunctionNode:
    return FunctionNode(
        ref_id="demo.mod.fix", qualified_name_in_file="fix",
        file="demo/mod.py", start_line=1, end_line=2,
        parameters=[], decorators=[], source_hash="abc",
        location_id="demo/mod.py:1",
    )


def test_fixture_matches_pytest_fixture_decorator():
    ctx = RuleContext(
        function=_fn(),
        module_imports={"pytest"},
        call_expressions=[],
        decorators=["fixture"],
        source_text="",
    )
    assert FixtureRule().check(ctx) is not None


def test_fixture_does_not_match_without_pytest_import():
    ctx = RuleContext(
        function=_fn(),
        module_imports=set(),
        call_expressions=[],
        decorators=["fixture"],
        source_text="",
    )
    assert FixtureRule().check(ctx) is None
