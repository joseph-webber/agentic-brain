import XCTest
@testable import BrainChatLib

final class RedpandaBridgeTests: XCTestCase {
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
              "text": "G'day Joseph",
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
            text: "G'day Joseph",
            provider: "claude",
            latencyMs: 412,
            success: true
        ))
    }
}
