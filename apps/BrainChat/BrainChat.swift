import AppKit
import AVFoundation
import AVFAudio
import SwiftUI
import Foundation

private enum BrainChatRuntimeMarker {
    static let directory = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("brain/agentic-brain/apps/BrainChat/runtime", isDirectory: true)

    static func write(_ filename: String, value: String) {
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try? value.write(to: directory.appendingPathComponent(filename), atomically: true, encoding: .utf8)
    }
}

@main
struct BrainChatApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var conversationStore = ConversationStore()
    @StateObject private var speechManager = SpeechManager()
    @StateObject private var voiceManager = VoiceManager()
    @StateObject private var settings = AppSettings()
    @StateObject private var llmRouter = LLMRouter()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(conversationStore)
                .environmentObject(speechManager)
                .environmentObject(voiceManager)
                .environmentObject(settings)
                .environmentObject(llmRouter)
                .frame(minWidth: 600, minHeight: 500)
        }
        .commands {
            CommandGroup(replacing: .newItem) {}
        }
        Settings {
            SettingsView()
                .environmentObject(settings)
                .environmentObject(voiceManager)
                .environmentObject(llmRouter)
                .frame(minWidth: 500, minHeight: 420)
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, @unchecked Sendable {
    func applicationDidFinishLaunching(_ notification: Notification) {
        BridgeDaemon.shared.startIfNeeded()
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)

        // Request microphone permission immediately on app launch
        // This ensures Brain Chat appears in System Settings > Privacy > Microphone
        requestMicrophonePermission()

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            if let window = NSApp.windows.first {
                window.title = "Brain Chat"
                window.makeKeyAndOrderFront(nil)
            }
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            BrainChatRuntimeMarker.write("last-greeting.txt", value: "G'day Joseph")
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/usr/bin/say")
            task.arguments = ["-v", "Karen", "-r", "160", "G'day Joseph"]
            try? task.run()
        }
    }
    
    /// Request microphone permission to ensure Brain Chat appears in System Settings > Privacy
    /// Uses AVAudioApplication for macOS 14+ which is the correct modern API
    private func requestMicrophonePermission() {
        BrainChatRuntimeMarker.write("mic-status.txt", value: "Starting mic permission request...")
        
        // Use modern AVAudioApplication API for macOS 14+
        if #available(macOS 14.0, *) {
            let audioApp = AVAudioApplication.shared
            let permission = audioApp.recordPermission
            BrainChatRuntimeMarker.write("mic-status.txt", value: "AVAudioApplication permission: \(permission.rawValue)")
            
            switch permission {
            case .undetermined:
                BrainChatRuntimeMarker.write("mic-status.txt", value: "Requesting via AVAudioApplication...")
                AVAudioApplication.requestRecordPermission { [weak self] granted in
                    BrainChatRuntimeMarker.write("mic-status.txt", value: "AVAudioApp result: granted=\(granted)")
                    if !granted {
                        DispatchQueue.main.async { [weak self] in
                            self?.openMicrophoneSettings()
                        }
                    }
                }
            case .denied:
                BrainChatRuntimeMarker.write("mic-status.txt", value: "Mic denied - opening settings")
                openMicrophoneSettings()
            case .granted:
                BrainChatRuntimeMarker.write("mic-status.txt", value: "Mic already granted!")
            @unknown default:
                break
            }
        } else {
            // Fallback for older macOS
            let status = AVCaptureDevice.authorizationStatus(for: .audio)
            BrainChatRuntimeMarker.write("mic-status.txt", value: "AVCaptureDevice status: \(status.rawValue)")
            
            switch status {
            case .notDetermined:
                AVCaptureDevice.requestAccess(for: .audio) { [weak self] granted in
                    BrainChatRuntimeMarker.write("mic-status.txt", value: "Requested: granted=\(granted)")
                    if !granted {
                        DispatchQueue.main.async { [weak self] in
                            self?.openMicrophoneSettings()
                        }
                    }
                }
            case .restricted, .denied:
                BrainChatRuntimeMarker.write("mic-status.txt", value: "Mic denied or restricted")
                openMicrophoneSettings()
            case .authorized:
                BrainChatRuntimeMarker.write("mic-status.txt", value: "Mic already authorized")
            @unknown default:
                break
            }
        }
    }
    
    /// Open System Settings directly to microphone permissions
    private func openMicrophoneSettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone") {
            NSWorkspace.shared.open(url)
            // Announce
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/usr/bin/say")
            task.arguments = ["-v", "Karen", "-r", "160", "Opening microphone settings. Please enable Brain Chat."]
            try? task.run()
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        BridgeDaemon.shared.stop()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }
}
