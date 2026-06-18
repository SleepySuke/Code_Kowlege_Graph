'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:50:00
@Description：pyknp.pipeline.calculation 包入口；re-export calculation.py 的 run(...)。
              stage 实现见 pyknp/pipeline/calculation/calculation.py。
'''
from pyknp.pipeline.calculation.calculation import run

__all__ = ["run"]
