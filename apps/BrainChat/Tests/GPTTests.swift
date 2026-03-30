import XCTest
@testable import BrainChatLib

final class GPTTests: XCTestCase {
    override func tearDown() {
        MockURLProtocol.reset()
        super.tearDown()
    }

    func testOpenAIAPIIntegrationRequest() throws {
        let api = OpenAIAPI(session: .mocked())
        let request = try api.makeRequest(
            apiKey: "sk-test",
            model: "gpt-4o",
            messages: [AIChatMessage(role: .user, content: "Hello GPT")]
        )

        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer sk-test")
        let body = try jsonBody(request)
        XCTAssertEqual(body["model"] as? String, "gpt-4o")
    }

    func testConversationContext() throws {
        let api = OpenAIAPI(session: .mocked())
        let request = try api.makeRequest(
            apiKey: "sk-test",
            model: "gpt-4o",
            messages: [
                AIChatMessage(role: .system, content: "System"),
                AIChatMessage(role: .user, content: "Question"),
                AIChatMessage(role: .assistant, content: "Answer")
            ]
        )

        let body = try jsonBody(request)
        let messages = try XCTUnwrap(body["messages"] as? [[String: String]])
        XCTAssertEqual(messages.count, 3)
        XCTAssertEqual(messages[1]["content"], "Question")
        XCTAssertEqual(messages[2]["role"], "assistant")
    }

    func testStreaming() async throws {
        let url = try XCTUnwrap(URL(string: "https://api.openai.com/v1/chat/completions"))
        MockURLProtocol.requestHandler = { _ in
            let data = Data((
                "data: {\"choices\":[{\"delta\":{\"content\":\"Hello \"}}]}\n" +
                "data: {\"choices\":[{\"delta\":{\"content\":\"world\"}}]}\n" +
                "data: [DONE]\n"
            ).utf8)
            return (httpResponse(url: url), data)
        }

        let api = OpenAIAPI(session: .mocked())
        let box = StringArrayBox()
        let response = try await api.streamResponse(
            apiKey: "sk-test",
            model: "gpt-4o",
            messages: [AIChatMessage(role: .user, content: "Hello")],
            onDelta: { box.values.append($0) }
        )

        XCTAssertEqual(box.values, ["Hello ", "world"])
        XCTAssertEqual(response, "Hello world")
    }

    func testMockResponsesForCI() async throws {
        let url = try XCTUnwrap(URL(string: "https://api.openai.com/v1/chat/completions"))
        MockURLProtocol.requestHandler = { _ in
            let data = Data("data: {\"choices\":[{\"delta\":{\"content\":\"mock response\"}}]}\n".utf8)
            return (httpResponse(url: url), data)
        }

        let api = OpenAIAPI(session: .mocked())
        let response = try await api.streamResponse(
            apiKey: "sk-test",
            model: "gpt-4o",
            messages: [AIChatMessage(role: .user, content: "Hi")],
            onDelta: { _ in }
        )

        XCTAssertEqual(response, "mock response")
    }
}
