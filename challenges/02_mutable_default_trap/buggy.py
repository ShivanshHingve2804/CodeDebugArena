"""User registry — BUGGY VERSION.

Bug: Mutable default argument causes all instances to share the same list.
"""


class UserRegistry:
    """Manages groups of users."""

    def __init__(self, users=[]):  # BUG: mutable default
        self.users = users

    def add_user(self, name: str):
        self.users.append(name)

    def get_users(self) -> list:
        return list(self.users)

    def count(self) -> int:
        return len(self.users)
