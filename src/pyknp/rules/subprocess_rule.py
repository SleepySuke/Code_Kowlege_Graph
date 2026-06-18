'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:42:00
@Description：SubprocessRule — 命中 subprocess 库或 os.system/os.popen 调用时
              打 SUBPROCESS tag。
'''
from pyknp.model.tag import Tag
from pyknp.model.tag_evidence import TagEvidence
from pyknp.rules.base import Rule, RuleContext

_SUBPROCESS_LIBS = {"subprocess"}
_OS_CMD_NAMES = {"system", "popen"}


class SubprocessRule(Rule):
    @property
    def id(self) -> str:
        return "subprocess.library_call"

    @property
    def tag(self) -> Tag:
        return Tag.SUBPROCESS

    def check(self, ctx: RuleContext) -> TagEvidence | None:
        evidence_parts: list[str] = []
        if "subprocess" in ctx.module_imports:
            for module, _ in ctx.call_expressions:
                if module == "subprocess":
                    evidence_parts.append(f"calls {module}")
        if "os" in ctx.module_imports:
            for module, name in ctx.call_expressions:
                if module == "os" and name in _OS_CMD_NAMES:
                    evidence_parts.append(f"calls os.{name}")
        if not evidence_parts:
            return None
        return TagEvidence(
            tag=self.tag,
            function_id=ctx.function.location_id or "",
            rule_id=self.id,
            evidence="\n".join(evidence_parts),
        )
