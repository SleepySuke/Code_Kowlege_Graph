'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 02:00:00
@Description：触发 PROPERTY tag 的样例 — @property 装饰器。
'''


class User:
    """Has a @property method."""

    def __init__(self, email):
        self._email = email

    @property
    def email(self):
        return self._email
