"""User registry — FIXED VERSION."""


class UserRegistry:
    """Manages groups of users."""

    def __init__(self, users=None):
        self.users = users if users is not None else []

    def add_user(self, name: str):
        self.users.append(name)

    def get_users(self) -> list:
        return list(self.users)

    def count(self) -> int:
        return len(self.users)
