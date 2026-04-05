#!/usr/bin/env python3
"""
🔄 SEAMLESS LLM HANDOFF SYSTEM
==============================
When Claude hits rate limits, this creates a handoff package
so local LLM can continue EXACTLY where Claude left off.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

HANDOFF_DIR = Path.home() / ".brain-continuity"
HANDOFF_FILE = HANDOFF_DIR / "llm-handoff.json"
INSTRUCTIONS_FILE = HANDOFF_DIR / "local-llm-instructions.md"


def create_handoff(
    current_task: str,
    context: str,
    pending_actions: list,
    important_state: dict = None,
    urgency: str = "normal",
) -> str:
    """
    Create handoff package for local LLM when rate limited.

    Args:
        current_task: What we were working on
        context: Relevant context local LLM needs
        pending_actions: List of actions that need completing
        important_state: Any critical state to preserve
        urgency: "low", "normal", "high", "critical"
    """
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)

    handoff = {
        "created_at": datetime.now().isoformat(),
        "reason": "rate_limit_429",
        "urgency": urgency,
        "current_task": current_task,
        "context": context,
        "pending_actions": pending_actions,
        "important_state": important_state or {},
        "handoff_to": "local_llm",
        "resume_instructions": f"""
# HANDOFF FROM CLAUDE TO LOCAL LLM
# Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## WHAT WAS HAPPENING
{current_task}

## CONTEXT YOU NEED
{context}

## WHAT NEEDS TO BE DONE
{chr(10).join(f'- [ ] {action}' for action in pending_actions)}

## IMPORTANT STATE
{json.dumps(important_state or {}, indent=2)}

## HOW TO CONTINUE
1. Read this handoff carefully
2. Complete the pending actions in order
3. Save state frequently
4. When done, update ~/.brain-continuity/last_session.json

## IF YOU GET STUCK
- Check ~/brain/CLAUDE.md for brain rules
- Check ~/brain/ROM-* files for specific knowledge
- Save partial progress and wait for Claude to return
""",
    }

    # Save JSON handoff
    with open(HANDOFF_FILE, "w") as f:
        json.dump(handoff, f, indent=2)

    # Save human-readable instructions
    with open(INSTRUCTIONS_FILE, "w") as f:
        f.write(handoff["resume_instructions"])

    return f"""✅ HANDOFF CREATED

📄 Handoff file: {HANDOFF_FILE}
📝 Instructions: {INSTRUCTIONS_FILE}

Local LLM can now continue your work seamlessly.

To resume with local LLM:
  ollama run claude-emulator "$(cat {INSTRUCTIONS_FILE})"

Or use MCP:
  openrouter_ask_local("Read {INSTRUCTIONS_FILE} and continue the work")
"""


def check_handoff() -> dict:
    """Check if there's a pending handoff from Claude"""
    if HANDOFF_FILE.exists():
        try:
            with open(HANDOFF_FILE) as f:
                return json.load(f)
        except:
            pass
    return None


def complete_handoff(summary: str = "Completed by local LLM"):
    """Mark handoff as complete"""
    if HANDOFF_FILE.exists():
        handoff = check_handoff()
        if handoff:
            handoff["completed_at"] = datetime.now().isoformat()
            handoff["completion_summary"] = summary

            # Archive it
            archive = HANDOFF_DIR / "handoff-archive"
            archive.mkdir(exist_ok=True)
            archive_file = (
                archive / f"handoff-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
            )
            with open(archive_file, "w") as f:
                json.dump(handoff, f, indent=2)

        # Clear current handoff
        HANDOFF_FILE.unlink()
        if INSTRUCTIONS_FILE.exists():
            INSTRUCTIONS_FILE.unlink()

    return "✅ Handoff completed and archived"


def emergency_save(message: str = "Emergency save due to rate limiting"):
    """Quick emergency save when rate limiting detected"""
    import subprocess

    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)

    # Get current git status
    try:
        git_status = subprocess.run(
            ["git", "-C", os.path.expanduser("~/brain"), "status", "--short"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout[:500]
    except:
        git_status = "Unable to get git status"

    emergency = {
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "git_status": git_status,
        "action": "SAVE_AND_WAIT",
    }

    emergency_file = HANDOFF_DIR / "emergency-save.json"
    with open(emergency_file, "w") as f:
        json.dump(emergency, f, indent=2)

    # Try to commit
    try:
        subprocess.run(
            ["git", "-C", os.path.expanduser("~/brain"), "add", "-A"], timeout=10
        )
        subprocess.run(
            [
                "git",
                "-C",
                os.path.expanduser("~/brain"),
                "commit",
                "-m",
                f"🚨 Emergency save: {message}",
            ],
            timeout=30,
        )
    except:
        pass

    return f"🚨 Emergency save complete: {emergency_file}"


if __name__ == "__main__":
    # Test
    print(
        create_handoff(
            current_task="Testing handoff system",
            context="This is a test of the seamless LLM handoff",
            pending_actions=["Verify handoff works", "Test local LLM resume"],
            important_state={"test": True},
        )
    )
