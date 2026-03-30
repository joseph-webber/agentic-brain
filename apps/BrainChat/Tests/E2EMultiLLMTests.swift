import XCTest
@testable import BrainChatLib

final class E2EMultiLLMTests: E2EOrchestratedTestCase {
    func testProviderSwitchingWorksAcrossAllBackends() {
        let recorder = beginScenario(named: "e2e-multi-llm")
        let app = SimulatedBrainChatApp(recorder: recorder)

        app.launch()

        for provider in E2ELLMProvider.allCases {
            app.switchProvider(to: provider)
            XCTAssertEqual(app.provider, provider)

            app.pressSpaceAndSpeak("Test \(provider.rawValue)")
            let response = app.providerResponse(to: "Test \(provider.rawValue)")

            XCTAssertTrue(response.contains(provider.rawValue))
            XCTAssertEqual(app.history.last?.text, response)
        }

        XCTAssertEqual(app.history.count, E2ELLMProvider.allCases.count * 2)
        XCTAssertEqual(recorder.spokenLines.filter { $0.contains("handled:") }.count, E2ELLMProvider.allCases.count)
    }
}
