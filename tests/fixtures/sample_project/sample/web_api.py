'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 02:00:00
@Description：触发 HTTP_ENDPOINT tag 的样例 — FastAPI 路由装饰器。
'''
from fastapi import FastAPI

app = FastAPI()


@app.get("/users/{uid}")
def get_user(uid: int):
    """HTTP_ENDPOINT tag — decorated with @app.get."""
    return {"uid": uid}
