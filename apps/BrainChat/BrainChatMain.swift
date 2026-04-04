import Foundation
import SwiftUI

@main
enum BrainChatLauncher {
    static func main() async {
        if let command = BrainChatCLICommand(arguments: CommandLine.arguments) {
            let exitCode = await BrainChatCLIHandler.run(command)
            fflush(stdout)
            fflush(stderr)
            exit(exitCode)
        }

        BrainChatApp.main()
    }
}
