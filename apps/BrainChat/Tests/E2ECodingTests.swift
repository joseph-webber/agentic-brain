import XCTest
@testable import BrainChatLib

final class E2ECodingTests: E2EOrchestratedTestCase {
    func testCodingFlowRoutesToCopilotAndRunsCode() throws {
        let recorder = beginScenario(named: "e2e-coding")
        let app = SimulatedBrainChatApp(recorder: recorder)

        app.launch()

        let prompt = "Create a Python hello world"
        app.pressSpaceAndSpeak(prompt)

        let route = app.routeCodingPrompt(prompt)
        XCTAssertEqual(route, .copilot)

        let code = app.generateCode(for: prompt)
        XCTAssertTrue(code.contains("Hello, World!"))

        app.readCodeAloud(code)
        XCTAssertTrue(recorder.spokenLines.contains(where: { $0.contains("Here is the code.") }))

        let fileURL = try app.saveCode(code, named: "hello_world.py")
        XCTAssertTrue(FileManager.default.fileExists(atPath: fileURL.path))

        let output = try app.runPythonFile(fileURL)
        XCTAssertEqual(output, "Hello, World!")
        XCTAssertTrue(recorder.spokenLines.contains(where: { $0.contains("Output: Hello, World!") }))
    }
}
