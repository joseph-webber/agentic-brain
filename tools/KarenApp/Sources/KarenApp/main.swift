import AppKit
import Foundation
import SwiftUI

enum KarenAppConstants {
    static let bundleIdentifier = "com.josephwebber.brain.karenapp"
    static let appName = "Karen Voice Chat"
    static let minimumMacOSVersion = "13.0"
    static let redisListKey = "brain:karen_app:events"

    static var homeDirectory: String {
        FileManager.default.homeDirectoryForCurrentUser.path
    }

    static var repoDirectory: String {
        ProcessInfo.processInfo.environment["KAREN_APP_REPO"] ?? "\(homeDirectory)/brain/agentic-brain"
    }

    static var virtualEnvActivatePath: String {
        ProcessInfo.processInfo.environment["KAREN_APP_VENV_ACTIVATE"] ?? "\(homeDirectory)/brain/venv/bin/activate"
    }

    static var voiceChatScriptPath: String {
        ProcessInfo.processInfo.environment["KAREN_APP_CHAT_SCRIPT"] ?? "\(repoDirectory)/karen_voice_chat.py"
    }
}

final class KarenAppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag {
            sender.windows.forEach { $0.makeKeyAndOrderFront(nil) }
        }
        return true
    }
}

KarenAppApp.main()
