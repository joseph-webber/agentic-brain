"""Chat SDK helpers for agentic-brain."""

try:
    from .terminal import TerminalChat
except ModuleNotFoundError:  # rich is an optional dependency
    __all__: list[str] = []
else:
    __all__ = ["TerminalChat"]
