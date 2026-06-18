'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:34:00
@Description：pyknp.pipeline.ast 包入口；re-export ast.py 的 run(...)。
              stage 实现见 pyknp/pipeline/ast/ast.py。
'''
from pyknp.pipeline.ast.ast import run

__all__ = ["run"]
