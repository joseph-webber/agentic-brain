#!/usr/bin/env python3
"""
PyMicPermission.app bootstrap — runs mic_permission_pyobjc.py in .app context.

TCC DISCOVERY: Shell script launcher + exec python3 preserves bundle TCC
attribution. macOS launch services keeps com.josephbrain.pymicpermission
as the requesting app even after exec(). Dialog appears, permission works!
"""

import os
import subprocess
import sys

# Ensure tools dir is on path
TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


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


import threading

import AVFoundation
import objc
from AppKit import NSApp, NSApplication
from Foundation import NSDate, NSLog, NSObject, NSRunLoop


def get_status_str(status):
    return {0: "notDetermined", 1: "restricted", 2: "denied", 3: "authorized"}.get(
        status, f"unknown({status})"
    )


class AppDelegate(NSObject):

    def applicationDidFinishLaunching_(self, notification):
        bundle_id = objc.lookUpClass("NSBundle").mainBundle().bundleIdentifier()
        status_raw = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
            AVFoundation.AVMediaTypeAudio
        )
        status = get_status_str(status_raw)

        push_redis(f"PYOBJC APP: Launch status={status} bundleID={bundle_id}")
        print(f"PyMicPermission launched. Status: {status}, Bundle: {bundle_id}")

        if status_raw == 0:  # notDetermined
            self._request()
        elif status_raw == 3:  # authorized
            push_redis("PYOBJC APP: Already authorized ✅")
            print("✅ Already authorized!")
            NSApp.terminate_(self)
        else:
            push_redis(
                f"PYOBJC APP: Status={status} - cannot request, open Privacy settings"
            )
            print(
                f"Status: {status}. Open System Settings → Privacy & Security → Microphone"
            )
            NSApp.terminate_(self)

    def _request(self):
        push_redis("PYOBJC APP: Calling requestAccessForMediaType_completionHandler_")
        print("Requesting microphone permission...")

        done = threading.Event()

        def handler(granted):
            final = get_status_str(
                AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
                    AVFoundation.AVMediaTypeAudio
                )
            )
            push_redis(f"PYOBJC APP RESULT: granted={granted} status={final}")
            if granted:
                push_redis(
                    "🎉 PYOBJC APP: MICROPHONE PERMISSION GRANTED! PyObjC .app bundle approach WORKS!"
                )
                print("✅ PERMISSION GRANTED!")
            else:
                push_redis(f"PYOBJC APP: Not granted. Final status: {final}")
                print(f"❌ Permission not granted. Status: {final}")
            done.set()
            NSApp.terminate_(self)

        AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            AVFoundation.AVMediaTypeAudio, handler
        )

    def applicationShouldTerminateAfterLastWindowClosed_(self, sender):
        return True


if __name__ == "__main__":
    push_redis("PYOBJC APP: Starting PyMicPermission.app")
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(0)  # Regular → shows in Dock (required for TCC dialog)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.activateIgnoringOtherApps_(True)
    app.run()
