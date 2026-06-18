'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:44:00
@Description：HttpEndpointRule — 装饰器末位名 ∈ HTTP 动词集合 且模块 import
              了已知 Web 框架符号（FastAPI/Flask/APIRouter 等）时打 HTTP_ENDPOINT tag。
              双因子匹配以避免误命中自定义 route 函数。
'''
from pyknp.model.tag import Tag
from pyknp.model.tag_evidence import TagEvidence
from pyknp.rules.base import Rule, RuleContext

_HTTP_VERB_DECORATORS = {
    "route", "get", "post", "put", "delete", "patch", "head", "options", "websocket",
}
_FRAMEWORK_IMPORTS = {
    "FastAPI", "Flask", "APIRouter", "Blueprint", "router", "app", "Application", "Request",
}


class HttpEndpointRule(Rule):
    @property
    def id(self) -> str:
        return "http_endpoint.decorator"

    @property
    def tag(self) -> Tag:
        return Tag.HTTP_ENDPOINT

    def check(self, ctx: RuleContext) -> TagEvidence | None:
        matched_decorators = set(ctx.decorators) & _HTTP_VERB_DECORATORS
        if not matched_decorators:
            return None
        matched_imports = ctx.module_imports & _FRAMEWORK_IMPORTS
        if not matched_imports:
            return None
        return TagEvidence(
            tag=self.tag,
            function_id=ctx.function.location_id or "",
            rule_id=self.id,
            evidence=(
                f"decorators: {sorted(matched_decorators)}\n"
                f"  imports framework: {sorted(matched_imports)}"
            ),
        )
