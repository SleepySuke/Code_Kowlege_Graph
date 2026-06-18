'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:40:00
@Description：规则注册中心 — 维护 Rule 实例列表，run_all 在单规则异常时
              跳过而非炸全流程；default_registry 装载全部内置规则。
'''
from pyknp.model.tag_evidence import TagEvidence
from pyknp.rules.base import Rule, RuleContext


class RuleRegistry:
    def __init__(self) -> None:
        self.rules: list[Rule] = []

    def register(self, rule: Rule) -> None:
        self.rules.append(rule)

    def run_all(self, ctx: RuleContext) -> list[TagEvidence]:
        out: list[TagEvidence] = []
        for rule in self.rules:
            try:
                ev = rule.check(ctx)
            except Exception:
                continue
            if ev is not None:
                out.append(ev)
        return out


def default_registry() -> RuleRegistry:
    """构造装载全部内置规则的注册中心。"""
    from pyknp.rules.compute_heavy import ComputeHeavyRule
    from pyknp.rules.database import DatabaseRule
    from pyknp.rules.filesystem import FilesystemRule
    from pyknp.rules.fixture import FixtureRule
    from pyknp.rules.http_endpoint import HttpEndpointRule
    from pyknp.rules.network import NetworkRule
    from pyknp.rules.property_rule import PropertyRule
    from pyknp.rules.subprocess_rule import SubprocessRule

    reg = RuleRegistry()
    rule_classes: list[type[Rule]] = [
        NetworkRule, FilesystemRule, DatabaseRule, SubprocessRule, ComputeHeavyRule,
        HttpEndpointRule, FixtureRule, PropertyRule,
    ]
    for rule_cls in rule_classes:
        reg.register(rule_cls())
    return reg


__all__ = ["Rule", "RuleContext", "RuleRegistry", "default_registry"]
