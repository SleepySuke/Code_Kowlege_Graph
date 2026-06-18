'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:46:00
@Description：pyknp.pipeline.tagging 包入口；re-export tagging.py 的 run(...)。
              stage 实现见 pyknp/pipeline/tagging/tagging.py。
'''
from pyknp.pipeline.tagging.tagging import run

__all__ = ["run"]
