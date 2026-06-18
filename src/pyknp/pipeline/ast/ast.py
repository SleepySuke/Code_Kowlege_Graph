'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:34:00
@Description：AST 阶段实现 — 用 tree-sitter 解析所有 .py 文件，提取函数级节点
              （含方法、装饰器、参数、源码哈希）与模块级 import 表。
              import 表把模块路径映射到该模块绑定的本地名字列表，供 resolve 阶段快速通道使用。
              pyknp.pipeline.ast 包入口 __init__.py 只 re-export run(...)。
'''
import hashlib
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

from pyknp.model.function import FunctionNode

_PY_LANGUAGE = Language(tspython.language())
_PARSER = Parser(_PY_LANGUAGE)


def _text(node: Node) -> str:
    """安全取节点文本；tree-sitter Node.text 类型为 bytes | None。"""
    return (node.text or b"").decode()


def _module_path(project_root: Path, file_path: Path) -> str:
    """计算 .py 文件相对项目根的 dotted module path，处理 __init__.py。"""
    rel = file_path.relative_to(project_root).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _walk_function_nodes(
    node: Node,
    ancestors: list[str],
    out: list[tuple[Node, list[str], Node | None]],
) -> None:
    """深度优先遍历，收集 (function_node, name_chain, decorated_parent_or_None)。"""
    for child in node.children:
        if child.type == "function_definition":
            name_node = child.child_by_field_name("name")
            if name_node is None:  # pragma: no cover — tree-sitter 总会提供 name
                continue
            out.append((child, ancestors + [_text(name_node)], None))
        elif child.type == "decorated_definition":
            inner_func: Node | None = None
            inner_class: Node | None = None
            for inner in child.children:
                if inner.type == "function_definition":
                    inner_func = inner
                elif inner.type == "class_definition":
                    inner_class = inner
            if inner_func is not None:
                name_node = inner_func.child_by_field_name("name")
                if name_node is not None:  # pragma: no cover — 同上
                    out.append(
                        (inner_func, ancestors + [_text(name_node)], child)
                    )
            elif inner_class is not None:  # pragma: no cover — decorated_definition 必包 func 或 class
                name_node = inner_class.child_by_field_name("name")
                if name_node is None:  # pragma: no cover — 同上
                    continue
                cls_name = _text(name_node)
                body = inner_class.child_by_field_name("body") or inner_class
                _walk_function_nodes(body, ancestors + [cls_name], out)
        elif child.type == "class_definition":
            name_node = child.child_by_field_name("name")
            if name_node is None:  # pragma: no cover — 同上
                continue
            cls_name = _text(name_node)
            body = child.child_by_field_name("body") or child
            _walk_function_nodes(body, ancestors + [cls_name], out)
        else:
            _walk_function_nodes(child, ancestors, out)


def _first_identifier(node: Node) -> str | None:
    """取节点下第一个 identifier 子节点；找不到返回 None。"""
    for sub in node.children:
        if sub.type == "identifier":
            return _text(sub)
    return None  # pragma: no cover — 调用方约定 node 必含 identifier


def _extract_parameters(func_node: Node) -> list[str]:
    params_node = func_node.child_by_field_name("parameters")
    if params_node is None:  # pragma: no cover — function_definition 必有 parameters 字段
        return []
    out: list[str] = []
    for child in params_node.children:
        if child.type == "identifier":
            out.append(_text(child))
        elif child.type in ("typed_parameter", "typed_default_parameter"):
            name = _first_identifier(child)
            if name is not None:  # pragma: no cover — typed_parameter 必含 identifier
                out.append(name)
        elif child.type == "list_splat_pattern":
            name = _first_identifier(child)
            if name is not None:  # pragma: no cover — list_splat_pattern 必含 identifier
                out.append("*" + name)
        elif child.type == "dictionary_splat_pattern":
            name = _first_identifier(child)
            if name is not None:  # pragma: no cover — dictionary_splat_pattern 必含 identifier
                out.append("**" + name)
    return out


def _extract_decorators(decorated_parent: Node | None) -> list[str]:
    """从 decorated_definition 父节点抓取装饰器末位名（按 spec §3 双因子匹配约定）。

    - @property              → "property"
    - @pytest.fixture        → "fixture"   (attribute 取末位)
    - @app.route("/x")       → "route"     (call 取 function 字段的末位)
    - @app.get               → "get"       (attribute 取末位)
    """
    if decorated_parent is None:
        return []
    out: list[str] = []
    for child in decorated_parent.children:
        if child.type != "decorator":
            continue
        for sub in child.children:
            if sub.type == "identifier":
                out.append(_text(sub))
            elif sub.type == "call":
                fn = sub.child_by_field_name("function")
                if fn is not None:  # pragma: no cover — call 必有 function 字段
                    out.append(_text(fn).split(".")[-1])
            elif sub.type == "attribute":
                out.append(_text(sub).split(".")[-1])
    return out


def _extract_imports(module_node: Node) -> list[str]:
    """收集 import 语句在模块作用域绑定的本地名字。

    tree-sitter Python 把 from-import 的目标总是包成 dotted_name（即使单个名字）。

    - `import X`             → "X"
    - `import X.Y.Z`         → "X"（首段）
    - `import X as Y`        → "Y"
    - `from M import N`      → "N"
    - `from M import N as P` → "P"
    - `from M import *`      → "*"
    """
    names: list[str] = []
    for child in module_node.children:
        if child.type == "import_statement":
            for sub in child.children:
                if sub.type == "dotted_name":
                    name = _first_identifier(sub)
                    if name is not None:  # pragma: no cover — dotted_name 必含 identifier
                        names.append(name)
                elif sub.type == "aliased_import":
                    ids = [_text(c) for c in sub.children if c.type == "identifier"]
                    if ids:  # pragma: no cover — aliased_import 必含 identifier
                        names.append(ids[-1])
        elif child.type == "import_from_statement":
            seen_import_kw = False
            for sub in child.children:
                if not seen_import_kw:
                    if sub.type == "import":
                        seen_import_kw = True
                    continue
                if sub.type == "aliased_import":
                    ids = [_text(c) for c in sub.children if c.type == "identifier"]
                    if ids:  # pragma: no cover — aliased_import 必含 identifier
                        names.append(ids[-1])
                elif sub.type == "dotted_name":
                    name = _first_identifier(sub)
                    if name is not None:  # pragma: no cover — dotted_name 必含 identifier
                        names.append(name)
                elif sub.type == "wildcard_import":
                    names.append("*")
    return names


def run(project_root: Path) -> tuple[list[FunctionNode], dict[str, list[str]]]:
    project_root = project_root.resolve()
    py_files = sorted(project_root.rglob("*.py"))

    functions: list[FunctionNode] = []
    imports: dict[str, list[str]] = {}

    for py_file in py_files:
        try:
            source = py_file.read_bytes()
            tree = _PARSER.parse(source)
        except Exception:  # pragma: no cover — read_bytes 仅在罕见 IO 故障时抛
            continue

        module_path = _module_path(project_root, py_file)
        rel_file = str(py_file.relative_to(project_root))

        imports[module_path] = _extract_imports(tree.root_node)

        collected: list[tuple[Node, list[str], Node | None]] = []
        _walk_function_nodes(tree.root_node, [], collected)

        for func_node, name_chain, decorated_parent in collected:
            ref_id = f"{module_path}.{'.'.join(name_chain)}"
            qualified_in_file = ".".join(name_chain)
            src_text = _text(func_node)
            source_hash = hashlib.sha1(src_text.encode()).hexdigest()

            functions.append(FunctionNode(
                ref_id=ref_id,
                qualified_name_in_file=qualified_in_file,
                file=rel_file,
                start_line=func_node.start_point[0] + 1,
                end_line=func_node.end_point[0] + 1,
                parameters=_extract_parameters(func_node),
                decorators=_extract_decorators(decorated_parent),
                source_hash=source_hash,
            ))

    return functions, imports
