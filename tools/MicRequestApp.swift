import AVFoundation
import Cocoa

class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    var statusLabel: NSTextField!
    var detailLabel: NSTextField!
    var primaryButton: NSButton!
    var secondaryButton: NSButton!
    var hasRequestedPermission = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        buildWindow()
        NSApp.activate(ignoringOtherApps: true)
        window.makeKeyAndOrderFront(nil)
        logLaunchContext()
        refreshStatusAndMaybeRequest(autoRequest: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }

    // MARK: - Window

    func buildWindow() {
        let rect = NSRect(x: 0, y: 0, width: 480, height: 300)
        window = NSWindow(
            contentRect: rect,
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Brain AI — Microphone Permission"
        window.center()
        window.isReleasedWhenClosed = false

        let content = window.contentView!

        // Icon / emoji label
        let icon = makeLabel("🎙️", fontSize: 48, bold: false)
        icon.frame = NSRect(x: 0, y: 220, width: 480, height: 56)
        icon.alignment = .center
        content.addSubview(icon)

        // Title
        let title = makeLabel("Microphone Permission Required", fontSize: 18, bold: true)
        title.frame = NSRect(x: 20, y: 175, width: 440, height: 36)
        title.alignment = .center
        content.addSubview(title)

        // Status label (updated dynamically)
        statusLabel = makeLabel("Checking current permission status…", fontSize: 13, bold: false)
        statusLabel.frame = NSRect(x: 20, y: 116, width: 440, height: 56)
        statusLabel.alignment = .center
        statusLabel.textColor = .secondaryLabelColor
        statusLabel.maximumNumberOfLines = 4
        content.addSubview(statusLabel)

        detailLabel = makeLabel("", fontSize: 12, bold: false)
        detailLabel.frame = NSRect(x: 20, y: 74, width: 440, height: 38)
        detailLabel.alignment = .center
        detailLabel.textColor = .tertiaryLabelColor
        detailLabel.maximumNumberOfLines = 3
        content.addSubview(detailLabel)

        primaryButton = NSButton(title: "Request Permission", target: self, action: #selector(requestPermissionNow))
        primaryButton.bezelStyle = .rounded
        primaryButton.frame = NSRect(x: 90, y: 20, width: 150, height: 38)
        primaryButton.keyEquivalent = "\r"
        content.addSubview(primaryButton)

        secondaryButton = NSButton(title: "Open Privacy Settings", target: self, action: #selector(openPrivacySettings))
        secondaryButton.bezelStyle = .rounded
        secondaryButton.frame = NSRect(x: 250, y: 20, width: 150, height: 38)
        content.addSubview(secondaryButton)
    }

    func makeLabel(_ text: String, fontSize: CGFloat, bold: Bool) -> NSTextField {
        let lbl = NSTextField(labelWithString: text)
        lbl.font = bold
            ? NSFont.boldSystemFont(ofSize: fontSize)
            : NSFont.systemFont(ofSize: fontSize)
        lbl.isEditable = false
        lbl.isBezeled = false
        lbl.drawsBackground = false
        return lbl
    }

    // MARK: - Permission Logic

    func refreshStatusAndMaybeRequest(autoRequest: Bool) {
        let status = AVCaptureDevice.authorizationStatus(for: .audio)
        DispatchQueue.main.async {
            self.handleStatus(status)
            if autoRequest && status == .notDetermined && !self.hasRequestedPermission {
                self.hasRequestedPermission = true
                self.statusLabel.stringValue = "⏳  Asking macOS to show the microphone permission dialog…"
                self.detailLabel.stringValue = "If a dialog appears, choose Allow."
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
                    self.requestPermission()
                }
            }
        }
    }

    func handleStatus(_ status: AVAuthorizationStatus) {
        let bundleID = Bundle.main.bundleIdentifier ?? "missing-bundle-id"

        switch status {
        case .authorized:
            statusLabel.textColor = NSColor.systemGreen
            statusLabel.stringValue = "✅  Microphone access is already GRANTED.\n\nThis app can now validate live audio input for Python."
            detailLabel.stringValue = validationSummary()
            primaryButton.title = "Close"
            primaryButton.action = #selector(closeApp)
            primaryButton.isEnabled = true
            secondaryButton.isHidden = false

        case .notDetermined:
            statusLabel.textColor = .labelColor
            statusLabel.stringValue = "⏳  Permission has not been decided yet.\n\nThis app will ask macOS for microphone access automatically."
            detailLabel.stringValue = "Bundle ID: \(bundleID)"
            primaryButton.title = "Request Again"
            primaryButton.action = #selector(requestPermissionNow)
            primaryButton.isEnabled = true
            secondaryButton.isHidden = false

        case .denied:
            statusLabel.textColor = NSColor.systemOrange
            statusLabel.stringValue = "⛔  Access was previously DENIED.\n\nmacOS will not re-prompt until you reset TCC or re-enable this app in Privacy settings."
            detailLabel.stringValue = "Enable “MicRequestApp” under Privacy & Security → Microphone, then reopen the app."
            primaryButton.title = "Open Privacy Settings"
            primaryButton.action = #selector(openPrivacySettings)
            primaryButton.isEnabled = true
            secondaryButton.isHidden = false

        case .restricted:
            statusLabel.textColor = NSColor.systemRed
            statusLabel.stringValue = "🔒  Microphone access is RESTRICTED by system policy\n(MDM, parental controls, or SIP).\n\nThis cannot be changed from within an app."
            detailLabel.stringValue = "If this is a managed Mac, an admin profile may be blocking microphone access."
            primaryButton.title = "Open System Settings"
            primaryButton.action = #selector(openPrivacySettings)
            primaryButton.isEnabled = true
            secondaryButton.isHidden = true

        @unknown default:
            statusLabel.stringValue = "Unknown permission state: \(status.rawValue)"
            detailLabel.stringValue = "Bundle ID: \(bundleID)"
        }

        print("TCC status for kTCCServiceMicrophone: \(status.rawValue) (\(statusDescription(status)))")
    }

    func statusDescription(_ s: AVAuthorizationStatus) -> String {
        switch s {
        case .notDetermined: return "notDetermined"
        case .authorized:    return "authorized"
        case .denied:        return "denied"
        case .restricted:    return "restricted"
        @unknown default:    return "unknown(\(s.rawValue))"
        }
    }

    // MARK: - Button Actions

    @objc func requestPermissionNow() {
        requestPermission()
    }

    func requestPermission() {
        let status = AVCaptureDevice.authorizationStatus(for: .audio)
        guard status == .notDetermined else {
            handleStatus(status)
            return
        }

        statusLabel.stringValue = "⏳  Waiting for your response in the macOS microphone dialog…"
        detailLabel.stringValue = "If nothing appears, the app was likely launched in a context macOS cannot prompt from."
        primaryButton.isEnabled = false

        AVCaptureDevice.requestAccess(for: .audio) { granted in
            DispatchQueue.main.async {
                let refreshedStatus = AVCaptureDevice.authorizationStatus(for: .audio)
                self.primaryButton.isEnabled = true
                if granted && refreshedStatus == .authorized {
                    self.handleStatus(.authorized)
                    DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                        NSApp.terminate(nil)
                    }
                } else {
                    self.handleStatus(refreshedStatus)
                }
            }
        }
    }

    @objc func openPrivacySettings() {
        // Works on macOS 13+ (Ventura) and macOS 14+ (Sonoma) and macOS 15 (Sequoia)
        let urls = [
            "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_Microphone",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
        ]
        for urlString in urls {
            if let url = URL(string: urlString) {
                if NSWorkspace.shared.open(url) { break }
            }
        }
    }

    @objc func closeApp() {
        NSApp.terminate(nil)
    }

    func validationSummary() -> String {
        guard let device = AVCaptureDevice.default(for: .audio) else {
            return "No audio input device was detected by AVFoundation."
        }

        do {
            let session = AVCaptureSession()
            let input = try AVCaptureDeviceInput(device: device)
            if session.canAddInput(input) {
                session.addInput(input)
                return "Validated audio device: \(device.localizedName)"
            }
            return "Microphone permission granted, but AVFoundation could not attach the audio input."
        } catch {
            return "Microphone permission granted, but audio input validation failed: \(error.localizedDescription)"
        }
    }

    func logLaunchContext() {
        let bundleID = Bundle.main.bundleIdentifier ?? "missing-bundle-id"
        let executable = Bundle.main.executableURL?.path ?? "missing-executable"
        let bundlePath = Bundle.main.bundleURL.path
        print("MicRequestApp launch")
        print("  PID: \(ProcessInfo.processInfo.processIdentifier)")
        print("  Bundle ID: \(bundleID)")
        print("  Bundle path: \(bundlePath)")
        print("  Executable: \(executable)")
    }
}

// ─────────────────────────────────────────────────────────────────
// Entry point — must use NSApplication properly (not CommandLine)
// for TCC to attribute the request to THIS app bundle, not Terminal
// ─────────────────────────────────────────────────────────────────
let app = NSApplication.shared
app.setActivationPolicy(.regular)   // Show in Dock (required for TCC dialog to appear)
let delegate = AppDelegate()
app.delegate = delegate
app.run()
