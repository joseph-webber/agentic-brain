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

struct BrainChatApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
    // MARK: - Lazy Initialization for Performance
    // StateObjects are lazy-initialized only when needed
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
                .onAppear {
                    // Defer scripting bridge initialization to avoid startup delays
                    Task { @MainActor in
                        let bridge = ScriptingBridge.shared
                        bridge.conversationStore = conversationStore
                        bridge.speechManager = speechManager
                        bridge.voiceManager = voiceManager
                        bridge.settings = settings
                        bridge.llmRouter = llmRouter
                    }
                }
        }
        .commands {
            CommandGroup(replacing: .newItem) {}
        }
        Settings {
            SettingsView()
                .environmentObject(settings)
                .environmentObject(voiceManager)
                .environmentObject(llmRouter)
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, @unchecked Sendable {
    private let profiler = PerformanceProfiler.shared
    private var launchStartTime = Date()
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        launchStartTime = Date()
        profiler.markInitStart("AppDelegate.applicationDidFinishLaunching")
        
        // OPTIMIZATION: Run non-critical initialization in background
        Task.detached { [weak self] in
            self?.profiler.markInitStart("BridgeDaemon.startup")
            BridgeDaemon.shared.startIfNeeded()
            self?.profiler.markInitEnd("BridgeDaemon.startup")
        }
        
        // Main thread: UI setup only
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)

        // OPTIMIZATION: Defer microphone permission request to avoid blocking
        Task.detached { [weak self] in
            self?.profiler.markInitStart("Microphone.permission")
            self?.requestMicrophonePermission()
            self?.profiler.markInitEnd("Microphone.permission")
        }

        // Window setup - minimal work on main thread
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            if let window = NSApp.windows.first {
                window.title = "Brain Chat"
                window.makeKeyAndOrderFront(nil)
            }
        }

        // OPTIMIZATION: Defer greeting message to background
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            Task.detached { [weak self] in
                self?.profiler.markInitStart("Greeting.audio")
                BrainChatRuntimeMarker.write("last-greeting.txt", value: "G'day Joseph")
                let task = Process()
                task.executableURL = URL(fileURLWithPath: "/usr/bin/say")
                task.arguments = ["-v", "Karen", "-r", "160", "G'day Joseph"]
                try? task.run()
                self?.profiler.markInitEnd("Greeting.audio")
                
                // Log total startup time
                if let startTime = self?.launchStartTime {
                    let totalTime = Date().timeIntervalSince(startTime)
                    if totalTime < 0.5 {
                        print("✅ App startup: \(String(format: "%.0f", totalTime * 1000))ms")
                    } else {
                        print("⚠️ App startup: \(String(format: "%.0f", totalTime * 1000))ms (target: <500ms)")
                    }
                }
            }
        }
        
        profiler.markInitEnd("AppDelegate.applicationDidFinishLaunching")
    }
    
    /// Request microphone permission to ensure Brain Chat appears in System Settings > Privacy
    /// OPTIMIZATION: Non-blocking async implementation
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
            // Announce - deferred to background
            Task.detached {
                let task = Process()
                task.executableURL = URL(fileURLWithPath: "/usr/bin/say")
                task.arguments = ["-v", "Karen", "-r", "160", "Opening microphone settings. Please enable Brain Chat."]
                try? task.run()
            }
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        Task.detached {
            BridgeDaemon.shared.stop()
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }
}
