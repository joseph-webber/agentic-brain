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
    
    // Use a single shared coordinator to manage all state
    @StateObject private var appState = BrainChatAppState()

    var body: some Scene {
        WindowGroup {
            BrainChatRootView()
                .environmentObject(appState)
        }
        .commands {
            CommandGroup(replacing: .newItem) {}
        }
        Settings {
            if let settings = appState.settings, let voiceManager = appState.voiceManager, let llmRouter = appState.llmRouter {
                SettingsView()
                    .environmentObject(settings)
                    .environmentObject(voiceManager)
                    .environmentObject(llmRouter)
                    .frame(minWidth: 500, minHeight: 420)
            }
        }
    }
}

/// Root view that initializes all components on the main actor safely
struct BrainChatRootView: View {
    @EnvironmentObject var appState: BrainChatAppState
    
    var body: some View {
        Group {
            if let store = appState.conversationStore,
               let speechManager = appState.speechManager,
               let voiceManager = appState.voiceManager,
               let settings = appState.settings,
               let llmRouter = appState.llmRouter {
                ContentView()
                    .environmentObject(store)
                    .environmentObject(speechManager)
                    .environmentObject(voiceManager)
                    .environmentObject(settings)
                    .environmentObject(llmRouter)
                    .frame(minWidth: 600, minHeight: 500)
                    .onAppear {
                        let bridge = ScriptingBridge.shared
                        bridge.conversationStore = store
                        bridge.speechManager = speechManager
                        bridge.voiceManager = voiceManager
                        bridge.settings = settings
                        bridge.llmRouter = llmRouter
                    }
            } else {
                ProgressView("Loading Brain Chat...")
                    .onAppear {
                        Task { @MainActor in
                            appState.initialize()
                        }
                    }
            }
        }
    }
}

/// App state holder that initializes lazily on the main actor
@MainActor
final class BrainChatAppState: ObservableObject {
    @Published var conversationStore: ConversationStore?
    @Published var speechManager: SpeechManager?
    @Published var voiceManager: VoiceManager?
    @Published var settings: AppSettings?
    @Published var llmRouter: LLMRouter?
    @Published var isInitialized = false
    
    func initialize() {
        guard !isInitialized else { return }
        isInitialized = true
        
        conversationStore = ConversationStore()
        speechManager = SpeechManager()
        voiceManager = VoiceManager()
        settings = AppSettings()
        llmRouter = LLMRouter()
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, @unchecked Sendable {
    func applicationDidFinishLaunching(_ notification: Notification) {
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

        // Delay bridge daemon start to after UI is ready
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
            Task { @MainActor in
                BridgeDaemon.shared.startIfNeeded()
            }
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            BrainChatRuntimeMarker.write("last-greeting.txt", value: "G'day")
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/usr/bin/say")
            task.arguments = ["-v", "Karen", "-r", "160", "G'day"]
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
