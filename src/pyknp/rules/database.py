'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:42:00
@Description：DatabaseRule — 命中 sqlite3/sqlalchemy/psycopg2/pymysql/pymongo/
              redis 等数据库库且函数体中实际调用时打 DATABASE tag。
'''
from pyknp.model.tag import Tag
from pyknp.model.tag_evidence import TagEvidence
from pyknp.rules.base import Rule, RuleContext

_DB_LIBS = {"sqlite3", "sqlalchemy", "psycopg2", "pymysql", "pymongo", "redis"}


class DatabaseRule(Rule):
    @property
    def id(self) -> str:
        return "database.library_call"

    @property
    def tag(self) -> Tag:
        return Tag.DATABASE

    def check(self, ctx: RuleContext) -> TagEvidence | None:
        matched_libs = ctx.module_imports & _DB_LIBS
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
