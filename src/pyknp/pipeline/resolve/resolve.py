'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:36:00
@Description：resolve 阶段实现 — 解析每个 call 表达式到具体被调函数，回填
              FunctionNode.location_id，产出正向 CallEdge 列表。
              快速通道：裸名命中模块 imports 且项目内同名唯一 → IMPORT_FAST_PATH。
              兜底：jedi.Script.infer(line, col) 单点解析 → JEDI_GOTO / UNRESOLVED。
              不调用 jedi.get_references()，保持 O(E) 复杂度。
              pyknp.pipeline.resolve 包入口 __init__.py 只 re-export run(...)。
'''
from __future__ import annotations

import logging
from pathlib import Path

import jedi
import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

from pyknp.model.edge import CallEdge, ResolvedVia
from pyknp.model.function import FunctionNode

logger = logging.getLogger(__name__)

_PY_LANGUAGE = Language(tspython.language())
_PARSER = Parser(_PY_LANGUAGE)


def _module_path_from_file(rel_file: str) -> str:
    rel = Path(rel_file).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":  # pragma: no cover — parts 至少含文件名
        parts = parts[:-1]
    return ".".join(parts)


def _backfill_location_ids(
    project_root: Path,
    functions: list[FunctionNode],
) -> dict[str, str]:
    """MVP 策略：location_id = '<rel_file>:<start_line>'。

    AST 阶段已知每个函数的字面物理位置，直接采用即可保证稳定性。
    re-export / alias 等 ref_id ≠ location_id 的场景留待后续扩展。
    """
    location_map: dict[str, str] = {}
    for fn in functions:
        loc = f"{fn.file}:{fn.start_line}"
        fn.location_id = loc
        location_map[fn.ref_id] = loc
    return location_map


def _walk_calls_by_function(
    tree_root: Node,
) -> list[tuple[int, int, int, int, str]]:
    """返回 [(fn_start_line, call_line, name_line, name_col, name_text)]。

    fn_start_line 是该 call 所属的最内层 function_definition 的起始行；
    这样嵌套函数的 call 不会被错误归到外层函数。

    name_line/name_col 是 jedi.infer 应当使用的位置 — 对于 attribute 调用
    （`a.b.c()`），用最后一个 identifier 而非整个 attribute 起点，
    否则 jedi 会返回 object 本身的定义而非 method。
    """
    out: list[tuple[int, int, int, int, str]] = []

    def walk(node: Node, current_fn_line: int | None) -> None:
        new_fn_line = current_fn_line
        if node.type == "function_definition":
            new_fn_line = node.start_point[0] + 1

        if node.type == "call" and current_fn_line is not None:
            fn_node = node.child_by_field_name("function")
            if fn_node is not None:  # pragma: no cover — call 必有 function 字段
                text_bytes = fn_node.text or b""
                # 对 attribute 调用，jedi 需要最后的 identifier 位置而非 attribute 起点
                if fn_node.type == "attribute":
                    last_id = None
                    for child in fn_node.children:
                        if child.type == "identifier":
                            last_id = child
                    if last_id is not None:
                        out.append((
                            current_fn_line,
                            node.start_point[0] + 1,
                            last_id.start_point[0] + 1,
                            last_id.start_point[1],
                            text_bytes.decode(),
                        ))
                        for c in node.children:
                            walk(c, new_fn_line)
                        return
                out.append((
                    current_fn_line,
                    node.start_point[0] + 1,
                    fn_node.start_point[0] + 1,
                    fn_node.start_point[1],
                    text_bytes.decode(),
                ))

        for c in node.children:
            walk(c, new_fn_line)

    walk(tree_root, None)
    return out


def _resolve_one_call(
    call_text: str,
    call_line: int,
    name_line: int,
    name_col: int,
    caller_location_id: str,
    current_imports: set[str],
    by_last_segment: dict[str, list[FunctionNode]],
    loc_to_fn: dict[str, FunctionNode],
    location_map: dict[str, str],
    script: jedi.Script,
    project_root: Path,
) -> CallEdge:
    last_segment = call_text.split(".")[-1]
    bare_name = call_text.split(".")[0]

    # 快速通道：裸名命中 imports，且项目内同名函数唯一
    if "." not in call_text and bare_name in current_imports:
        candidates = by_last_segment.get(last_segment, [])
        if len(candidates) == 1:
            callee_loc = location_map.get(candidates[0].ref_id)
            return CallEdge(
                caller_location_id=caller_location_id,
                callee_location_id=callee_loc,
                callee_ref_id_attempt=call_text,
                call_line=call_line,
                resolved_via=ResolvedVia.IMPORT_FAST_PATH,
            )

    # 兜底：jedi 单点解析
    try:
        defs = script.infer(name_line, name_col)
    except Exception:  # pragma: no cover — jedi 仅在罕见内部错误时抛
        defs = []

    for d in defs:
        if d.module_path is None:  # pragma: no cover — jedi 仅在罕见 stub 缺失时返回 None
            continue
        callee_module_path = Path(d.module_path)
        try:
            rel = callee_module_path.relative_to(project_root)
            rel_str = str(rel).replace("\\", "/")
        except ValueError:
            rel_str = str(callee_module_path).replace("\\", "/")
        callee_loc = f"{rel_str}:{d.line}"
        # 直接按物理位置查（处理 alias / re-export 场景）
        if callee_loc in loc_to_fn:
            return CallEdge(
                caller_location_id=caller_location_id,
                callee_location_id=callee_loc,
                callee_ref_id_attempt=call_text,
                call_line=call_line,
                resolved_via=ResolvedVia.JEDI_GOTO,
            )

    _log_unresolved(call_text, call_line, caller_location_id)
    return CallEdge(
        caller_location_id=caller_location_id,
        callee_location_id=None,
        callee_ref_id_attempt=call_text,
        call_line=call_line,
        resolved_via=ResolvedVia.UNRESOLVED,
    )


def _log_unresolved(call_text: str, call_line: int, caller: str) -> None:
    """spec §6：UNRESOLVED 调用走 DEBUG 级别（多为外部库/内置，正常现象）。

    要排查时设置 LOG_LEVEL=DEBUG。聚合统计在 run() 末尾 INFO 级别输出。
    """
    logger.debug("UNRESOLVED call %s at %s:%s", call_text, caller, call_line)


def run(
    project_root: Path,
    functions: list[FunctionNode],
    imports: dict[str, list[str]],
) -> tuple[list[CallEdge], dict[str, str]]:
    project_root = project_root.resolve()
    location_map = _backfill_location_ids(project_root, functions)

    by_last_segment: dict[str, list[FunctionNode]] = {}
    for fn in functions:
        last = fn.qualified_name_in_file.split(".")[-1]
        by_last_segment.setdefault(last, []).append(fn)

    loc_to_fn: dict[str, FunctionNode] = {
        fn.location_id: fn for fn in functions if fn.location_id
    }

    by_file: dict[str, dict[int, FunctionNode]] = {}
    for fn in functions:
        by_file.setdefault(fn.file, {})[fn.start_line] = fn

    edges: list[CallEdge] = []
    jedi_project = jedi.Project(str(project_root))

    for rel_file, line_to_fn in by_file.items():
        abs_path = project_root / rel_file
        try:
            source = abs_path.read_text()
            tree = _PARSER.parse(source.encode())
        except Exception:  # pragma: no cover — read_text 仅在罕见 IO 故障时抛
            continue

        current_module = _module_path_from_file(rel_file)
        current_imports = set(imports.get(current_module, []))
        script = jedi.Script(source, path=str(abs_path), project=jedi_project)

        for fn_start_line, call_line, name_line, name_col, name_text in _walk_calls_by_function(tree.root_node):
            caller_fn = line_to_fn.get(fn_start_line)
            if caller_fn is None:
                continue
            caller_loc = caller_fn.location_id or f"{rel_file}:{fn_start_line}"
            edges.append(_resolve_one_call(
                name_text, call_line, name_line, name_col,
                caller_loc, current_imports,
                by_last_segment, loc_to_fn, location_map,
                script, project_root,
            ))

    # 阶段汇总：单条 INFO 替代 N 条 UNRESOLVED WARNING，便于 console 排查
    from collections import Counter
    via_counter = Counter(e.resolved_via.value for e in edges)
    logger.info(
        "resolve stage done: %d edges (fast_path=%d / jedi_goto=%d / unresolved=%d)",
        len(edges),
        via_counter.get("import_fast_path", 0),
        via_counter.get("jedi_goto", 0),
        via_counter.get("unresolved", 0),
    )

    return edges, location_map
