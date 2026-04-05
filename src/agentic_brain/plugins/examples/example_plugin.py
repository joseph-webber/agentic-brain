import asyncio

from agentic_brain.plugins.base import Plugin


class ExamplePlugin(Plugin):
    """Simple example plugin for tests and development."""

    def __init__(self, config=None):
        super().__init__(config)
        self.inited = False
        self.started = False
        self.stopped = False

    def on_load(self):
        self.inited = True
        # register a hook handler example
        self.register_hook("echo", self._on_echo)

    def on_unload(self):
        self.stopped = True

    def on_message(self, message: str, **kwargs) -> str:
        # echo plugin appends a prefix
        return message

    def _on_echo(self, message: str) -> str:
        return f"echo:{message}"
