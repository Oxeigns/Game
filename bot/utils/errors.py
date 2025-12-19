class BotError(Exception):
    """Base error for user-facing exceptions."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class PermissionError(BotError):
    pass


class CooldownError(BotError):
    def __init__(self, remaining: float):
        super().__init__(f"Cooldown active ({remaining:.1f}s)")
        self.remaining = remaining
