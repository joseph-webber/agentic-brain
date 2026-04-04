import XCTest
@testable import BrainChatLib

final class YoloTests: XCTestCase {
    func testYoloCommandEventEncodesExpectedPayload() throws {
        let timestamp = Date(timeIntervalSince1970: 1_700_000_100)
        let event = YoloCommandEvent(
            requestID: "req-123",
            sessionID: "session-456",
            prompt: "Delete stale build artifacts",
            timestamp: timestamp,
            source: "brainchat",
            targetLLM: "Copilot",
            dangerous: true,
            confirmationReason: "This request sounds destructive."
        )

        let data = try PandaproxyClient.makeEncoder().encode(event)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])

        XCTAssertEqual(json["requestID"] as? String, "req-123")
        XCTAssertEqual(json["sessionID"] as? String, "session-456")
        XCTAssertEqual(json["prompt"] as? String, "Delete stale build artifacts")
        XCTAssertEqual(json["text"] as? String, "Delete stale build artifacts")
        XCTAssertEqual(json["targetLLM"] as? String, "Copilot")
        XCTAssertEqual(json["dangerous"] as? Bool, true)
        XCTAssertEqual(json["confirmationReason"] as? String, "This request sounds destructive.")
        XCTAssertEqual(json["mode"] as? String, "yolo")
        XCTAssertEqual(json["timestamp"] as? String, "2023-11-14T22:15:00Z")
    }

    func testAgentResultEventDecodesFlexibleBrainPayload() throws {
        let payload = """
        {
          "request_id": "req-123",
          "session_id": "session-456",
          "output": "Created API routes successfully",
          "agent_name": "python-yolo-processor",
          "status": "completed",
          "success": true,
          "timestamp": "2026-04-04T10:15:00Z"
        }
        """.data(using: .utf8)!

        let result = try PandaproxyClient.makeDecoder().decode(AgentResultEvent.self, from: payload)

        XCTAssertEqual(result.requestID, "req-123")
        XCTAssertEqual(result.sessionID, "session-456")
        XCTAssertEqual(result.text, "Created API routes successfully")
        XCTAssertEqual(result.agent, "python-yolo-processor")
        XCTAssertEqual(result.status, "completed")
        XCTAssertTrue(result.success)
        XCTAssertEqual(result.chatSummary, "✅ python-yolo-processor: Created API routes successfully")
    }
}
