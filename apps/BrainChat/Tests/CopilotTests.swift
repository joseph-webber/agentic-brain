import XCTest
@testable import BrainChatLib

final class CopilotTests: XCTestCase {
    func testCLIExecution() async throws {
        let box = CopilotRunnerBox()
        box.result = .success("copilot says hi")
        let client = CopilotClient(runner: MockCopilotRunner(box: box))
        let deltas = StringArrayBox()

        let response = try await client.streamResponse(prompt: "hello", yoloMode: false) { deltas.values.append($0) }

        XCTAssertEqual(box.capturedPrompt, "hello")
        XCTAssertEqual(deltas.values, ["copilot says hi"])
        XCTAssertEqual(response, "copilot says hi")
    }

    func testResponseParsing() {
        let bridge = CopilotBridge(runner: MockCopilotCLIRunner())
        let response = bridge.parseResponse("```swift\nprint(\"hi\")\n```", duration: 0.2)
        XCTAssertTrue(response.isCodeBlock)
        XCTAssertEqual(response.language, "swift")
        XCTAssertEqual(response.codeBlocks.count, 1)
    }

    func testTimeout30Seconds() async {
        let box = CopilotRunnerBox()
        box.result = .failure(AIServiceError.httpStatus(408, "Copilot CLI timed out after 30 seconds."))
        let client = CopilotClient(timeout: 30, runner: MockCopilotRunner(box: box))

        do {
            _ = try await client.streamResponse(prompt: "slow task", yoloMode: false, onDelta: { _ in })
            XCTFail("Expected timeout")
        } catch {
            if case let AIServiceError.httpStatus(code, message) = error {
                XCTAssertEqual(code, 408)
                XCTAssertEqual(message, "Copilot CLI timed out after 30 seconds.")
            } else {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    func testCodeBlockExtraction() {
        let bridge = CopilotBridge(runner: MockCopilotCLIRunner())
        let blocks = bridge.extractCodeBlocks(from: """
        Here you go
        ```swift
        print(\"hi\")
        ```
        ```python
        print('hi')
        ```
        """)

        XCTAssertEqual(blocks.count, 2)
        XCTAssertEqual(blocks.first?.language, "swift")
        XCTAssertTrue(blocks[1].code.contains("print('hi')"))
    }

    func testMockCLIForCI() async throws {
        let box = CopilotRunnerBox()
        box.result = .success("/yolo result")
        let client = CopilotClient(runner: MockCopilotRunner(box: box))

        let response = try await client.streamResponse(prompt: "build tests", yoloMode: true, onDelta: { _ in })

        XCTAssertEqual(box.capturedPrompt, "/yolo build tests")
        XCTAssertEqual(response, "/yolo result")
    }
}
