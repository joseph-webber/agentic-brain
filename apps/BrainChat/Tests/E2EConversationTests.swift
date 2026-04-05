import XCTest
@testable import BrainChatLib

final class E2EConversationTests: E2EOrchestratedTestCase {
    func testFiveExchangeConversationFlow() {
        let recorder = beginScenario(named: "e2e-conversation")
        let app = SimulatedBrainChatApp(recorder: recorder)

        app.launch()

        XCTAssertTrue(app.launched)
        XCTAssertEqual(recorder.spokenLines.first, "G'day")

        let exchanges = [
            ("Hello Karen", "G'day, lovely to hear from you."),
            ("How are you today?", "I’m feeling sharp and ready to help."),
            ("What can you do?", "I can chat, code, and drive tasks step by step."),
            ("Tell me a quick joke", "Why do programmers mix up Halloween and Christmas? Because OCT 31 equals DEC 25."),
            ("Thanks Karen", "Always a pleasure.."),
        ]

        for (index, exchange) in exchanges.enumerated() {
            app.pressSpaceAndSpeak(exchange.0)
            XCTAssertEqual(app.displayedTranscript, exchange.0)
            XCTAssertEqual(app.history[(index * 2)].text, exchange.0)

            app.showThinking()
            XCTAssertTrue(app.isThinking)

            app.deliverAssistantResponse(exchange.1)
            XCTAssertFalse(app.isThinking)
            XCTAssertEqual(app.history[(index * 2) + 1].text, exchange.1)
        }

        XCTAssertEqual(app.history.count, 10)
        XCTAssertEqual(recorder.spokenLines.count, 6)
        XCTAssertTrue(recorder.logs.contains(where: { $0.contains("AI processes and shows thinking state") }))
    }
}
