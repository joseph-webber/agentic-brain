import XCTest
@testable import BrainChatLib

final class ClaudeTests: XCTestCase {
    override func tearDown() {
        MockURLProtocol.reset()
        super.tearDown()
    }

    func testAPIAuthenticationAndMessageFormatting() throws {
        let api = ClaudeAPI(session: .mocked())
        let request = try api.makeRequest(
            apiKey: "sk-ant-test",
            model: "claude-sonnet-4-20250514",
            systemPrompt: "Be concise",
            messages: [
                AIChatMessage(role: .system, content: "ignore"),
                AIChatMessage(role: .user, content: "Hello Claude")
            ]
        )

        XCTAssertEqual(request.value(forHTTPHeaderField: "x-api-key"), "sk-ant-test")
        XCTAssertEqual(request.value(forHTTPHeaderField: "anthropic-version"), "2023-06-01")
        let body = try jsonBody(request)
        XCTAssertEqual(body["system"] as? String, "Be concise")
        XCTAssertEqual(body["model"] as? String, "claude-sonnet-4-20250514")
        let messages = try XCTUnwrap(body["messages"] as? [[String: Any]])
        XCTAssertEqual(messages.count, 1)
        XCTAssertEqual(messages.first?["role"] as? String, "user")
    }

    func testResponseParsing() async throws {
        let url = try XCTUnwrap(URL(string: "https://api.anthropic.com/v1/messages"))
        MockURLProtocol.requestHandler = { _ in
            let data = Data((
                "data: {\"type\":\"content_block_delta\",\"delta\":{\"text\":\"Hello \"}}\n" +
                "data: {\"type\":\"content_block_delta\",\"delta\":{\"text\":\"Joseph\"}}\n"
            ).utf8)
            return (httpResponse(url: url), data)
        }

        let api = ClaudeAPI(session: .mocked())
        let box = StringArrayBox()
        let response = try await api.streamResponse(
            apiKey: "sk-ant-test",
            model: "claude-sonnet-4-20250514",
            systemPrompt: "Be concise",
            messages: [AIChatMessage(role: .user, content: "Hello")],
            onDelta: { box.values.append($0) }
        )

        XCTAssertEqual(box.values, ["Hello ", "Joseph"])
        XCTAssertEqual(response, "Hello Joseph")
    }

    func testRateLimitHandling() async {
        let url = try! XCTUnwrap(URL(string: "https://api.anthropic.com/v1/messages"))
        MockURLProtocol.requestHandler = { _ in
            let data = Data("{\"error\":{\"message\":\"rate limit exceeded\"}}".utf8)
            return (httpResponse(url: url, statusCode: 429), data)
        }

        let api = ClaudeAPI(session: .mocked())
        do {
            _ = try await api.streamResponse(
                apiKey: "sk-ant-test",
                model: "claude-sonnet-4-20250514",
                systemPrompt: "Be concise",
                messages: [AIChatMessage(role: .user, content: "Hello")],
                onDelta: { _ in }
            )
            XCTFail("Expected rate limit error")
        } catch {
            if case let AIServiceError.httpStatus(code, message) = error {
                XCTAssertEqual(code, 429)
                XCTAssertEqual(message, "rate limit exceeded")
            } else {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    func testCIUsesMockedSessionNoRealCalls() async throws {
        let url = try XCTUnwrap(URL(string: "https://api.anthropic.com/v1/messages"))
        let count = IntBox()
        MockURLProtocol.requestHandler = { _ in
            count.value += 1
            let data = Data("data: {\"delta\":{\"text\":\"mocked\"}}\n".utf8)
            return (httpResponse(url: url), data)
        }

        let api = ClaudeAPI(session: .mocked())
        _ = try await api.streamResponse(
            apiKey: "sk-ant-test",
            model: "claude-sonnet-4-20250514",
            systemPrompt: "Be concise",
            messages: [AIChatMessage(role: .user, content: "Hello")],
            onDelta: { _ in }
        )

        XCTAssertEqual(count.value, 1)
    }
}
