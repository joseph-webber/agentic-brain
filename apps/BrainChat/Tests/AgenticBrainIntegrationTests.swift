import XCTest
@testable import BrainChatLib

final class AgenticBrainIntegrationTests: XCTestCase {

    override func tearDown() {
        MockURLProtocol.reset()
        super.tearDown()
    }

    func testADLLoaderMapsTechnicalPersonaToDeveloperProfile() {
        let adl = """
        application AgenticBrain {
          persona technical
        }

        llm Primary {
          systemPrompt "Ship complete code."
        }

        rag MainRAG {
          vectorStore neo4j
        }

        modes {
          routing smart
          fallback ["ollama", "openai", "groq"]
        }
        """

        let summary = ADLConfigurationLoader.parse(adl)
        XCTAssertEqual(summary.profile, .developer)
        XCTAssertEqual(summary.mode, .hybrid)
        XCTAssertEqual(summary.fallbackProviders, [.ollama, .gpt, .groq])
        XCTAssertEqual(summary.systemPrompt, "Ship complete code.")
        XCTAssertTrue(summary.graphRAGEnabled)
    }

    func testBackendChatAddsAuthHeadersAndGraphRAGMetadata() async throws {
        let headersBox = DictionaryBox<String, String>()
        let bodyBox = DictionaryBox<String, Any>()

        MockURLProtocol.requestHandler = { request in
            headersBox.value = request.allHTTPHeaderFields ?? [:]
            bodyBox.value = try jsonBody(request)
            let payload = """
            {"response":"Backend hello","session_id":"sess-1","message_id":"msg-1"}
            """.data(using: .utf8)!
            return (httpResponse(url: request.url!), payload)
        }

        let backend = AgenticBrainBackendClient(session: .mocked())
        let configuration = AgenticBrainBackendConfiguration(
            enabled: true,
            restBaseURL: "http://localhost:8000",
            webSocketURL: "",
            apiKey: "brain-key",
            bearerToken: "jwt-token",
            sessionID: "sess-1",
            userID: "joseph",
            mode: .hybrid,
            graphRAGEnabled: true,
            graphRAGScope: "workspace"
        )

        let response = try await backend.chat(
            prompt: "hello",
            configuration: configuration,
            provider: .claude,
            model: "claude-sonnet",
            metadata: [
                "brainchat_profile": "developer",
                "rag": [
                    "enabled": true,
                    "scope": "workspace",
                ],
            ]
        )

        XCTAssertEqual(response.response, "Backend hello")
        XCTAssertEqual(headersBox.value["X-API-Key"], "brain-key")
        XCTAssertEqual(headersBox.value["Authorization"], "Bearer jwt-token")
        XCTAssertEqual(bodyBox.value["message"] as? String, "hello")
        XCTAssertEqual(bodyBox.value["session_id"] as? String, "sess-1")
        let metadata = try XCTUnwrap(bodyBox.value["metadata"] as? [String: Any])
        let rag = try XCTUnwrap(metadata["rag"] as? [String: Any])
        XCTAssertEqual(rag["scope"] as? String, "workspace")
    }

    @MainActor
    func testRouterUsesBackendBeforeDirectProviders() async {
        let backend = MockAgenticBrainBackend(result: .success("backend answer"))
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "claude" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "gpt" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ollama" },
            groqClient: MockGroqStreamer { _, _, _ in "groq" },
            grokClient: MockGrokStreamer { _, _, _ in "grok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "gemini" },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox()),
            backendClient: backend
        )

        let response = await router.streamReply(
            history: [ChatMessage(role: .user, content: "hello backend")],
            configuration: makeConfig(
                provider: .claude,
                backend: AgenticBrainBackendConfiguration(
                    enabled: true,
                    restBaseURL: "http://localhost:8000",
                    webSocketURL: "",
                    apiKey: "",
                    bearerToken: "",
                    sessionID: "sess-2",
                    userID: "joseph",
                    mode: .hybrid,
                    graphRAGEnabled: true,
                    graphRAGScope: "session"
                )
            ),
            onEvent: { _ in }
        )

        XCTAssertEqual(response, "backend answer")
        XCTAssertEqual(router.activeProviderName, "Agentic Brain API")
    }

    @MainActor
    func testRouterFallsBackToDirectProvidersWhenBackendFails() async {
        let backend = MockAgenticBrainBackend(result: .failure(AIServiceError.httpStatus(503, "down")))
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "claude fallback" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "gpt" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ollama" },
            groqClient: MockGroqStreamer { _, _, _ in "groq" },
            grokClient: MockGrokStreamer { _, _, _ in "grok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "gemini" },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox()),
            backendClient: backend
        )

        let response = await router.streamReply(
            history: [ChatMessage(role: .user, content: "hello backend")],
            configuration: makeConfig(
                provider: .claude,
                fallbackProviders: [.claude, .gpt, .ollama],
                backend: AgenticBrainBackendConfiguration(
                    enabled: true,
                    restBaseURL: "http://localhost:8000",
                    webSocketURL: "",
                    apiKey: "",
                    bearerToken: "",
                    sessionID: "sess-3",
                    userID: "joseph",
                    mode: .hybrid,
                    graphRAGEnabled: false,
                    graphRAGScope: "session"
                ),
                groqAPIKey: ""
            ),
            onEvent: { _ in }
        )

        XCTAssertEqual(response, "claude fallback")
        XCTAssertEqual(router.statusMessage, "Ready")
    }

    func testRedpandaBridgeRecoversAfterPollFailure() async throws {
        let baseURL = URL(string: "http://localhost:8082")!
        let pollCount = IntBox()

        MockURLProtocol.requestHandler = { request in
            let path = request.url?.path ?? ""
            switch (request.httpMethod ?? "GET", path) {
            case ("POST", "/consumers/brainchat-swift"):
                let consumerURI = "\(baseURL.absoluteString)/consumers/brainchat-swift/instances/mock"
                let body = try JSONSerialization.data(withJSONObject: ["instance_id": "mock", "base_uri": consumerURI])
                return (httpResponse(url: request.url!), body)
            case ("POST", "/consumers/brainchat-swift/instances/mock/subscription"):
                return (httpResponse(url: request.url!), Data())
            case ("DELETE", "/consumers/brainchat-swift/instances/mock"):
                return (httpResponse(url: request.url!, statusCode: 204), Data())
            case ("GET", "/consumers/brainchat-swift/instances/mock/records"):
                pollCount.value += 1
                if pollCount.value == 1 {
                    return (httpResponse(url: request.url!, statusCode: 503), Data("offline".utf8))
                }

                let payload = try JSONSerialization.data(withJSONObject: [[
                    "topic": "brain.voice.response",
                    "partition": 0,
                    "offset": pollCount.value,
                    "value": [
                        "text": "Recovered",
                        "provider": "claude",
                        "latencyMs": 120,
                        "success": true,
                    ],
                ]])
                return (httpResponse(url: request.url!), payload)
            default:
                return (httpResponse(url: request.url!), Data("[]".utf8))
            }
        }

        let client = PandaproxyClient(baseURL: baseURL, session: .mocked())
        let bridge = RedpandaBridge(client: client)
        let expectation = expectation(description: "Recovered after retry")

        try await bridge.startListening { response in
            if response.text == "Recovered" {
                expectation.fulfill()
            }
        }

        await fulfillment(of: [expectation], timeout: 3.0)
        await bridge.stop()
        XCTAssertGreaterThanOrEqual(pollCount.value, 2)
    }
}

final class DictionaryBox<Key: Hashable, Value>: @unchecked Sendable {
    var value: [Key: Value] = [:]
}
