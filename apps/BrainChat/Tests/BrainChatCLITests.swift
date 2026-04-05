import XCTest
@testable import BrainChatLib

final class BrainChatCLITests: XCTestCase {
    func testSendCommandParsesJoinedArguments() {
        let command = BrainChatCLICommand(arguments: ["BrainChat", "--send", "Hello", "user"])
        XCTAssertEqual(command, .send("Hello user"))
    }

    func testSpeakCommandParsesJoinedArguments() {
        let command = BrainChatCLICommand(arguments: ["BrainChat", "--speak", "G'day", "user"])
        XCTAssertEqual(command, .speak("G'day user"))
    }

    func testListenCommandParsesWithoutPayload() {
        XCTAssertEqual(BrainChatCLICommand(arguments: ["BrainChat", "--listen"]), .listen)
    }

    func testUnknownCommandReturnsNil() {
        XCTAssertNil(BrainChatCLICommand(arguments: ["BrainChat", "--unknown"]))
    }
}
