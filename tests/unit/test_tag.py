'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:26:00
@Description：Tag 枚举契约测试，确保 8 类标签值与字符串枚举类型稳定。
'''
from pyknp.model.tag import Tag


def test_tag_has_eight_values():
    values = {t.value for t in Tag}
    assert values == {
        "network", "filesystem", "database", "subprocess", "compute_heavy",
        "http_endpoint", "fixture", "property",
    }


def test_tag_is_string_enum():
    assert Tag.NETWORK == "network"
    assert isinstance(Tag.NETWORK, str)
