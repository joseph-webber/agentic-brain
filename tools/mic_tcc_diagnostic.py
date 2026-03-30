#!/usr/bin/env python3
"""
mic_tcc_diagnostic.py — Diagnose macOS microphone TCC permission state
Run this BEFORE and AFTER using MicRequestApp.app

Usage:
    python3 mic_tcc_diagnostic.py
"""
import subprocess
import sys
import os


def run(cmd, capture=True):
    r = subprocess.run(cmd, shell=True, capture_output=capture, text=True)
    return r.stdout.strip() + r.stderr.strip()


def check_sounddevice():
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        print("\n── sounddevice devices ──────────────────────────")
        for i, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                print(f"  [{i}] {d['name']}  (in:{d['max_input_channels']})")
        # Try a tiny capture
        import numpy as np
        print("\n── Test record (0.1s) ──────────────────────────")
        data = sd.rec(int(0.1 * 44100), samplerate=44100, channels=1, dtype='float32')
        sd.wait()
        peak = float(np.abs(data).max())
        if peak < 1e-10:
            print(f"  ⚠  Peak amplitude: {peak:.2e} — likely ZERO (permission denied at driver level)")
        else:
            print(f"  ✅ Peak amplitude: {peak:.4f} — audio IS flowing!")
    except ImportError:
        print("  sounddevice not installed — skipping")
    except Exception as e:
        print(f"  Error: {e}")


def check_tcc():
    print("\n── TCC database ─────────────────────────────────")
    db = os.path.expanduser("~/Library/Application Support/com.apple.TCC/TCC.db")
    if not os.path.exists(db):
        print("  TCC db not found at expected path")
        return
    result = run(
        f'sqlite3 "{db}" '
        '"SELECT service,client,auth_value,auth_reason,last_modified '
        "FROM access WHERE service='kTCCServiceMicrophone';\" 2>&1"
    )
    if result:
        # auth_value: 0=deny, 2=allow, 3=limited
        VALS = {'0': 'DENIED', '2': 'ALLOWED', '3': 'LIMITED', '4': 'ALWAYS_ALLOW'}
        for line in result.splitlines():
            parts = line.split('|')
            if len(parts) >= 4:
                val = VALS.get(parts[2], parts[2])
                print(f"  {parts[1]:40s} → {val:10s} (reason={parts[3]})")
        print()
    else:
        print("  (empty or locked — TCC.db requires Full Disk Access to read)")


def check_avfoundation():
    print("\n── AVCaptureDevice via Swift ────────────────────")
    print("  Note: this status is for the CURRENT process (Terminal/Python),")
    print("        not for MicRequestApp.app's bundle ID.")
    result = run("""swift -e 'import AVFoundation
let status = AVCaptureDevice.authorizationStatus(for: .audio)
switch status {
case .authorized:    print("AUTHORIZED")
case .denied:        print("DENIED")
case .notDetermined: print("NOT_DETERMINED")
case .restricted:    print("RESTRICTED")
@unknown default:    print("UNKNOWN(\\(status.rawValue))")
}' 2>/dev/null || echo 'swift error'""")
    print(f"  Status: {result}")


def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║   Brain AI — Microphone Permission Diagnostic    ║")
    print(f"║   macOS {run('sw_vers -productVersion'):42s}║")
    print("╚══════════════════════════════════════════════════╝")

    check_avfoundation()
    check_tcc()
    check_sounddevice()

    print("\n── Recommendation ───────────────────────────────")
    # Re-check status for advice
    status_line = run("swift -e \"import AVFoundation; print(AVCaptureDevice.authorizationStatus(for:.audio).rawValue)\" 2>/dev/null").strip()
    if status_line == '3':  # authorized
        print("  ✅ Permission is GRANTED. sounddevice should work.")
        print("     If still getting zero audio, check device index or exclusive lock.")
    elif status_line == '0':  # not determined
        print("  ⏳ Terminal/Python permission NOT YET DECIDED.")
        print("     Run:  open ~/brain/agentic-brain/tools/MicRequestApp.app")
        print("     The app now requests microphone permission automatically on launch.")
    elif status_line == '1':  # denied
        print("  ⛔ Terminal/Python permission DENIED.")
        print("     Option A: Run MicRequestApp.app — it will open Privacy Settings.")
        print("     Option B: System Settings → Privacy & Security → Microphone")
        print("                Enable the toggle for Terminal / MicRequestApp.")
        print("     Option C: tccutil reset Microphone — resets ALL mic permissions")
        print("                (you'll need to grant them again for each app)")
    elif status_line == '2':  # restricted
        print("  🔒 RESTRICTED by system policy (MDM/SIP). Cannot override from user space.")
    else:
        print(f"  Unknown status value: {status_line!r}")
        print("     Run MicRequestApp.app and check what it reports.")

    print()


if __name__ == "__main__":
    main()
