'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:42:00
@Description：NetworkRule — 命中 requests/httpx/aiohttp/socket/urllib 等网络库
              且函数体中实际调用时打 NETWORK tag。
'''
from pyknp.model.tag import Tag
from pyknp.model.tag_evidence import TagEvidence
from pyknp.rules.base import Rule, RuleContext

_NETWORK_LIBS = {"requests", "httpx", "aiohttp", "socket", "urllib", "urllib3"}


class NetworkRule(Rule):
    @property
    def id(self) -> str:
        return "network.library_call"

    @property
    def tag(self) -> Tag:
        return Tag.NETWORK

    def check(self, ctx: RuleContext) -> TagEvidence | None:
        matched_libs = ctx.module_imports & _NETWORK_LIBS
        if not matched_libs:
            return None
        for module, _name in ctx.call_expressions:
            if module in matched_libs:
                return TagEvidence(
                    tag=self.tag,
                    function_id=ctx.function.location_id or "",
                    rule_id=self.id,
                    evidence=f"imports: {sorted(matched_libs)}\n  calls {module}",
                )
        return None
