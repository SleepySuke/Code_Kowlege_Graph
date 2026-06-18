'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:42:00
@Description：NetworkRule 契约测试 — 命中、未命中、socket 直命中三场景。
'''
from pyknp.model.function import FunctionNode
from pyknp.rules.base import RuleContext
from pyknp.rules.network import NetworkRule


def _make_fn() -> FunctionNode:
    return FunctionNode(
        ref_id="demo.mod.fetch",
        qualified_name_in_file="fetch",
        file="demo/mod.py",
        start_line=1, end_line=3,
        parameters=["url"], decorators=[],
        source_hash="abc",
        location_id="demo/mod.py:1",
    )


def test_network_rule_matches_requests_call():
    ctx = RuleContext(
        function=_make_fn(),
        module_imports={"requests"},
        call_expressions=[("requests", "get")],
        decorators=[],
        source_text="import requests\nrequests.get(url)",
    )
    rule = NetworkRule()
    ev = rule.check(ctx)
    assert ev is not None
    assert ev.tag.value == "network"
    assert "requests" in ev.evidence


def test_network_rule_does_not_match_when_no_import():
    ctx = RuleContext(
        function=_make_fn(),
        module_imports=set(),
        call_expressions=[("requests", "get")],
        decorators=[],
        source_text="",
    )
    rule = NetworkRule()
    assert rule.check(ctx) is None


def test_network_rule_matches_socket_directly():
    ctx = RuleContext(
        function=_make_fn(),
        module_imports={"socket"},
        call_expressions=[("socket", "connect")],
        decorators=[],
        source_text="",
    )
    rule = NetworkRule()
    assert rule.check(ctx) is not None
