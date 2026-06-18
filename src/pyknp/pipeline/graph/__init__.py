'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:48:00
@Description：pyknp.pipeline.graph 包入口；re-export graph.py 的 run(...)。
              stage 实现见 pyknp/pipeline/graph/graph.py。
'''
from pyknp.pipeline.graph.graph import run

__all__ = ["run"]
