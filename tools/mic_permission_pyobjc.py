#!/usr/bin/env python3
"""
mic_permission_pyobjc.py — Request macOS microphone permission via PyObjC

WORKING SOLUTION:
  Must be run from inside a .app bundle (PyMicPermission.app) so that
  macOS TCC attributes the request correctly and shows the system dialog.

  Bundle: com.josephbrain.pymicpermission
  Info.plist has: NSMicrophoneUsageDescription

ARCHITECTURE DISCOVERY:
  - Shell script launcher at Contents/MacOS/ + exec python3 WORKS
  - macOS launch services preserves TCC bundle attribution even after exec()
  - NSBundle.mainBundle() shows org.python.python but TCC uses the
    launch context (com.josephbrain.pymicpermission) → dialog appears!

USAGE:
  open ~/brain/agentic-brain/tools/PyMicPermission.app
  # Dialog appears → click Allow
  # Status becomes: authorized

DIRECT USAGE (after permission granted, from any Python process):
  import AVFoundation
  status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
      AVFoundation.AVMediaTypeAudio)
  # 3 = authorized, 0 = notDetermined, 2 = denied

REDIS COORDINATION:
  redis-cli -a BrainRedis2026 LRANGE swarm:mic_permission:findings 0 -1
"""

import sys
import os
import subprocess


def get_status():
    import AVFoundation

    raw = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
        AVFoundation.AVMediaTypeAudio
    )
    return {0: "notDetermined", 1: "restricted", 2: "denied", 3: "authorized"}.get(
        raw, f"unknown({raw})"
    )


def push_redis(msg):
    try:
        subprocess.run(
            [
                "redis-cli",
                "-a",
                "BrainRedis2026",
                "RPUSH",
                "swarm:mic_permission:findings",
                msg,
            ],
            capture_output=True,
            timeout=3,
        )
    except Exception:
        pass


def request_permission_blocking(timeout_seconds=30):
    """
    Request microphone permission. MUST be called from inside PyMicPermission.app.
    Blocks until user responds or timeout.

    Returns:
        True  - permission granted
        False - denied or cancelled
    """
    import AVFoundation
    from Foundation import NSRunLoop, NSDate, NSObject
    from AppKit import NSApplication

    import threading

    current_status = get_status()
    print(f"Current microphone status: {current_status}")
    push_redis(f"mic_permission_pyobjc.py: current status = {current_status}")

    if current_status == "authorized":
        push_redis("mic_permission_pyobjc.py: already authorized ✅")
        print("✅ Microphone already authorized!")
        return True

    if current_status == "denied":
        push_redis("mic_permission_pyobjc.py: denied — must use Privacy settings")
        print(
            "❌ Microphone denied. Open: System Settings → Privacy & Security → Microphone"
        )
        return False

    if current_status == "restricted":
        push_redis("mic_permission_pyobjc.py: restricted by MDM/SIP")
        print("🔒 Microphone restricted by system policy.")
        return False

    # notDetermined → ask
    result = {"granted": None, "event": threading.Event()}

    def handler(granted):
        result["granted"] = bool(granted)
        new_status = get_status()
        push_redis(
            f"mic_permission_pyobjc.py: handler fired granted={granted} status={new_status}"
        )
        print(f"Handler: granted={granted}, status={new_status}")
        result["event"].set()

    push_redis(
        "mic_permission_pyobjc.py: calling requestAccessForMediaType_completionHandler_"
    )
    AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
        AVFoundation.AVMediaTypeAudio, handler
    )

    # Pump the run loop until handler fires
    deadline = NSDate.dateWithTimeIntervalSinceNow_(timeout_seconds)
    while not result["event"].is_set():
        NSRunLoop.currentRunLoop().runUntilDate_(
            NSDate.dateWithTimeIntervalSinceNow_(0.1)
        )
        if (
            NSDate.date().compare_(deadline) != -1
        ):  # NSOrderedDescending = 1, NSOrderedAscending = -1
            push_redis("mic_permission_pyobjc.py: TIMEOUT waiting for user response")
            print("⏱ Timeout waiting for permission response")
            return False

    granted = result["granted"]
    final_status = get_status()
    push_redis(
        f"mic_permission_pyobjc.py: FINAL granted={granted} status={final_status}"
    )

    if granted:
        push_redis("🎉 MICROPHONE PERMISSION GRANTED via PyObjC!")
        print("✅ MICROPHONE PERMISSION GRANTED!")
    else:
        print(f"❌ Permission not granted. Final status: {final_status}")

    return granted


def check_status():
    """Just check and print current permission status. Works from any Python process."""
    import AVFoundation

    status_str = get_status()
    raw = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
        AVFoundation.AVMediaTypeAudio
    )
    print(f"Microphone permission status: {status_str} (raw={raw})")

    if status_str == "authorized":
        print("✅ You can record audio from Python!")
        # Bonus: try to find the default audio device
        device = AVFoundation.AVCaptureDevice.defaultDeviceWithMediaType_(
            AVFoundation.AVMediaTypeAudio
        )
        if device:
            print(f"   Default audio device: {device.localizedName()}")
    elif status_str == "notDetermined":
        print(
            "⚠️  Run 'open ~/brain/agentic-brain/tools/PyMicPermission.app' to request permission"
        )
    elif status_str == "denied":
        print(
            "❌ Open System Settings → Privacy & Security → Microphone → enable Python/Terminal"
        )
    return status_str


if __name__ == "__main__":
    if "--status" in sys.argv or len(sys.argv) == 1:
        check_status()
    elif "--request" in sys.argv:
        # Must be running inside the .app bundle for this to work
        from AppKit import NSApplication

        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(0)
        granted = request_permission_blocking(timeout_seconds=60)
        sys.exit(0 if granted else 1)
    else:
        print(__doc__)
