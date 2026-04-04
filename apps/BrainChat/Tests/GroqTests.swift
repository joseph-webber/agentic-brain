import XCTest
@testable import BrainChatLib

final class GroqTests: XCTestCase {
    override func tearDown() {
        MockURLProtocol.reset()
        super.tearDown()
    }

    func testGroqAPIStreamsOpenAICompatibleChunks() async throws {
        let url = try XCTUnwrap(URL(string: "https://api.groq.com/openai/v1/chat/completions"))
        MockURLProtocol.requestHandler = { request in
            XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer groq-test")
            let body = try jsonBody(request)
            XCTAssertEqual(body["model"] as? String, "llama-3.1-8b-instant")
            XCTAssertEqual(body["stream"] as? Bool, true)

            let data = Data((
                "data: {\"choices\":[{\"delta\":{\"content\":\"hello\"}}]}\n" +
                "data: {\"choices\":[{\"delta\":{\"content\":\" world\"}}]}\n" +
                "data: [DONE]\n"
            ).utf8)
            return (httpResponse(url: url), data)
        }

        let client = GroqClient(session: .mocked())
        let response = try await client.streamResponse(
            apiKey: "groq-test",
            model: "llama-3.1-8b-instant",
            messages: [AIChatMessage(role: .user, content: "Hi")],
            onDelta: { _ in }
        )

        XCTAssertEqual(response, "hello world")
    }

    func testGroqDefaultsToInstantModelWhenBlank() async throws {
        let url = try XCTUnwrap(URL(string: "https://api.groq.com/openai/v1/chat/completions"))
        MockURLProtocol.requestHandler = { request in
            let body = try jsonBody(request)
            XCTAssertEqual(body["model"] as? String, "llama-3.1-8b-instant")
            return (httpResponse(url: url), Data("data: {\"choices\":[{\"delta\":{\"content\":\"ok\"}}]}\ndata: [DONE]\n".utf8))
        }

        let client = GroqClient(session: .mocked())
        let response = try await client.streamResponse(
            apiKey: "groq-test",
            model: "   ",
            messages: [AIChatMessage(role: .user, content: "Hi")],
            onDelta: { _ in }
        )

        XCTAssertEqual(response, "ok")
    }
}
