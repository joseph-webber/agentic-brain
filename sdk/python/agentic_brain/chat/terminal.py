"""
Terminal Chat SDK - Rich CLI interface for agentic-brain

Usage:
    from agentic_brain.chat import TerminalChat

    chat = TerminalChat(mode="hybrid")
    chat.run()  # Interactive loop

    # Or programmatic:
    response = await chat.send("Hello!")
"""

from __future__ import annotations

import asyncio
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner

from ..client import AgenticBrain, DeploymentMode, ResponseLayer


class TerminalChat:
    """Rich terminal chat interface."""

    def __init__(
        self,
        mode: str = "hybrid",
        voice_enabled: bool = False,
        yolo_mode: bool = False,
        show_layers: bool = True,
    ):
        self.brain = AgenticBrain(mode=DeploymentMode(mode))
        self.console = Console()
        self.voice_enabled = voice_enabled
        self.yolo_mode = yolo_mode
        self.show_layers = show_layers
        self.history: list[dict] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start interactive chat loop."""
        self.console.print(Panel.fit(
            "[bold blue]🧠 Agentic Brain Terminal Chat[/]\n"
            f"Mode: [cyan]{self.brain.mode.value}[/] | "
            f"Voice: {'[green]✅[/]' if self.voice_enabled else '[red]❌[/]'} | "
            f"YOLO: {'[yellow]⚡[/]' if self.yolo_mode else '[red]❌[/]'}",
            title="Welcome",
        ))

        while True:
            try:
                user_input = self.console.input("[bold green]You:[/] ")
                if user_input.strip().lower() in {"exit", "quit", "bye"}:
                    self.console.print("[yellow]Goodbye![/]")
                    break
                asyncio.run(self._handle_input(user_input))
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Interrupted[/]")
                break

    async def send(self, message: str) -> str:
        """Programmatic send — returns the final response text."""
        response = await self.brain.chat(
            message,
            layers=[ResponseLayer.INSTANT, ResponseLayer.DEEP],
        )
        self.history.append({"user": message, "assistant": response.final})
        return response.final

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _handle_input(self, text: str) -> None:
        """Process user input."""
        if text.startswith("/"):
            await self._handle_command(text)
            return

        with Live(
            Spinner("dots", text="[italic]Thinking…[/]"),
            console=self.console,
            refresh_per_second=10,
        ):
            response = await self.brain.chat(
                text,
                layers=[ResponseLayer.INSTANT, ResponseLayer.DEEP],
            )

        if self.show_layers and response.instant:
            self.console.print(Panel(
                response.instant,
                title="⚡ Instant",
                border_style="green",
            ))

        self.console.print(Panel(
            Markdown(response.final),
            title="🧠 Brain",
            border_style="blue",
        ))

        self.history.append({"user": text, "assistant": response.final})

        if self.voice_enabled:
            self._speak(response.final)

    def _speak(self, text: str) -> None:
        """Speak text via macOS say (accessibility helper)."""
        import subprocess
        try:
            subprocess.Popen(
                ["say", "-v", "Karen", text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            pass  # Non-macOS — silently skip

    async def _handle_command(self, cmd: str) -> None:
        """Handle slash commands."""
        parts = cmd.strip().split()
        command = parts[0].lower()

        if command == "/help":
            self.console.print(Panel(
                "[bold]/help[/]             Show this help\n"
                "[bold]/mode[/] <mode>      Switch mode: airlocked | cloud | hybrid\n"
                "[bold]/voice[/]            Toggle voice output\n"
                "[bold]/yolo[/]             Toggle YOLO (auto-execute) mode\n"
                "[bold]/layers[/]           Toggle instant-layer display\n"
                "[bold]/clear[/]            Clear conversation history\n"
                "[bold]/status[/]           Show current settings",
                title="Commands",
                border_style="dim",
            ))

        elif command == "/mode" and len(parts) > 1:
            try:
                new_mode = DeploymentMode(parts[1])
                self.brain.mode = new_mode
                self.console.print(f"[green]Switched to [bold]{new_mode.value}[/] mode[/]")
            except ValueError:
                self.console.print(
                    f"[red]Unknown mode '[bold]{parts[1]}[/]'. "
                    "Use: airlocked | cloud | hybrid[/]"
                )

        elif command == "/voice":
            self.voice_enabled = not self.voice_enabled
            state = "[green]enabled[/]" if self.voice_enabled else "[red]disabled[/]"
            self.console.print(f"Voice {state}")

        elif command == "/yolo":
            self.yolo_mode = not self.yolo_mode
            if self.yolo_mode:
                self.console.print("[yellow]⚡ YOLO mode ON — commands will auto-execute[/]")
            else:
                self.console.print("[green]YOLO mode OFF[/]")

        elif command == "/layers":
            self.show_layers = not self.show_layers
            state = "[green]shown[/]" if self.show_layers else "[dim]hidden[/]"
            self.console.print(f"Instant layer {state}")

        elif command == "/clear":
            self.history.clear()
            self.brain.clear_history()
            self.console.print("[dim]History cleared[/]")

        elif command == "/status":
            self.console.print(Panel(
                f"Mode:         [cyan]{self.brain.mode.value}[/]\n"
                f"Voice:        {'[green]on[/]' if self.voice_enabled else '[red]off[/]'}\n"
                f"YOLO:         {'[yellow]on ⚡[/]' if self.yolo_mode else '[red]off[/]'}\n"
                f"Show layers:  {'[green]yes[/]' if self.show_layers else '[dim]no[/]'}\n"
                f"History msgs: [cyan]{len(self.history)}[/]",
                title="Status",
                border_style="dim",
            ))

        else:
            self.console.print(f"[red]Unknown command: {cmd}[/]  Type [bold]/help[/] for options.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point for the [bold]brain-chat[/] command."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Agentic Brain Terminal Chat",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  brain-chat\n"
            "  brain-chat --mode airlocked\n"
            "  brain-chat --mode cloud --voice\n"
            "  brain-chat --yolo\n"
        ),
    )
    parser.add_argument(
        "--mode",
        default="hybrid",
        choices=["airlocked", "cloud", "hybrid"],
        help="Deployment mode (default: hybrid)",
    )
    parser.add_argument("--voice", action="store_true", help="Enable voice output")
    parser.add_argument("--yolo", action="store_true", help="Enable YOLO auto-execute mode")
    parser.add_argument("--no-layers", action="store_true", help="Hide instant-layer output")
    args = parser.parse_args()

    chat = TerminalChat(
        mode=args.mode,
        voice_enabled=args.voice,
        yolo_mode=args.yolo,
        show_layers=not args.no_layers,
    )
    chat.run()


if __name__ == "__main__":
    main()
