import XCTest
@testable import BrainChatLib

final class GrokTests: XCTestCase {
    override func tearDown() {
        MockURLProtocol.reset()
        super.tearDown()
    }

    func testXAIAPI() async throws {
        let url = try XCTUnwrap(URL(string: "https://api.x.ai/v1/chat/completions"))
        MockURLProtocol.requestHandler = { request in
            XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer xai-test")
            let data = Data((
                "data: {\"choices\":[{\"delta\":{\"content\":\"hello\"}}]}\n" +
                "data: [DONE]\n"
            ).utf8)
            return (httpResponse(url: url), data)
        }

        let client = GrokClient(session: .mocked())
        let response = try await client.streamResponse(
            apiKey: "xai-test",
            model: "grok-3-latest",
            messages: [AIChatMessage(role: .user, content: "Hi")],
            onDelta: { _ in }
        )

        XCTAssertEqual(response, "hello")
    }

    func testMockForCI() async throws {
        let url = try XCTUnwrap(URL(string: "https://api.x.ai/v1/chat/completions"))
        MockURLProtocol.requestHandler = { _ in
            let data = Data("data: {\"choices\":[{\"delta\":{\"content\":\"mock grok\"}}]}\n".utf8)
            return (httpResponse(url: url), data)
        }

        let client = GrokClient(session: .mocked())
        let response = try await client.streamResponse(
            apiKey: "xai-test",
            model: "grok-3-latest",
            messages: [AIChatMessage(role: .user, content: "Hi")],
            onDelta: { _ in }
        )

        XCTAssertEqual(response, "mock grok")
    }
}
