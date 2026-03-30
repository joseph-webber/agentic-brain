import AVFoundation
import Cocoa

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.activate(ignoringOtherApps: true)
        
        let status = AVCaptureDevice.authorizationStatus(for: .audio)
        print("Current mic status: \(status.rawValue)")
        
        switch status {
        case .authorized:
            showAlert(title: "Microphone Access", message: "✅ Already authorized! You're good to go.", success: true)
        case .notDetermined:
            print("Requesting access...")
            AVCaptureDevice.requestAccess(for: .audio) { granted in
                DispatchQueue.main.async {
                    if granted {
                        self.showAlert(title: "Success!", message: "✅ Microphone access granted! You can now use voice chat.", success: true)
                    } else {
                        self.showAlert(title: "Denied", message: "❌ Microphone access was denied. Please enable in System Settings.", success: false)
                    }
                }
            }
        case .denied, .restricted:
            // Open System Settings
            if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone") {
                NSWorkspace.shared.open(url)
            }
            showAlert(title: "Permission Needed", message: "Please enable microphone access for Terminal in System Settings, then run this again.", success: false)
        @unknown default:
            break
        }
    }
    
    func showAlert(title: String, message: String, success: Bool) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = message
        alert.alertStyle = success ? .informational : .warning
        alert.addButton(withTitle: "OK")
        alert.runModal()
        NSApp.terminate(nil)
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
