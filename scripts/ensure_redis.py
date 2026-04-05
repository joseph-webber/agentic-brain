#!/usr/bin/env python3
"""
Ensure Redis is running for agentic-brain voice system.
Auto-starts Redis via Docker if not available.

Usage:
    python3 scripts/ensure_redis.py          # Check and start if needed
    python3 scripts/ensure_redis.py --check  # Just check, don't start
"""
import subprocess
import sys
import time


def check_redis() -> bool:
    """Check if Redis is responding on localhost:6379."""
    try:
        result = subprocess.run(
            ["redis-cli", "ping"], capture_output=True, text=True, timeout=3
        )
        return result.returncode == 0 and "PONG" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def check_colima() -> bool:
    """Check if Colima (Docker runtime) is running."""
    try:
        result = subprocess.run(
            ["colima", "status"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0 and "Running" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def start_colima() -> bool:
    """Start Colima if not running."""
    print("🐳 Starting Colima (Docker runtime)...")
    try:
        subprocess.run(
            ["colima", "start", "--memory", "4", "--cpu", "2"], check=True, timeout=120
        )
        print("✅ Colima started")
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"❌ Failed to start Colima: {e}")
        return False


def start_redis_container() -> bool:
    """Start Redis container via docker-compose."""
    print("🔴 Starting Redis container...")
    try:
        # Get the agentic-brain directory
        script_dir = subprocess.run(
            ["dirname", __file__], capture_output=True, text=True
        ).stdout.strip()
        agentic_brain_dir = f"{script_dir}/.."

        subprocess.run(
            ["docker", "compose", "up", "-d", "redis"],
            cwd=agentic_brain_dir,
            check=True,
            timeout=60,
        )
        print("✅ Redis container started")

        # Wait for Redis to be ready
        for i in range(10):
            time.sleep(1)
            if check_redis():
                print("✅ Redis is responding")
                return True
            print(f"   Waiting for Redis... ({i+1}/10)")

        return False
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"❌ Failed to start Redis: {e}")
        return False


def ensure_redis() -> bool:
    """Ensure Redis is running, starting it if necessary."""
    # Already running?
    if check_redis():
        print("✅ Redis is already running")
        return True

    print("⚠️  Redis not responding, checking Docker...")

    # Check Colima
    if not check_colima():
        if not start_colima():
            return False

    # Start Redis container
    return start_redis_container()


def main():
    check_only = "--check" in sys.argv

    if check_only:
        if check_redis():
            print("✅ Redis OK")
            sys.exit(0)
        else:
            print("❌ Redis not available")
            sys.exit(1)
    else:
        if ensure_redis():
            sys.exit(0)
        else:
            print("❌ Could not start Redis")
            sys.exit(1)


if __name__ == "__main__":
    main()
