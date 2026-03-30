import XCTest
@testable import BrainChatLib

final class OllamaTests: XCTestCase {
    override func tearDown() {
        MockURLProtocol.reset()
        super.tearDown()
    }

    func testConnectionToLocalhost11434() throws {
        let api = OllamaAPI(session: .mocked())
        let url = try XCTUnwrap(URL(string: "http://localhost:11434/api/chat"))
        let request = try api.makeRequest(url: url, model: "llama3.2:3b", messages: [AIChatMessage(role: .user, content: "Hello")])
        XCTAssertEqual(request.url?.host, "localhost")
        XCTAssertEqual(request.url?.port, 11434)
        XCTAssertEqual(request.url?.path, "/api/chat")
    }

    func testPromptResponseCycle() async throws {
        let url = try XCTUnwrap(URL(string: "http://localhost:11434/api/chat"))
        let api = OllamaAPI(session: .mocked())
        let request = try api.makeRequest(url: url, model: "llama3.2:3b", messages: [AIChatMessage(role: .user, content: "Hello")])
        let body = try jsonBody(request)
        XCTAssertEqual(body["model"] as? String, "llama3.2:3b")
        let messages = try XCTUnwrap(body["messages"] as? [[String: String]])
        XCTAssertEqual(messages.last?["content"], "Hello")
        MockURLProtocol.requestHandler = { _ in
            let data = Data("{\"message\":{\"content\":\"Hi Joseph\"},\"done\":true}\n".utf8)
            return (httpResponse(url: url), data)
        }
        let response = try await api.streamResponse(endpoint: url.absoluteString, model: "llama3.2:3b", messages: [AIChatMessage(role: .user, content: "Hello")], onDelta: { _ in })
        XCTAssertEqual(response, "Hi Joseph")
    }

    func testStreamingResponses() async throws {
        let url = try XCTUnwrap(URL(string: "http://localhost:11434/api/chat"))
        MockURLProtocol.requestHandler = { _ in
            let data = Data(("{\"message\":{\"content\":\"Hello \"},\"done\":false}\n" + "{\"message\":{\"content\":\"world\"},\"done\":false}\n" + "{\"done\":true}\n").utf8)
            return (httpResponse(url: url), data)
        }
        let api = OllamaAPI(session: .mocked())
        let box = StringArrayBox()
        let response = try await api.streamResponse(endpoint: url.absoluteString, model: "llama3.2:3b", messages: [AIChatMessage(role: .user, content: "Hello")], onDelta: { box.values.append($0) })
        XCTAssertEqual(box.values, ["Hello ", "world"])
        XCTAssertEqual(response, "Hello world")
    }

    func testTimeoutHandling() async {
        MockURLProtocol.error = URLError(.timedOut)
        let api = OllamaAPI(session: .mocked())
        do {
            _ = try await api.streamResponse(endpoint: "http://localhost:11434/api/chat", model: "llama3.2:3b", messages: [AIChatMessage(role: .user, content: "Hello")], onDelta: { _ in })
            XCTFail("Expected timeout")
        } catch {
            XCTAssertTrue(error is URLError)
            XCTAssertEqual((error as? URLError)?.code, .timedOut)
        }
    }

    func testWhenOllamaNotRunning() async {
        MockURLProtocol.error = URLError(.cannotConnectToHost)
        let api = OllamaAPI(session: .mocked())
        do {
            _ = try await api.streamResponse(endpoint: "http://localhost:11434/api/chat", model: "llama3.2:3b", messages: [AIChatMessage(role: .user, content: "Hello")], onDelta: { _ in })
            XCTFail("Expected connection error")
        } catch {
            XCTAssertEqual((error as? URLError)?.code, .cannotConnectToHost)
        }
    }
}
