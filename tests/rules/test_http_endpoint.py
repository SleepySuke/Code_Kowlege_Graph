'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:44:00
@Description：HttpEndpointRule 契约测试 — 装饰器末位名 + 框架 import 双因子匹配。
'''
from pyknp.model.function import FunctionNode
from pyknp.rules.base import RuleContext
from pyknp.rules.http_endpoint import HttpEndpointRule


def _fn() -> FunctionNode:
    return FunctionNode(
        ref_id="demo.mod.get_user", qualified_name_in_file="get_user",
        file="demo/mod.py", start_line=1, end_line=2,
        parameters=[], decorators=[], source_hash="abc",
        location_id="demo/mod.py:1",
    )


def test_http_endpoint_matches_app_get_with_fastapi_import():
    ctx = RuleContext(
        function=_fn(),
        module_imports={"FastAPI", "app"},
        call_expressions=[],
        decorators=["get"],
        source_text="",
    )
    assert HttpEndpointRule().check(ctx) is not None


def test_http_endpoint_does_not_match_without_framework():
    ctx = RuleContext(
        function=_fn(),
        module_imports=set(),
        call_expressions=[],
        decorators=["get"],
        source_text="",
    )
    assert HttpEndpointRule().check(ctx) is None


def test_http_endpoint_matches_router_post():
    ctx = RuleContext(
        function=_fn(),
        module_imports={"APIRouter"},
        call_expressions=[],
        decorators=["post"],
        source_text="",
    )
    assert HttpEndpointRule().check(ctx) is not None
