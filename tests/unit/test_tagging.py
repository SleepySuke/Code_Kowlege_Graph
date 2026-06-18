'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:46:00
@Description：tagging 阶段契约测试 — NETWORK 资源 tag 与 FIXTURE 角色 tag 命中。
'''
from pathlib import Path

from pyknp.model.tag import Tag
from pyknp.pipeline.ast import run as ast_run
from pyknp.pipeline.resolve import run as resolve_run
from pyknp.pipeline.tagging import run as tagging_run


def test_tagging_assigns_network_tag(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "import requests\n"
        "\n"
        "def fetch(url):\n"
        "    return requests.get(url)\n"
    )

    functions, imports = ast_run(tmp_path)
    edges, _ = resolve_run(tmp_path, functions, imports)
    direct_tags = tagging_run(tmp_path, functions, imports)

    fetch_fn = next(f for f in functions if f.ref_id == "demo.mod.fetch")
    assert fetch_fn.location_id in direct_tags
    tags = {ev.tag for ev in direct_tags[fetch_fn.location_id]}
    assert Tag.NETWORK in tags


def test_tagging_assigns_fixture_tag(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "test_mod.py").write_text(
        "import pytest\n"
        "\n"
        "@pytest.fixture\n"
        "def sample_data():\n"
        "    return [1, 2, 3]\n"
    )

    functions, imports = ast_run(tmp_path)
    edges, _ = resolve_run(tmp_path, functions, imports)
    direct_tags = tagging_run(tmp_path, functions, imports)

    fix_fn = next(f for f in functions if f.ref_id == "demo.test_mod.sample_data")
    tags = {ev.tag for ev in direct_tags.get(fix_fn.location_id, [])}
    assert Tag.FIXTURE in tags


def test_tagging_accepts_custom_registry(tmp_path: Path):
    """显式传入 registry → 走 registry is not None 的 False 分支。"""
    from pyknp.rules import RuleRegistry
    from pyknp.rules.base import Rule

    class _AlwaysTag(Rule):
        @property
        def id(self) -> str:
            return "test.always"

        @property
        def tag(self) -> Tag:
            return Tag.NETWORK

        def check(self, ctx):
            from pyknp.model.tag_evidence import TagEvidence
            return TagEvidence(
                tag=self.tag,
                function_id=ctx.function.location_id or "",
                rule_id=self.id,
                evidence="test",
            )

    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f():\n    return 1\n")

    functions, imports = ast_run(tmp_path)
    resolve_run(tmp_path, functions, imports)
    reg = RuleRegistry()
    reg.register(_AlwaysTag())
    direct_tags = tagging_run(tmp_path, functions, imports, registry=reg)
    fn = next(f for f in functions if f.ref_id == "demo.mod.f")
    assert fn.location_id in direct_tags
    assert direct_tags[fn.location_id][0].rule_id == "test.always"
