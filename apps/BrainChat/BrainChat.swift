import AppKit
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

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        BridgeDaemon.shared.startIfNeeded()
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)

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

    func applicationWillTerminate(_ notification: Notification) {
        BridgeDaemon.shared.stop()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }
}
