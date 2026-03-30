import SwiftUI

struct KarenAppApp: App {
    @NSApplicationDelegateAdaptor(KarenAppDelegate.self) private var appDelegate
    @StateObject private var manager = VoiceChatManager()

    var body: some Scene {
        WindowGroup {
            ContentView(manager: manager)
                .frame(minWidth: 620, idealWidth: 680, minHeight: 520, idealHeight: 560)
        }
        .windowResizability(.contentSize)
        .commands {
            CommandGroup(replacing: .newItem) { }
        }
    }
}
