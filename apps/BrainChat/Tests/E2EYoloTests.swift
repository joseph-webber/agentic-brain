import XCTest
@testable import BrainChatLib

final class E2EYoloTests: E2EOrchestratedTestCase {
    func testYoloModeAutonomousRestAPIFlow() throws {
        let recorder = beginScenario(named: "e2e-yolo")
        let app = SimulatedBrainChatApp(recorder: recorder)

        app.launch()
        app.pressSpaceAndSpeak("Enable yolo mode")
        app.enableYoloMode()

        XCTAssertTrue(app.yoloModeEnabled)
        XCTAssertTrue(recorder.spokenLines.contains(where: { $0.contains("YOLO mode enabled") }))

        app.pressSpaceAndSpeak("Create a REST API")
        let createdFiles = try app.createRestAPIProject()

        XCTAssertEqual(createdFiles.count, 3)
        XCTAssertTrue(createdFiles.allSatisfy { FileManager.default.fileExists(atPath: $0.path) })
        XCTAssertEqual(app.actionAnnouncements.count, 3)
        XCTAssertTrue(app.actionAnnouncements.contains("Creating FastAPI entrypoint"))
        XCTAssertTrue(app.actionAnnouncements.contains("Creating API routes"))
        XCTAssertTrue(app.actionAnnouncements.contains("Saving dependencies"))

        app.pressSpaceAndSpeak("Yolo off")
        app.disableYoloMode()
        XCTAssertFalse(app.yoloModeEnabled)
        XCTAssertEqual(recorder.spokenLines.last, "YOLO mode off.")
    }
}
