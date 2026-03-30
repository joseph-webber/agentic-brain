import Foundation
@testable import BrainChat

final class MockCopilotCLI: CopilotCLIRunning {
    var isAvailable = true
    var runResult: Result<(stdout: String, stderr: String, exitCode: Int32), Error> = .success(("Done", "", 0))
    var prompts: [String] = []
    var cancelCallCount = 0

    func run(prompt: String, cliPath: String, timeout: TimeInterval) throws -> (stdout: String, stderr: String, exitCode: Int32) {
        prompts.append(prompt)
        switch runResult {
        case .success(let value): return value
        case .failure(let error): throw error
        }
    }

    func cancel() {
        cancelCallCount += 1
    }
}
