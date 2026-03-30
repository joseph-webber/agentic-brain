import XCTest
@testable import BrainChat

final class TestCopilotBridge: XCTestCase {
    func testUnavailableCLIReportsError() async {
        let runner = MockCopilotCLI()
        runner.isAvailable = false
        let bridge = CopilotBridge(runner: runner)
        do {
            _ = try await bridge.execute(prompt: "hello")
            XCTFail("Expected cliNotFound")
        } catch {
            XCTAssertEqual(error as? CopilotError, .cliNotFound)
        }
    }

    func testParsesCodeBlocks() {
        let runner = MockCopilotCLI()
        let bridge = CopilotBridge(runner: runner)
        let response = bridge.parseResponse("Here\n```swift\nprint(\"hi\")\n```", duration: 0.5)
        XCTAssertTrue(response.isCodeBlock)
        XCTAssertEqual(response.language, "swift")
        XCTAssertEqual(response.codeBlocks.first?.code, "print(\"hi\")")
    }

    func testExecuteReturnsParsedResponse() async throws {
        let runner = MockCopilotCLI()
        runner.runResult = .success(("```python\nprint('hi')\n```", "", 0))
        let bridge = CopilotBridge(runner: runner)
        let response = try await bridge.execute(prompt: "write python")
        XCTAssertEqual(runner.prompts, ["write python"])
        XCTAssertEqual(response.language, "python")
    }

    func testExecutePropagatesFailure() async {
        let runner = MockCopilotCLI()
        runner.runResult = .failure(CopilotError.timeout)
        let bridge = CopilotBridge(runner: runner)
        do {
            _ = try await bridge.execute(prompt: "wait")
            XCTFail("Expected timeout")
        } catch {
            XCTAssertEqual(error as? CopilotError, .timeout)
        }
    }
}
