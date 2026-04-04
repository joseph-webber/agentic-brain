import Foundation
import SwiftUI

@main
enum BrainChatLauncher {
    static func main() {
        // Check for CLI command FIRST (synchronous check)
        if let command = BrainChatCLICommand(arguments: CommandLine.arguments) {
            // CLI mode: don't block the main thread, use RunLoop for async
            Task { @MainActor in
                let exitCode = await BrainChatCLIHandler.run(command)
                fflush(stdout)
                fflush(stderr)
                exit(exitCode)
            }
            // Keep main thread alive for CLI tasks
            RunLoop.main.run()
            return
        }

        // Launch SwiftUI app on main thread
        BrainChatApp.main()
    }
}
