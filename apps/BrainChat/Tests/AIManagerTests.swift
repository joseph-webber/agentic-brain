import XCTest
@testable import BrainChatLib

// MARK: - Mock AI Client

final class MockAIClient: AIClientProtocol {
    var responses: [String: String] = [:]
    var callCount = 0
    var lastMessage: String?
    var lastModel: String?
    var lastEndpoint: String?
    var shouldFail = false
    var failureError: Error = NSError(domain: "MockAI", code: -1,
                                       userInfo: [NSLocalizedDescriptionKey: "Mock failure"])

    func sendMessage(_ message: String, model: String, endpoint: String,
                     completion: @escaping (Result<String, Error>) -> Void) {
        callCount += 1
        lastMessage = message
        lastModel = model
        lastEndpoint = endpoint

        if shouldFail {
            completion(.failure(failureError))
            return
        }

        let response = responses[message] ?? "Mock response to: \(message)"
        completion(.success(response))
    }
}

// MARK: - AI Manager Tests

final class AIManagerTests: XCTestCase {

    // MARK: - Ollama API Tests

    func testOllamaRequestFormat() throws {
        let _ = "http://localhost:11434/api/chat"
        let model = "llama3.2:3b"
        let message = "Hello Brain"

        let body: [String: Any] = [
            "model": model,
            "messages": [
                ["role": "system", "content": "You are Brain Chat, a helpful AI assistant."],
                ["role": "user", "content": message]
            ],
            "stream": false
        ]

        let data = try JSONSerialization.data(withJSONObject: body)
        let parsed = try JSONSerialization.jsonObject(with: data) as! [String: Any]

        XCTAssertEqual(parsed["model"] as? String, model)
        XCTAssertFalse(parsed["stream"] as! Bool)

        let messages = parsed["messages"] as! [[String: String]]
        XCTAssertEqual(messages.count, 2)
        XCTAssertEqual(messages[0]["role"], "system")
        XCTAssertEqual(messages[1]["role"], "user")
        XCTAssertEqual(messages[1]["content"], message)
    }

    func testOllamaResponseParsing() throws {
        let json = """
        {
            "model": "llama3.2:3b",
            "message": {
                "role": "assistant",
                "content": "Hello! How can I help you today?"
            },
            "done": true
        }
        """.data(using: .utf8)!

        let parsed = try JSONSerialization.jsonObject(with: json) as! [String: Any]
        let messageObj = parsed["message"] as! [String: String]

        XCTAssertEqual(messageObj["role"], "assistant")
        XCTAssertEqual(messageObj["content"], "Hello! How can I help you today?")
        XCTAssertTrue(parsed["done"] as! Bool)
    }

    func testOllamaErrorResponse() throws {
        let json = """
        {
            "error": "model 'nonexistent' not found"
        }
        """.data(using: .utf8)!

        let parsed = try JSONSerialization.jsonObject(with: json) as! [String: Any]
        XCTAssertNotNil(parsed["error"])
        XCTAssertEqual(parsed["error"] as? String, "model 'nonexistent' not found")
    }

    // MARK: - OpenAI API Tests

    func testOpenAIRequestFormat() throws {
        let model = "gpt-4o"
        let message = "Tell me about Swift"
        let apiKey = "sk-test-key-12345"

        let body: [String: Any] = [
            "model": model,
            "messages": [
                ["role": "system", "content": "You are a helpful assistant."],
                ["role": "user", "content": message]
            ]
        ]

        let data = try JSONSerialization.data(withJSONObject: body)
        let parsed = try JSONSerialization.jsonObject(with: data) as! [String: Any]

        XCTAssertEqual(parsed["model"] as? String, model)

        let messages = parsed["messages"] as! [[String: String]]
        XCTAssertEqual(messages[1]["content"], message)

        // Verify auth header format
        let authHeader = "Bearer \(apiKey)"
        XCTAssertTrue(authHeader.hasPrefix("Bearer "))
        XCTAssertTrue(authHeader.contains("sk-test"))
    }

    func testOpenAIResponseParsing() throws {
        let json = """
        {
            "id": "chatcmpl-abc123",
            "object": "chat.completion",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Swift is a programming language by Apple."
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18
            }
        }
        """.data(using: .utf8)!

        let parsed = try JSONSerialization.jsonObject(with: json) as! [String: Any]
        let choices = parsed["choices"] as! [[String: Any]]
        let firstChoice = choices[0]
        let messageObj = firstChoice["message"] as! [String: String]

        XCTAssertEqual(messageObj["content"], "Swift is a programming language by Apple.")
        XCTAssertEqual(firstChoice["finish_reason"] as? String, "stop")
    }

    // MARK: - Mock Client Tests

    func testMockClientSuccessResponse() {
        let client = MockAIClient()
        client.responses["hello"] = "Hi there!"

        let expectation = XCTestExpectation(description: "AI response")

        client.sendMessage("hello", model: "test", endpoint: "http://test") { result in
            switch result {
            case .success(let response):
                XCTAssertEqual(response, "Hi there!")
            case .failure:
                XCTFail("Expected success")
            }
            expectation.fulfill()
        }

        wait(for: [expectation], timeout: 1.0)
        XCTAssertEqual(client.callCount, 1)
        XCTAssertEqual(client.lastMessage, "hello")
    }

    func testMockClientFailure() {
        let client = MockAIClient()
        client.shouldFail = true

        let expectation = XCTestExpectation(description: "AI failure")

        client.sendMessage("hello", model: "test", endpoint: "http://test") { result in
            switch result {
            case .success:
                XCTFail("Expected failure")
            case .failure(let error):
                XCTAssertEqual(error.localizedDescription, "Mock failure")
            }
            expectation.fulfill()
        }

        wait(for: [expectation], timeout: 1.0)
    }

    // MARK: - Conversation History Tests

    func testConversationHistoryBuilding() throws {
        let store = TestConversationStore()
        store.addMessage(role: .user, content: "Hello")
        store.addMessage(role: .assistant, content: "Hi there!")
        store.addMessage(role: .user, content: "How are you?")

        XCTAssertEqual(store.messages.count, 3)

        // Build API messages from history
        var apiMessages: [[String: String]] = [
            ["role": "system", "content": "You are Brain Chat."]
        ]

        for msg in store.messages {
            let role: String
            switch msg.role {
            case .user: role = "user"
            case .assistant: role = "assistant"
            case .system: role = "system"
            }
            apiMessages.append(["role": role, "content": msg.content])
        }

        XCTAssertEqual(apiMessages.count, 4) // system + 3 messages
        XCTAssertEqual(apiMessages[1]["role"], "user")
        XCTAssertEqual(apiMessages[2]["role"], "assistant")
        XCTAssertEqual(apiMessages[3]["content"], "How are you?")
    }

    func testConversationHistoryTruncation() {
        let store = TestConversationStore()

        // Add many messages
        for i in 0..<100 {
            store.addMessage(role: .user, content: "Message \(i)")
            store.addMessage(role: .assistant, content: "Response \(i)")
        }

        XCTAssertEqual(store.messages.count, 200)

        // Truncate to last 20 for API (common pattern)
        let recentMessages = Array(store.messages.suffix(20))
        XCTAssertEqual(recentMessages.count, 20)
        XCTAssertEqual(recentMessages.first?.content, "Message 90")
    }

    // MARK: - Endpoint Validation

    func testOllamaEndpointValidation() {
        let validEndpoints = [
            "http://localhost:11434/api/chat",
            "http://127.0.0.1:11434/api/chat",
            "http://localhost:11434/api/generate"
        ]

        for endpoint in validEndpoints {
            let url = URL(string: endpoint)
            XCTAssertNotNil(url, "Invalid endpoint: \(endpoint)")
            XCTAssertTrue(
                url?.host == "localhost" || url?.host == "127.0.0.1",
                "Unexpected host for: \(endpoint)"
            )
        }
    }

    func testOpenAIEndpointValidation() {
        let endpoint = "https://api.openai.com/v1/chat/completions"
        let url = URL(string: endpoint)
        XCTAssertNotNil(url)
        XCTAssertEqual(url?.scheme, "https")
        XCTAssertEqual(url?.host, "api.openai.com")
    }
}
