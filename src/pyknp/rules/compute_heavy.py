'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:42:00
@Description：ComputeHeavyRule — 命中 numpy/pandas/scipy/tensorflow/torch/
              sklearn/jax 等计算密集库且函数体中实际调用时打 COMPUTE_HEAVY tag。
'''
from pyknp.model.tag import Tag
from pyknp.model.tag_evidence import TagEvidence
from pyknp.rules.base import Rule, RuleContext

_COMPUTE_LIBS = {
    "numpy", "np",  # numpy 与常见别名 np
    "pandas", "pd",
    "scipy", "sp",
    "tensorflow", "tf",
    "torch",
    "sklearn",
    "jax",
}


class ComputeHeavyRule(Rule):
    @property
    def id(self) -> str:
        return "compute_heavy.library_call"

    @property
    def tag(self) -> Tag:
        return Tag.COMPUTE_HEAVY

    def check(self, ctx: RuleContext) -> TagEvidence | None:
        matched_libs = ctx.module_imports & _COMPUTE_LIBS
        if not matched_libs:
            return None
        for module, name in ctx.call_expressions:
            if module in matched_libs:
                return TagEvidence(
                    tag=self.tag,
                    function_id=ctx.function.location_id or "",
                    rule_id=self.id,
                    evidence=f"imports: {sorted(matched_libs)}\n  calls {module}",
                )
            if module is None and name in matched_libs:
                return TagEvidence(
                    tag=self.tag,
                    function_id=ctx.function.location_id or "",
                    rule_id=self.id,
                    evidence=f"imports: {sorted(matched_libs)}\n  calls {name}",
                )
        return None
