import Foundation
import XCTest
@testable import BrainChatLib

final class MockURLProtocol: URLProtocol, @unchecked Sendable {
    static var requestHandler: (@Sendable (URLRequest) throws -> (HTTPURLResponse, Data))?
    static var error: Error?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        if let error = Self.error {
            client?.urlProtocol(self, didFailWithError: error)
            return
        }

        guard let handler = Self.requestHandler else {
            XCTFail("MockURLProtocol.requestHandler not set")
            return
        }

        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}

    static func reset() {
        requestHandler = nil
        error = nil
    }
}

extension URLSession {
    static func mocked() -> URLSession {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        return URLSession(configuration: config)
    }
}

func httpResponse(url: URL, statusCode: Int = 200, headers: [String: String] = [:]) -> HTTPURLResponse {
    HTTPURLResponse(url: url, statusCode: statusCode, httpVersion: nil, headerFields: headers)!
}

func jsonBody(_ request: URLRequest) throws -> [String: Any] {
    let data = try XCTUnwrap(request.httpBody)
    return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
}

func makeConfig(
    provider: LLMProvider = .claude,
    yoloMode: Bool = false,
    claudeAPIKey: String = "claude-key",
    openAIAPIKey: String = "openai-key",
    groqAPIKey: String = "groq-key",
    grokAPIKey: String = "grok-key",
    geminiAPIKey: String = "gemini-key",
    ollamaEndpoint: String = "http://localhost:11434/api/chat"
) -> LLMRouterConfiguration {
    LLMRouterConfiguration(
        provider: provider,
        systemPrompt: "System prompt",
        yoloMode: yoloMode,
        bridgeWebSocketURL: "ws://localhost:8765",
        claudeAPIKey: claudeAPIKey,
        openAIAPIKey: openAIAPIKey,
        groqAPIKey: groqAPIKey,
        grokAPIKey: grokAPIKey,
        geminiAPIKey: geminiAPIKey,
        ollamaEndpoint: ollamaEndpoint,
        ollamaModel: "llama3.2:3b",
        claudeModel: "claude-sonnet-4-20250514",
        openAIModel: "gpt-4o",
        groqModel: "llama-3.1-8b-instant",
        grokModel: "grok-3-latest",
        geminiModel: "gemini-2.5-flash"
    )
}

struct MockClaudeStreamer: ClaudeStreaming {
    var handler: @Sendable (String, String, String, [AIChatMessage]) async throws -> String
    func streamResponse(apiKey: String, model: String, systemPrompt: String, messages: [AIChatMessage], onDelta: @escaping @Sendable (String) -> Void) async throws -> String {
        let result = try await handler(apiKey, model, systemPrompt, messages)
        onDelta(result)
        return result
    }
}

struct MockOpenAIStreamer: OpenAIStreaming {
    var handler: @Sendable (String, String, [AIChatMessage]) async throws -> String
    func streamResponse(apiKey: String, model: String, messages: [AIChatMessage], onDelta: @escaping @Sendable (String) -> Void) async throws -> String {
        let result = try await handler(apiKey, model, messages)
        onDelta(result)
        return result
    }
}

struct MockOllamaStreamer: OllamaStreaming {
    var handler: @Sendable (String, String, [AIChatMessage]) async throws -> String
    func streamResponse(endpoint: String, model: String, messages: [AIChatMessage], onDelta: @escaping @Sendable (String) -> Void) async throws -> String {
        let result = try await handler(endpoint, model, messages)
        onDelta(result)
        return result
    }
}

struct MockGroqStreamer: GroqStreaming {
    var handler: @Sendable (String, String, [AIChatMessage]) async throws -> String
    func streamResponse(apiKey: String, model: String, messages: [AIChatMessage], onDelta: @escaping @Sendable (String) -> Void) async throws -> String {
        let result = try await handler(apiKey, model, messages)
        onDelta(result)
        return result
    }
}

struct MockGrokStreamer: GrokStreaming {
    var handler: @Sendable (String, String, [AIChatMessage]) async throws -> String
    func streamResponse(apiKey: String, model: String, messages: [AIChatMessage], onDelta: @escaping @Sendable (String) -> Void) async throws -> String {
        let result = try await handler(apiKey, model, messages)
        onDelta(result)
        return result
    }
}

struct MockGeminiStreamer: GeminiStreaming {
    var handler: @Sendable (String, String, String, [AIChatMessage]) async throws -> String
    func streamResponse(apiKey: String, model: String, systemPrompt: String, messages: [AIChatMessage], onDelta: @escaping @Sendable (String) -> Void) async throws -> String {
        let result = try await handler(apiKey, model, systemPrompt, messages)
        onDelta(result)
        return result
    }
}

final class CopilotRunnerBox: @unchecked Sendable {
    var capturedPrompt: String?
    var isAvailable = true
    var result: Result<String, Error> = .success("ok")
}

struct MockCopilotRunner: CopilotCommandRunning {
    let box: CopilotRunnerBox

    func isAvailable(atPath path: String) -> Bool {
        box.isAvailable
    }

    func run(prompt: String, cliPath: String, timeout: TimeInterval) throws -> String {
        box.capturedPrompt = prompt
        return try box.result.get()
    }
}

struct MockCopilotStreamer: CopilotStreaming {
    let box: CopilotRunnerBox
    var result: Result<String, Error> = .success("copilot")

    func streamResponse(prompt: String, yoloMode: Bool, onDelta: @escaping @Sendable (String) -> Void) async throws -> String {
        box.capturedPrompt = yoloMode ? "/yolo \(prompt)" : prompt
        let output = try result.get()
        onDelta(output)
        return output
    }
}


final class StringArrayBox: @unchecked Sendable {
    var values: [String] = []
}

final class IntBox: @unchecked Sendable {
    var value: Int = 0
}

struct MockCopilotCLIRunner: CopilotCLIRunning {
    var isAvailable: Bool = true
    var stdout: String = ""
    var stderr: String = ""
    var exitCode: Int32 = 0

    func run(prompt: String, cliPath: String, timeout: TimeInterval) throws -> (stdout: String, stderr: String, exitCode: Int32) {
        (stdout, stderr, exitCode)
    }

    func cancel() {}
}
