import XCTest
@testable import BrainChatLib

final class RedpandaBridgeTests: XCTestCase {
    override func tearDown() {
        MockURLProtocol.reset()
        super.tearDown()
    }

    func testVoiceInputEventRoundTripUsesISO8601Timestamp() throws {
        let timestamp = Date(timeIntervalSince1970: 1_700_000_000)
        let event = VoiceInputEvent(
            text: "Hello from Brain Chat",
            timestamp: timestamp,
            source: "brainchat",
            targetLLM: "claude",
            yoloMode: true
        )

        let data = try PandaproxyClient.makeEncoder().encode(event)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        XCTAssertEqual(json?["text"] as? String, "Hello from Brain Chat")
        XCTAssertEqual(json?["source"] as? String, "brainchat")
        XCTAssertEqual(json?["targetLLM"] as? String, "claude")
        XCTAssertEqual(json?["yoloMode"] as? Bool, true)
        XCTAssertEqual(json?["timestamp"] as? String, "2023-11-14T22:13:20Z")

        let decoded = try PandaproxyClient.makeDecoder().decode(VoiceInputEvent.self, from: data)
        XCTAssertEqual(decoded, event)
    }

    func testVoiceResponseRecordDecodingFromPandaproxyPayload() throws {
        let payload = """
        [
          {
            "topic": "brain.voice.response",
            "key": null,
            "value": {
              "text": "G'day",
              "provider": "claude",
              "latencyMs": 412,
              "success": true
            },
            "partition": 0,
            "offset": 12
          }
        ]
        """.data(using: .utf8)!

        let records = try PandaproxyClient.decodeRecords(from: payload, as: VoiceResponseEvent.self)

        XCTAssertEqual(records.count, 1)
        XCTAssertEqual(records[0].topic, "brain.voice.response")
        XCTAssertEqual(records[0].partition, 0)
        XCTAssertEqual(records[0].offset, 12)
        XCTAssertEqual(records[0].value, VoiceResponseEvent(
            text: "G'day",
            provider: "claude",
            latencyMs: 412,
            success: true
        ))
    }

    func testPublishFastRequestPublishesInstantPriorityAndLayers() async throws {
        let expectedURL = URL(string: "http://localhost:8082/topics/brain.llm.request")!
        MockURLProtocol.requestHandler = { request in
            XCTAssertEqual(request.url, expectedURL)
            XCTAssertEqual(request.httpMethod, "POST")

            let body = try jsonBody(request)
            let records = try XCTUnwrap(body["records"] as? [[String: Any]])
            let value = try XCTUnwrap(records.first?["value"] as? [String: Any])

            XCTAssertEqual(value["prompt"] as? String, "Ship a fast answer")
            XCTAssertEqual(value["priority"] as? String, "instant")
            XCTAssertEqual(value["layers"] as? [String], ["fast", "deep"])
            XCTAssertEqual(value["source"] as? String, "brainchat")
            XCTAssertNotNil(value["request_id"] as? String)
            XCTAssertNotNil(value["timestamp"] as? String)

            return (httpResponse(url: expectedURL), Data())
        }

        let client = PandaproxyClient(session: .mocked())
        try await client.publishFastRequest("Ship a fast answer")
    }

    func testSubscribeToResponsesMergesFastAndDeepTopicsInArrivalOrder() async throws {
        let baseURI = URL(string: "http://localhost:8082/consumers/brainchat-llm-test/instances/mock")!
        let pollCount = IntBox()
        let subscribedTopics = StringArrayBox()

        MockURLProtocol.requestHandler = { request in
            let url = try XCTUnwrap(request.url)

            switch (request.httpMethod, url.path) {
            case ("POST", "/consumers/brainchat-llm-test"):
                let body = [
                    "instance_id": "mock",
                    "base_uri": baseURI.absoluteString
                ]
                let data = try JSONSerialization.data(withJSONObject: body)
                return (httpResponse(url: url), data)

            case ("POST", "/consumers/brainchat-llm-test/instances/mock/subscription"):
                let body = try jsonBody(request)
                let topics = try XCTUnwrap(body["topics"] as? [String])
                subscribedTopics.values.append(contentsOf: topics)
                return (httpResponse(url: url, statusCode: 204), Data())

            case ("GET", "/consumers/brainchat-llm-test/instances/mock/records"):
                pollCount.value += 1
                let payload: Data
                if pollCount.value == 1 {
                    payload = """
                    [
                      {
                        "topic": "brain.llm.response.fast",
                        "key": null,
                        "value": {
                          "request_id": "req-fast",
                          "text": "Fast path ready",
                          "provider": "groq",
                          "latency_ms": 88,
                          "success": true,
                          "timestamp": "2026-04-04T10:15:00Z"
                        },
                        "partition": 0,
                        "offset": 12
                      },
                      {
                        "topic": "brain.llm.response.deep",
                        "key": null,
                        "value": {
                          "request_id": "req-fast",
                          "answer": "Deep analysis complete",
                          "provider": "claude",
                          "latency_ms": 640,
                          "status": "completed",
                          "timestamp": "2026-04-04T10:15:01Z"
                        },
                        "partition": 0,
                        "offset": 13
                      }
                    ]
                    """.data(using: .utf8)!
                } else {
                    payload = Data("[]".utf8)
                }
                return (httpResponse(url: url), payload)

            case ("DELETE", "/consumers/brainchat-llm-test/instances/mock"):
                return (httpResponse(url: url, statusCode: 204), Data())

            default:
                XCTFail("Unexpected request: \(request.httpMethod ?? "nil") \(url.absoluteString)")
                return (httpResponse(url: url, statusCode: 500), Data())
            }
        }

        let client = PandaproxyClient(session: .mocked())
        let stream = await client.subscribeToResponses(groupID: "brainchat-llm-test")
        var iterator = stream.makeAsyncIterator()

        let first = try XCTUnwrap(await iterator.next())
        let second = try XCTUnwrap(await iterator.next())

        XCTAssertEqual(Set(subscribedTopics.values), Set([
            "brain.llm.response.fast",
            "brain.llm.response.deep",
            "brain.llm.response.consensus"
        ]))

        XCTAssertEqual(first.requestID, "req-fast")
        XCTAssertEqual(first.provider, "groq")
        XCTAssertEqual(first.layer, .fast)
        XCTAssertEqual(first.sourceTopic, "brain.llm.response.fast")
        XCTAssertEqual(first.text, "Fast path ready")

        XCTAssertEqual(second.requestID, "req-fast")
        XCTAssertEqual(second.provider, "claude")
        XCTAssertEqual(second.layer, .deep)
        XCTAssertEqual(second.sourceTopic, "brain.llm.response.deep")
        XCTAssertEqual(second.text, "Deep analysis complete")
    }
}
