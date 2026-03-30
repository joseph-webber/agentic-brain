import XCTest
@testable import BrainChatLib

final class GeminiTests: XCTestCase {
    override func tearDown() {
        MockURLProtocol.reset()
        super.tearDown()
    }

    func testGoogleAPI() async throws {
        let expectedURL = try XCTUnwrap(URL(string: "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:streamGenerateContent?alt=sse&key=AIza-test"))
        MockURLProtocol.requestHandler = { request in
            XCTAssertEqual(request.url, expectedURL)
            let data = Data("data: {\"candidates\":[{\"content\":{\"parts\":[{\"text\":\"gemini reply\"}]}}]}\n".utf8)
            return (httpResponse(url: expectedURL), data)
        }

        let client = GeminiClient(session: .mocked())
        let response = try await client.streamResponse(
            apiKey: "AIza-test",
            model: "gemini-2.5-flash",
            systemPrompt: "Be concise",
            messages: [AIChatMessage(role: .user, content: "Hi")],
            onDelta: { _ in }
        )

        XCTAssertEqual(response, "gemini reply")
    }

    func testMockForCI() async throws {
        let url = try XCTUnwrap(URL(string: "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:streamGenerateContent?alt=sse&key=AIza-test"))
        MockURLProtocol.requestHandler = { _ in
            let data = Data("data: {\"candidates\":[{\"content\":{\"parts\":[{\"text\":\"mock gemini\"}]}}]}\n".utf8)
            return (httpResponse(url: url), data)
        }

        let client = GeminiClient(session: .mocked())
        let response = try await client.streamResponse(
            apiKey: "AIza-test",
            model: "gemini-2.5-flash",
            systemPrompt: "Be concise",
            messages: [AIChatMessage(role: .user, content: "Hi")],
            onDelta: { _ in }
        )

        XCTAssertEqual(response, "mock gemini")
    }
}
