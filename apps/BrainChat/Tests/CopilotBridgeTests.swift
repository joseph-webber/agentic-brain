import XCTest
@testable import BrainChatLib

// MARK: - Mock Copilot Bridge

final class MockCopilotBridge {
    var isAvailable: Bool = true
    var isBusy: Bool = false
    var responses: [String: TestCopilotResponse] = [:]
    var shouldFail = false
    var failureError: Error = NSError(domain: "MockCopilot", code: -1,
                                       userInfo: [NSLocalizedDescriptionKey: "Mock copilot failure"])
    var executeCallCount = 0
    var lastPrompt: String?
    var cancelCallCount = 0

    func execute(prompt: String, completion: @escaping (Result<TestCopilotResponse, Error>) -> Void) {
        executeCallCount += 1
        lastPrompt = prompt

        guard !isBusy else {
            completion(.failure(NSError(domain: "Copilot", code: 1,
                                         userInfo: [NSLocalizedDescriptionKey: "Already running"])))
            return
        }

        guard isAvailable else {
            completion(.failure(NSError(domain: "Copilot", code: 2,
                                         userInfo: [NSLocalizedDescriptionKey: "CLI not found"])))
            return
        }

        if shouldFail {
            completion(.failure(failureError))
            return
        }

        isBusy = true
        let response = responses[prompt] ?? TestCopilotResponse(
            text: "Copilot response to: \(prompt)",
            duration: 0.5
        )
        isBusy = false
        completion(.success(response))
    }

    func cancel() {
        cancelCallCount += 1
        isBusy = false
    }
}

// MARK: - Copilot Bridge Tests

final class CopilotBridgeTests: XCTestCase {

    // MARK: - Availability

    func testCLIAvailabilityCheck() {
        let mock = MockCopilotBridge()
        XCTAssertTrue(mock.isAvailable)
    }

    func testCLINotAvailable() {
        let mock = MockCopilotBridge()
        mock.isAvailable = false

        let expectation = XCTestExpectation(description: "CLI not found")

        mock.execute(prompt: "test") { result in
            switch result {
            case .success:
                XCTFail("Should fail when CLI not available")
            case .failure(let error):
                XCTAssertTrue(error.localizedDescription.contains("not found"))
            }
            expectation.fulfill()
        }

        wait(for: [expectation], timeout: 1.0)
    }

    // MARK: - Execution

    func testSuccessfulExecution() {
        let mock = MockCopilotBridge()
        mock.responses["write hello world in swift"] = TestCopilotResponse(
            text: "```swift\nprint(\"Hello, World!\")\n```",
            duration: 1.2,
            isCodeBlock: true,
            language: "swift",
            codeBlocks: [(language: "swift", code: "print(\"Hello, World!\")")]
        )

        let expectation = XCTestExpectation(description: "Copilot response")

        mock.execute(prompt: "write hello world in swift") { result in
            switch result {
            case .success(let response):
                XCTAssertTrue(response.isCodeBlock)
                XCTAssertEqual(response.language, "swift")
                XCTAssertEqual(response.codeBlocks.count, 1)
                XCTAssertTrue(response.text.contains("Hello, World!"))
            case .failure:
                XCTFail("Expected success")
            }
            expectation.fulfill()
        }

        wait(for: [expectation], timeout: 1.0)
        XCTAssertEqual(mock.executeCallCount, 1)
    }

    func testAlreadyRunningError() {
        let mock = MockCopilotBridge()
        mock.isBusy = true

        let expectation = XCTestExpectation(description: "Already running")

        mock.execute(prompt: "test") { result in
            switch result {
            case .success:
                XCTFail("Should fail when busy")
            case .failure(let error):
                XCTAssertTrue(error.localizedDescription.contains("Already running"))
            }
            expectation.fulfill()
        }

        wait(for: [expectation], timeout: 1.0)
    }

    func testCancelExecution() {
        let mock = MockCopilotBridge()
        mock.isBusy = true
        mock.cancel()

        XCTAssertFalse(mock.isBusy)
        XCTAssertEqual(mock.cancelCallCount, 1)
    }

    // MARK: - Code Block Parsing

    func testCodeBlockExtraction() {
        let parser = CodeBlockParser()
        let markdown = """
        Here's the code:

        ```swift
        func greet() {
            print("Hello!")
        }
        ```

        And more:

        ```python
        def greet():
            print("Hello!")
        ```
        """

        let blocks = parser.extractCodeBlocks(from: markdown)
        XCTAssertEqual(blocks.count, 2)
        XCTAssertEqual(blocks[0].language, "swift")
        XCTAssertTrue(blocks[0].code.contains("func greet()"))
        XCTAssertEqual(blocks[1].language, "python")
        XCTAssertTrue(blocks[1].code.contains("def greet()"))
    }

    func testCodeBlockNoLanguage() {
        let parser = CodeBlockParser()
        let markdown = """
        ```
        some code here
        ```
        """

        let blocks = parser.extractCodeBlocks(from: markdown)
        XCTAssertEqual(blocks.count, 1)
        XCTAssertNil(blocks[0].language)
    }

    func testNoCodeBlocks() {
        let parser = CodeBlockParser()
        let text = "Just regular text without any code blocks."

        let blocks = parser.extractCodeBlocks(from: text)
        XCTAssertTrue(blocks.isEmpty)
    }

    func testEmptyCodeBlock() {
        let parser = CodeBlockParser()
        let markdown = """
        ```swift
        ```
        """

        let blocks = parser.extractCodeBlocks(from: markdown)
        XCTAssertTrue(blocks.isEmpty, "Empty code blocks should be filtered")
    }

    func testNestedMarkdown() {
        let parser = CodeBlockParser()
        let markdown = """
        ```swift
        let x = "```not a block```"
        let y = 42
        ```
        """

        let blocks = parser.extractCodeBlocks(from: markdown)
        // Due to line-by-line parsing, the inner backticks terminate the block
        XCTAssertGreaterThanOrEqual(blocks.count, 1)
    }

    // MARK: - Response Duration

    func testResponseDuration() {
        let response = TestCopilotResponse(text: "test", duration: 2.5)
        XCTAssertEqual(response.duration, 2.5, accuracy: 0.01)
    }

    // MARK: - Prompt Tracking

    func testLastPromptTracked() {
        let mock = MockCopilotBridge()

        let exp = XCTestExpectation(description: "execute")
        mock.execute(prompt: "explain this code") { _ in exp.fulfill() }
        wait(for: [exp], timeout: 1.0)

        XCTAssertEqual(mock.lastPrompt, "explain this code")
    }

    // MARK: - Error Handling

    func testTimeoutError() {
        let mock = MockCopilotBridge()
        mock.shouldFail = true
        mock.failureError = NSError(domain: "Copilot", code: 3,
                                     userInfo: [NSLocalizedDescriptionKey: "Timed out after 30 seconds"])

        let exp = XCTestExpectation(description: "timeout")
        mock.execute(prompt: "complex query") { result in
            switch result {
            case .success:
                XCTFail("Should timeout")
            case .failure(let error):
                XCTAssertTrue(error.localizedDescription.contains("Timed out"))
            }
            exp.fulfill()
        }

        wait(for: [exp], timeout: 1.0)
    }

    func testExecutionFailedError() {
        let mock = MockCopilotBridge()
        mock.shouldFail = true
        mock.failureError = NSError(domain: "Copilot", code: 1,
                                     userInfo: [NSLocalizedDescriptionKey: "Exit code 1: command not found"])

        let exp = XCTestExpectation(description: "exec fail")
        mock.execute(prompt: "bad command") { result in
            if case .failure(let error) = result {
                XCTAssertTrue(error.localizedDescription.contains("Exit code"))
            } else {
                XCTFail("Expected failure")
            }
            exp.fulfill()
        }

        wait(for: [exp], timeout: 1.0)
    }
}
