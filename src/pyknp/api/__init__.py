'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:56:00
@Description：pyknp.api 子包入口；re-export router 供 app.py 装载。
'''
from pyknp.api.routes import router

__all__ = ["router"]
