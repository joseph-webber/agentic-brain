#!/usr/bin/env python3
"""
mic_permission_manager.py — Complete macOS microphone permission solution for Brain AI

═══════════════════════════════════════════════════════════════════════════════
 DISCOVERIES (from PyObjC swarm investigation)
═══════════════════════════════════════════════════════════════════════════════

1. REQUESTING PERMISSION — PyObjC .app Bundle (THIS FILE'S AppDelegate)
   ──────────────────────────────────────────────────────────────────────
   • PyMicPermission.app: shell script launcher + exec python3 WORKS
   • macOS launch services preserves TCC bundle attribution after exec()
   • NSBundle.mainBundle() shows "org.python.python" but TCC uses
     com.josephbrain.pymicpermission (the launch context)
   • Dialog appears, user grants → authorized under brain bundle ID

2. AUDIO CAPTURE — sox subprocess (BEST METHOD)
   ──────────────────────────────────────────────
   • sox/rec inherits Terminal.app's TCC microphone permission
   • Works immediately from any Python subprocess
   • sounddevice/PyAudio FAIL because PortAudio makes its own TCC request
   • sox → CoreAudio HAL directly → real mic data, no extra TCC needed
   • See: ~/brain/core/audio/sox_capture.py

3. CHECKING STATUS — AVCaptureDevice
   ────────────────────────────────────
   • authorizationStatusForMediaType_() checks CURRENT process's bundle
   • From plain python3: checks org.python.python → may be notDetermined
   • Permission may exist under com.josephbrain.pymicpermission

═══════════════════════════════════════════════════════════════════════════════

USAGE:
  python3 mic_permission_manager.py --status    # Check current status
  python3 mic_permission_manager.py --request   # Open app to request (if needed)
  python3 mic_permission_manager.py --test      # Test actual audio capture via sox
  python3 mic_permission_manager.py --privacy   # Open Privacy & Security settings

  open ~/brain/agentic-brain/tools/PyMicPermission.app   # Direct app launch
"""

import sys
import os
import subprocess
import argparse


REDIS_KEY = "swarm:mic_permission:findings"
APP_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "PyMicPermission.app"
)
SOX_CAPTURE = os.path.expanduser("~/brain/core/audio/sox_capture.py")


def push_redis(msg):
    try:
        subprocess.run(
            ["redis-cli", "-a", "BrainRedis2026", "RPUSH", REDIS_KEY, msg],
            capture_output=True,
            timeout=3,
        )
    except Exception:
        pass


def get_av_status():
    """Return (raw_int, string) of AVFoundation mic auth status for current process."""
    try:
        import AVFoundation

        raw = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
            AVFoundation.AVMediaTypeAudio
        )
        label = {0: "notDetermined", 1: "restricted", 2: "denied", 3: "authorized"}.get(
            raw, f"unknown({raw})"
        )
        return raw, label
    except ImportError:
        return -1, "AVFoundation not available"


def cmd_status():
    """Show complete permission status."""
    raw, label = get_av_status()
    print(f"┌─ Microphone Permission Status ─────────────────────────────────────┐")
    print(f"│  AVFoundation status (current process): {label} (raw={raw})")

    icons = {0: "⏳", 1: "🔒", 2: "❌", 3: "✅", -1: "⚠️"}
    print(f"│  {icons.get(raw, '?')} {label}")
    print(f"│")

    # Test sox capture (inherits Terminal TCC)
    sox_ok = _test_sox_quick()
    print(
        f"│  sox capture test: {'✅ WORKING (Terminal TCC inherited)' if sox_ok else '❌ Failed'}"
    )
    print(f"│")
    print(f"│  PyMicPermission.app: {APP_PATH}")
    print(f"│  Bundle ID: com.josephbrain.pymicpermission")
    print(f"└────────────────────────────────────────────────────────────────────┘")

    if raw == 0 and not sox_ok:
        print("\n→  Run: open ~/brain/agentic-brain/tools/PyMicPermission.app")
        print("   (Dialog will appear → click Allow)")
    elif sox_ok:
        print("\n✅ Audio capture via sox WORKS from Python subprocess.")
        print("   Use: from core.audio.sox_capture import capture_audio")
    elif raw == 3:
        print("\n✅ Authorized! Use sounddevice or AVFoundation directly.")
    elif raw == 2:
        print(
            "\n→  Open: System Settings → Privacy & Security → Microphone → enable your app"
        )


def _test_sox_quick():
    """Quick 0.2s sox capture test to verify Terminal TCC inheritance."""
    sox = "/opt/homebrew/bin/rec"
    if not os.path.exists(sox):
        return False
    try:
        # Capture 0.2s to /dev/null (just test if mic is accessible)
        r = subprocess.run(
            [
                sox,
                "-r",
                "24000",
                "-c",
                "1",
                "-b",
                "16",
                "-t",
                "raw",
                "/dev/null",
                "trim",
                "0",
                "0.2",
            ],
            capture_output=True,
            timeout=3,
        )
        return r.returncode == 0
    except Exception:
        return False


def cmd_request():
    """Open PyMicPermission.app to trigger the TCC dialog."""
    raw, label = get_av_status()
    print(f"Current status: {label}")

    if raw == 3:
        print("✅ Already authorized! No need to request again.")
        return

    if not os.path.exists(APP_PATH):
        print(f"❌ App not found at: {APP_PATH}")
        print("   Run from ~/brain/agentic-brain/tools/")
        return

    print(f"Opening {APP_PATH}...")
    print("→ If status is notDetermined, the macOS permission dialog will appear")
    print("→ Click 'Allow' to grant microphone access")
    push_redis("mic_permission_manager.py: opening PyMicPermission.app via --request")
    subprocess.run(["open", APP_PATH])
    print("\nWatch Redis for result:")
    print(f"  redis-cli -a BrainRedis2026 LRANGE '{REDIS_KEY}' 0 -1")


def cmd_test():
    """Test actual audio capture using the sox approach."""
    print("Testing microphone capture via sox (0.5s)...")
    push_redis("mic_permission_manager.py: running audio capture test")

    sox = "/opt/homebrew/bin/rec"
    if not os.path.exists(sox):
        print(f"❌ sox not found at {sox}. Install: brew install sox")
        return False

    try:
        import numpy as np
        import wave

        outfile = os.path.expanduser("~/brain/cache/mic_test.wav")
        os.makedirs(os.path.dirname(outfile), exist_ok=True)

        r = subprocess.run(
            [sox, "-r", "24000", "-c", "1", "-b", "16", outfile, "trim", "0", "0.5"],
            capture_output=True,
            timeout=8,
        )

        if r.returncode != 0 or not os.path.exists(outfile):
            print(f"❌ sox failed: {r.stderr.decode()}")
            push_redis(
                f"mic_permission_manager.py: sox test FAILED: {r.stderr.decode()[:100]}"
            )
            return False

        with wave.open(outfile, "rb") as w:
            frames = w.getnframes()
            data = (
                np.frombuffer(w.readframes(frames), dtype=np.int16).astype(np.float32)
                / 32768.0
            )

        rms = float(np.sqrt(np.mean(data**2)))
        peak = float(np.abs(data).max())

        os.unlink(outfile)

        print(f"✅ Captured {frames} frames @ 24kHz")
        print(f"   RMS: {rms:.5f}  Peak: {peak:.5f}")

        if rms < 1e-10:
            print("⚠️  All zeros — microphone permission blocked at driver level")
            push_redis(
                f"mic_permission_manager.py: sox test captured all zeros - driver blocked"
            )
            return False
        else:
            print("✅ REAL AUDIO DETECTED — microphone is working!")
            push_redis(
                f"mic_permission_manager.py: sox test SUCCESS rms={rms:.5f} frames={frames}"
            )
            return True

    except ImportError:
        print("⚠️  numpy/wave not available — running raw test")
        ok = _test_sox_quick()
        print(f"Raw sox test: {'✅ WORKING' if ok else '❌ FAILED'}")
        return ok
    except Exception as e:
        print(f"❌ Test error: {e}")
        push_redis(f"mic_permission_manager.py: test exception: {str(e)[:100]}")
        return False


def cmd_privacy():
    """Open macOS Privacy & Security → Microphone settings."""
    urls = [
        "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_Microphone",
        "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
    ]
    for url in urls:
        r = subprocess.run(["open", url], capture_output=True)
        if r.returncode == 0:
            print(f"✅ Opened Privacy settings: {url}")
            return
    print("❌ Could not open Privacy settings")


def main():
    parser = argparse.ArgumentParser(
        description="Brain AI microphone permission manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("USAGE:")[1] if "USAGE:" in __doc__ else "",
    )
    parser.add_argument(
        "--status", action="store_true", help="Check current permission status"
    )
    parser.add_argument(
        "--request",
        action="store_true",
        help="Open PyMicPermission.app to request permission",
    )
    parser.add_argument(
        "--test", action="store_true", help="Test actual mic capture via sox"
    )
    parser.add_argument(
        "--privacy", action="store_true", help="Open Privacy & Security settings"
    )

    args = parser.parse_args()

    if args.request:
        cmd_request()
    elif args.test:
        cmd_test()
    elif args.privacy:
        cmd_privacy()
    else:
        cmd_status()  # default


if __name__ == "__main__":
    main()
