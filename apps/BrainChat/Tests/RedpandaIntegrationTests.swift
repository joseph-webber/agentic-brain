import XCTest
@testable import BrainChatLib

// MARK: - Redpanda / Pandaproxy Integration Tests
// Brain Chat connects to Redpanda (Kafka-compatible) via Pandaproxy REST API.
// All LLM voice requests flow through:
//   brain.voice.input   → Python brain receives text, routes to LLM
//   brain.voice.response ← Python brain publishes the reply
// These tests use MockURLProtocol – no running Redpanda required.

final class VoiceEventCodingTests: XCTestCase {

    // MARK: - VoiceInputEvent encoding

    func testVoiceInputEventEncodesAllFields() throws {
        let ts = Date(timeIntervalSince1970: 1_700_000_000)
        let event = VoiceInputEvent(
            text: "What's the weather?",
            timestamp: ts,
            source: "brainchat",
            targetLLM: "claude",
            yoloMode: false
        )

        let data = try PandaproxyClient.makeEncoder().encode(event)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])

        XCTAssertEqual(json["text"]      as? String, "What's the weather?")
        XCTAssertEqual(json["source"]    as? String, "brainchat")
        XCTAssertEqual(json["targetLLM"] as? String, "claude")
        XCTAssertEqual(json["yoloMode"]  as? Bool,   false)
        XCTAssertEqual(json["timestamp"] as? String, "2023-11-14T22:13:20Z")
    }

    func testVoiceInputEventRoundTrip() throws {
        let original = VoiceInputEvent(
            text: "G'day Brain",
            timestamp: Date(timeIntervalSince1970: 0),
            source: "brainchat",
            targetLLM: "ollama",
            yoloMode: true
        )

        let data    = try PandaproxyClient.makeEncoder().encode(original)
        let decoded = try PandaproxyClient.makeDecoder().decode(VoiceInputEvent.self, from: data)

        XCTAssertEqual(decoded, original)
    }

    func testVoiceInputDefaultTimestampIsNow() {
        let before = Date()
        let event  = VoiceInputEvent(
            text: "test", source: "brainchat", targetLLM: "groq", yoloMode: false)
        let after  = Date()

        XCTAssertGreaterThanOrEqual(event.timestamp, before)
        XCTAssertLessThanOrEqual(event.timestamp, after)
    }

    func testYoloModeFlagEncodesTrue() throws {
        let event = VoiceInputEvent(
            text: "deploy to prod", source: "brainchat", targetLLM: "claude", yoloMode: true)
        let data  = try PandaproxyClient.makeEncoder().encode(event)
        let json  = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(json["yoloMode"] as? Bool, true)
    }

    // MARK: - VoiceResponseEvent decoding

    func testVoiceResponseEventDecodesFromJSON() throws {
        let json = """
        {"text":"G'day","provider":"claude","latencyMs":412,"success":true}
        """.data(using: .utf8)!

        let response = try PandaproxyClient.makeDecoder().decode(VoiceResponseEvent.self, from: json)
        XCTAssertEqual(response.text,      "G'day")
        XCTAssertEqual(response.provider,  "claude")
        XCTAssertEqual(response.latencyMs, 412)
        XCTAssertTrue(response.success)
    }

    func testVoiceResponseFailureDecodesSuccessFalse() throws {
        let json = """
        {"text":"Rate limit hit","provider":"groq","latencyMs":5001,"success":false}
        """.data(using: .utf8)!

        let response = try PandaproxyClient.makeDecoder().decode(VoiceResponseEvent.self, from: json)
        XCTAssertFalse(response.success)
        XCTAssertEqual(response.provider, "groq")
    }

    func testVoiceResponseRoundTrip() throws {
        let original = VoiceResponseEvent(
            text: "Hello!", provider: "ollama", latencyMs: 800, success: true)
        let data    = try PandaproxyClient.makeEncoder().encode(original)
        let decoded = try PandaproxyClient.makeDecoder().decode(VoiceResponseEvent.self, from: data)
        XCTAssertEqual(decoded, original)
    }
}

// MARK: - PandaproxyClient HTTP Layer Tests

final class PandaproxyClientHTTPTests: XCTestCase {

    override func tearDown() {
        MockURLProtocol.reset()
        super.tearDown()
    }

    // MARK: - publish

    func testPublishSendsCorrectTopicURL() async throws {
        var capturedURL: URL?

        MockURLProtocol.requestHandler = { request in
            capturedURL = request.url
            return (httpResponse(url: request.url!), Data())
        }

        let client = PandaproxyClient(session: .mocked())
        let event  = VoiceInputEvent(
            text: "hello", source: "brainchat", targetLLM: "ollama", yoloMode: false)

        try await client.publish(topic: "brain.voice.input", event: event)

        let url = try XCTUnwrap(capturedURL)
        XCTAssertTrue(url.absoluteString.hasSuffix("/topics/brain.voice.input"))
    }

    func testPublishUsesPostMethod() async throws {
        var capturedMethod: String?

        MockURLProtocol.requestHandler = { request in
            capturedMethod = request.httpMethod
            return (httpResponse(url: request.url!), Data())
        }

        let client = PandaproxyClient(session: .mocked())
        let event  = VoiceInputEvent(
            text: "test", source: "brainchat", targetLLM: "groq", yoloMode: false)

        try await client.publish(topic: "brain.voice.input", event: event)

        XCTAssertEqual(capturedMethod, "POST")
    }

    func testPublishSendsKafkaContentType() async throws {
        var capturedHeaders: [String: String] = [:]

        MockURLProtocol.requestHandler = { request in
            capturedHeaders = request.allHTTPHeaderFields ?? [:]
            return (httpResponse(url: request.url!), Data())
        }

        let client = PandaproxyClient(session: .mocked())
        let event  = VoiceInputEvent(
            text: "test", source: "brainchat", targetLLM: "claude", yoloMode: false)

        try await client.publish(topic: "brain.voice.input", event: event)

        XCTAssertEqual(capturedHeaders["Content-Type"],
                       "application/vnd.kafka.json.v2+json",
                       "Pandaproxy requires this Content-Type")
    }

    func testPublishWrapsEventInRecordsArray() async throws {
        var body: [String: Any] = [:]

        MockURLProtocol.requestHandler = { request in
            body = (try? jsonBody(request)) ?? [:]
            return (httpResponse(url: request.url!), Data())
        }

        let client = PandaproxyClient(session: .mocked())
        let event  = VoiceInputEvent(
            text: "test event", source: "brainchat", targetLLM: "gpt", yoloMode: false)

        try await client.publish(topic: "brain.voice.input", event: event)

        let records = try XCTUnwrap(body["records"] as? [[String: Any]])
        XCTAssertEqual(records.count, 1, "Pandaproxy expects exactly one record per publish")
        XCTAssertNotNil(records[0]["value"], "Record must have a 'value' key")
    }

    func testPublishThrowsOnHTTPError() async throws {
        MockURLProtocol.requestHandler = { request in
            (httpResponse(url: request.url!, statusCode: 500), Data("server error".utf8))
        }

        let client = PandaproxyClient(session: .mocked())
        let event  = VoiceInputEvent(
            text: "fail me", source: "brainchat", targetLLM: "claude", yoloMode: false)

        do {
            try await client.publish(topic: "brain.voice.input", event: event)
            XCTFail("Expected an error for 500 response")
        } catch let err as RedpandaBridgeError {
            guard case .unavailable(let msg) = err else {
                XCTFail("Expected .unavailable error, got \(err)"); return
            }
            XCTAssertTrue(msg.contains("500"))
        }
    }

    // MARK: - ensureConsumer

    func testEnsureConsumerCreatesConsumerThenSubscribes() async throws {
        var requestCount = 0
        var postPaths: [String] = []

        MockURLProtocol.requestHandler = { request in
            requestCount += 1
            let path = request.url?.path ?? ""
            if request.httpMethod == "POST" { postPaths.append(path) }

            // Consumer creation response
            if path.hasSuffix("/consumers/test-group") {
                let consumerURI = "\(request.url!.scheme!)://\(request.url!.host!)/consumers/test-group/instances/mock"
                let body = try! JSONSerialization.data(
                    withJSONObject: ["instance_id": "mock", "base_uri": consumerURI])
                return (httpResponse(url: request.url!), body)
            }

            // Subscribe response
            return (httpResponse(url: request.url!), Data())
        }

        let client = PandaproxyClient(session: .mocked())
        try await client.ensureConsumer(groupID: "test-group", topic: "brain.voice.response")

        XCTAssertGreaterThanOrEqual(requestCount, 2,
            "Must create consumer then subscribe: at least 2 HTTP calls")
    }

    func testEnsureConsumerIdempotentForSameGroup() async throws {
        var createCallCount = 0

        MockURLProtocol.requestHandler = { request in
            let path = request.url?.path ?? ""
            if path.hasSuffix("/consumers/idempotent-group") {
                createCallCount += 1
                let uri = "\(request.url!.scheme!)://\(request.url!.host!)/consumers/idempotent-group/instances/mock"
                let body = try! JSONSerialization.data(
                    withJSONObject: ["instance_id": "mock", "base_uri": uri])
                return (httpResponse(url: request.url!), body)
            }
            return (httpResponse(url: request.url!), Data())
        }

        let client = PandaproxyClient(session: .mocked())
        try await client.ensureConsumer(groupID: "idempotent-group", topic: "brain.voice.response")
        try await client.ensureConsumer(groupID: "idempotent-group", topic: "brain.voice.response")

        XCTAssertEqual(createCallCount, 1, "Consumer creation should only happen once per group")
    }
}

// MARK: - Pandaproxy Codec Tests

final class PandaproxyCodecTests: XCTestCase {

    func testMakeEncoderUsesISO8601DateStrategy() throws {
        let encoder = PandaproxyClient.makeEncoder()
        // Date(timeIntervalSinceReferenceDate: 0) = 2001-01-01T00:00:00Z (Apple epoch)
        // Date(timeIntervalSince1970: 978307200) = 2001-01-01T00:00:00Z
        let ts   = Date(timeIntervalSince1970: 978_307_200)
        let data = try encoder.encode(["ts": ts])
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(json["ts"] as? String, "2001-01-01T00:00:00Z")
    }

    func testMakeDecoderParsesISO8601DateString() throws {
        let decoder = PandaproxyClient.makeDecoder()
        let json    = #"{"ts":"2001-01-01T00:00:00Z"}"#.data(using: .utf8)!
        struct Wrapper: Decodable { let ts: Date }
        let result = try decoder.decode(Wrapper.self, from: json)
        XCTAssertEqual(result.ts, Date(timeIntervalSince1970: 978_307_200))
    }
}

// MARK: - RedpandaBridgeError Tests

final class RedpandaBridgeErrorTests: XCTestCase {

    func testInvalidBaseURLError() {
        let error = RedpandaBridgeError.invalidBaseURL("not-a-url")
        XCTAssertFalse(error.localizedDescription.isEmpty)
    }

    func testUnavailableErrorCarriesMessage() {
        let error = RedpandaBridgeError.unavailable("Pandaproxy is down")
        if case .unavailable(let msg) = error {
            XCTAssertEqual(msg, "Pandaproxy is down")
        } else {
            XCTFail("Expected .unavailable error")
        }
    }

    func testConsumerNotReadyError() {
        let error = RedpandaBridgeError.consumerNotReady
        XCTAssertFalse(error.localizedDescription.isEmpty)
    }

    func testCancelledError() {
        let error = RedpandaBridgeError.cancelled
        XCTAssertFalse(error.localizedDescription.isEmpty)
    }

    func testResponseFailedCarriesProviderAndMessage() {
        let error = RedpandaBridgeError.responseFailed(provider: "claude", message: "Overloaded")
        if case .responseFailed(let provider, let msg) = error {
            XCTAssertEqual(provider, "claude")
            XCTAssertEqual(msg, "Overloaded")
        } else {
            XCTFail("Expected .responseFailed")
        }
    }
}

// MARK: - Topic Name Tests

final class RedpandaTopicNamingTests: XCTestCase {

    func testVoiceInputTopicIsCorrect() {
        let topic = "brain.voice.input"
        XCTAssertTrue(topic.hasPrefix("brain."), "Topics must be namespaced under 'brain.'")
        XCTAssertTrue(topic.hasSuffix(".input"), "Input topic must end in '.input'")
    }

    func testVoiceResponseTopicIsCorrect() {
        let topic = "brain.voice.response"
        XCTAssertTrue(topic.hasPrefix("brain."),    "Topics must be namespaced under 'brain.'")
        XCTAssertTrue(topic.hasSuffix(".response"), "Response topic must end in '.response'")
    }

    func testTopicsFollowDotNotationConvention() {
        let topics = ["brain.voice.input", "brain.voice.response",
                      "brain.llm.response.fast", "brain.llm.response.deep"]
        for topic in topics {
            XCTAssertFalse(topic.contains("_"),
                           "Topic '\(topic)' must use dots not underscores")
            XCTAssertFalse(topic.hasPrefix("."),  "Topic must not start with a dot")
            XCTAssertFalse(topic.hasSuffix("."),  "Topic must not end with a dot")
        }
    }

    func testConsumerGroupIDFollowsNamingConvention() {
        let groupID = "brainchat-swift"
        XCTAssertFalse(groupID.isEmpty)
        XCTAssertTrue(groupID.hasPrefix("brainchat"),
                      "Consumer groups must be prefixed with 'brainchat'")
    }
}
