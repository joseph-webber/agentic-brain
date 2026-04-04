import XCTest
@testable import BrainChatLib

final class BrainChatCLITests: XCTestCase {
    func testSendCommandParsesJoinedArguments() {
        let command = BrainChatCLICommand(arguments: ["BrainChat", "--send", "Hello", "Joseph"])
        XCTAssertEqual(command, .send("Hello Joseph"))
    }

    func testSpeakCommandParsesJoinedArguments() {
        let command = BrainChatCLICommand(arguments: ["BrainChat", "--speak", "G'day", "Joseph"])
        XCTAssertEqual(command, .speak("G'day Joseph"))
    }

    func testListenCommandParsesWithoutPayload() {
        XCTAssertEqual(BrainChatCLICommand(arguments: ["BrainChat", "--listen"]), .listen)
    }

    func testUnknownCommandReturnsNil() {
        XCTAssertNil(BrainChatCLICommand(arguments: ["BrainChat", "--unknown"]))
    }
}
