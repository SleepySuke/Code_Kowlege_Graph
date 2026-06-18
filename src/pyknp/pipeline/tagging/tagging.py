'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:46:00
@Description：tagging 阶段实现 — 为每个函数构造 RuleContext（imports + calls + 装饰器
              + 源码），运行全部注册规则，聚合为 direct_tags。
              call 归属最内层 function_definition，避免嵌套函数的 call 错误归到外层。
              pyknp.pipeline.tagging 包入口 __init__.py 只 re-export run(...)。
'''
from collections import defaultdict
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

from pyknp.model.function import FunctionNode
from pyknp.model.tag_evidence import TagEvidence
from pyknp.rules import RuleContext, RuleRegistry, default_registry

_PY_LANGUAGE = Language(tspython.language())
_PARSER = Parser(_PY_LANGUAGE)


def _module_path_from_file(rel_file: str) -> str:
    rel = Path(rel_file).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":  # pragma: no cover — parts 至少含文件名
        parts = parts[:-1]
    return ".".join(parts)


def _walk_functions_with_calls(
    tree_root: Node,
) -> list[tuple[int, Node, list[tuple[str | None, str]]]]:
    """返回 [(fn_start_line, fn_node, calls)]，calls 归属最内层函数。"""
    out: list[tuple[int, Node, list[tuple[str | None, str]]]] = []

    def walk(node: Node, current_fn_line: int | None, current_calls: list[tuple[str | None, str]]) -> None:
        new_fn_line = current_fn_line
        new_calls = current_calls
        if node.type == "function_definition":
            new_fn_line = node.start_point[0] + 1
            new_calls = []
            out.append((new_fn_line, node, new_calls))

        if node.type == "call" and current_fn_line is not None:
            fn_node = node.child_by_field_name("function")
            if fn_node is not None:  # pragma: no cover — call 必有 function 字段
                text_bytes = fn_node.text or b""
                text = text_bytes.decode()
                if "." in text:
                    parts = text.split(".")
                    current_calls.append((parts[0], parts[-1]))
                else:
                    current_calls.append((None, text))

        for c in node.children:
            walk(c, new_fn_line, new_calls)

    walk(tree_root, None, [])
    return out


def run(
    project_root: Path,
    functions: list[FunctionNode],
    imports: dict[str, list[str]],
    registry: RuleRegistry | None = None,
) -> dict[str, list[TagEvidence]]:
    if registry is None:
        registry = default_registry()

    project_root = project_root.resolve()
    direct_tags: dict[str, list[TagEvidence]] = defaultdict(list)

    by_file: dict[str, dict[int, FunctionNode]] = defaultdict(dict)
    for fn in functions:
        by_file[fn.file][fn.start_line] = fn

    for rel_file, line_to_fn in by_file.items():
        abs_path = project_root / rel_file
        try:
            source_bytes = abs_path.read_bytes()
            tree = _PARSER.parse(source_bytes)
        except Exception:  # pragma: no cover — read_bytes 仅在罕见 IO 故障时抛
            continue

        current_module = _module_path_from_file(rel_file)
        current_imports = set(imports.get(current_module, []))

        for fn_start_line, fn_node, calls in _walk_functions_with_calls(tree.root_node):
            fn_record = line_to_fn.get(fn_start_line)
            if fn_record is None or not fn_record.location_id:
                continue
            src_text = source_bytes[fn_node.start_byte:fn_node.end_byte].decode(errors="replace")
            ctx = RuleContext(
                function=fn_record,
                module_imports=current_imports,
                call_expressions=calls,
                decorators=fn_record.decorators,
                source_text=src_text,
            )
            direct_tags[fn_record.location_id] = registry.run_all(ctx)

    return dict(direct_tags)
