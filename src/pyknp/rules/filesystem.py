'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:42:00
@Description：FilesystemRule — 命中 pathlib/os/shutil/io 等文件系统库
              或直接调用 open() 时打 FILESYSTEM tag。
'''
from pyknp.model.tag import Tag
from pyknp.model.tag_evidence import TagEvidence
from pyknp.rules.base import Rule, RuleContext

_FS_LIBS = {
    "pathlib", "Path",  # pathlib 与常见 from-import 符号 Path
    "os", "shutil", "io",
}
# 内建 open 不在 imports 集合里也算 FILESYSTEM（避免 `from foo import open` 误命中）
_FS_BARE_CALLS = {"open"}


class FilesystemRule(Rule):
    @property
    def id(self) -> str:
        return "filesystem.library_call"

    @property
    def tag(self) -> Tag:
        return Tag.FILESYSTEM

    def check(self, ctx: RuleContext) -> TagEvidence | None:
        matched_libs = ctx.module_imports & _FS_LIBS
        if not matched_libs:
            # 兜底：未导入 FS 库但调用了内建 open → 仍打 FILESYSTEM
            if not any(
                m is None and n in _FS_BARE_CALLS for m, n in ctx.call_expressions
            ):
                return None
        evidence_parts: list[str] = []
        if matched_libs:
            evidence_parts.append(f"imports: {sorted(matched_libs)}")
        for module, name in ctx.call_expressions:
            if module in matched_libs:
                evidence_parts.append(f"  calls {module}")
            elif module is None and name in matched_libs:
                evidence_parts.append(f"  calls {name}")
            elif module is None and name in _FS_BARE_CALLS:
                evidence_parts.append(f"  calls {name}")
        if len(evidence_parts) <= (1 if matched_libs else 0):
            # 只 imports 但没实际调用 → 不命中（spec §3 要求"实际调用"）
            return None
        return TagEvidence(
            tag=self.tag,
            function_id=ctx.function.location_id or "",
            rule_id=self.id,
            evidence="\n".join(evidence_parts),
        )
