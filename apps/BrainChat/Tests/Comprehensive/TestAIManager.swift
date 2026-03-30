import Foundation
import XCTest
@testable import BrainChatLib

final class TestAIManager: XCTestCase {
    func testPrefersClaudeWhenClaudeKeyExists() {
        let manager = AIManager(httpClient: MockHTTPClient())
        XCTAssertEqual(manager.route(for: TestFixtures.claudeConfig), .claude)
    }

    func testUsesOpenAIWhenEnabledAndNoClaude() {
        let manager = AIManager(httpClient: MockHTTPClient())
        XCTAssertEqual(manager.route(for: TestFixtures.openAIConfig), .gpt)
    }

    func testFallsBackToOllama() {
        let manager = AIManager(httpClient: MockHTTPClient())
        XCTAssertEqual(manager.route(for: TestFixtures.ollamaConfig), .ollama)
    }

    func testBuildsAccessibleOpenAIRequest() throws {
        let manager = AIManager(httpClient: MockHTTPClient())
        let request = try manager.makeOpenAIRequest(message: "Help", history: TestFixtures.history, config: TestFixtures.openAIConfig)
        let json = try XCTUnwrap(try JSONSerialization.jsonObject(with: XCTUnwrap(request.httpBody)) as? [String: Any])
        let messages = try XCTUnwrap(json["messages"] as? [[String: String]])
        XCTAssertEqual(messages.first?["content"], "Accessible prompt")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer openai-key")
    }

    func testBuildsClaudeRequest() throws {
        let manager = AIManager(httpClient: MockHTTPClient())
        let request = try manager.makeClaudeRequest(message: "Hi", history: TestFixtures.history, config: TestFixtures.claudeConfig)
        XCTAssertEqual(request.value(forHTTPHeaderField: "x-api-key"), "claude-key")
        let json = try XCTUnwrap(try JSONSerialization.jsonObject(with: XCTUnwrap(request.httpBody)) as? [String: Any])
        XCTAssertEqual(json["system"] as? String, "Accessible prompt")
    }

    func testParsesOllamaResponse() {
        let manager = AIManager(httpClient: MockHTTPClient())
        let response = manager.parseResponse(
            data: TestFixtures.jsonData(["message": ["content": "Ollama reply"]]),
            response: HTTPURLResponse(url: URL(string: "http://localhost")!, statusCode: 200, httpVersion: nil, headerFields: nil)!,
            backend: .ollama,
            endpoint: URL(string: "http://localhost")
        )
        XCTAssertEqual(response.text, "Ollama reply")
    }

    func testSendUsesMockHTTPClient() async {
        let client = MockHTTPClient()
        client.nextResult = .success((
            TestFixtures.jsonData(["choices": [["message": ["content": "GPT reply"]]]]),
            HTTPURLResponse(url: URL(string: "https://api.openai.com")!, statusCode: 200, httpVersion: nil, headerFields: nil)!
        ))
        let manager = AIManager(httpClient: client)
        let response = await manager.send(message: "Need help", history: TestFixtures.history, config: TestFixtures.openAIConfig)
        XCTAssertEqual(response.backend, .gpt)
        XCTAssertEqual(response.text, "GPT reply")
        XCTAssertEqual(client.lastRequest?.url?.absoluteString, "https://api.openai.com/v1/chat/completions")
    }
}
