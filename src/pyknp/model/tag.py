'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:26:00
@Description：Tag 枚举，覆盖 5 类资源依赖（NETWORK/FILESYSTEM/DATABASE/
              SUBPROCESS/COMPUTE_HEAVY）与 3 类角色（HTTP_ENDPOINT/FIXTURE/PROPERTY）。
'''
from enum import Enum


class Tag(str, Enum):
    NETWORK = "network"
    FILESYSTEM = "filesystem"
    DATABASE = "database"
    SUBPROCESS = "subprocess"
    COMPUTE_HEAVY = "compute_heavy"
    HTTP_ENDPOINT = "http_endpoint"
    FIXTURE = "fixture"
    PROPERTY = "property"
