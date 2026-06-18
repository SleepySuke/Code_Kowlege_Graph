'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:36:00
@Description：pyknp.pipeline.resolve 包入口；re-export resolve.py 的 run(...)。
              stage 实现见 pyknp/pipeline/resolve/resolve.py。
'''
from pyknp.pipeline.resolve.resolve import run

__all__ = ["run"]
