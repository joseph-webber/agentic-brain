import XCTest
@testable import BrainChatLib

// =============================================================================
// VoiceCodingEngine Tests — Voice command parsing and CodeSpeaker formatting
// =============================================================================

final class VoiceCodingCommandTests: XCTestCase {

    let engine = VoiceCodingEngine.shared
    let speaker = CodeSpeaker()

    // MARK: - Line Reading Commands

    func testReadLineParsing() {
        XCTAssertEqual(engine.parse("read line 10"), .readLine(10))
        XCTAssertEqual(engine.parse("Read Line 5"), .readLine(5))
        XCTAssertEqual(engine.parse("show line 42"), .readLine(42))
        XCTAssertEqual(engine.parse("what's on line 1"), .readLine(1))
        XCTAssertEqual(engine.parse("what is on line 99"), .readLine(99))
    }

    func testReadLineRangeParsing() {
        XCTAssertEqual(engine.parse("read lines 10 to 20"), .readLines(10, 20))
        XCTAssertEqual(engine.parse("show lines 1 through 5"), .readLines(1, 5))
        XCTAssertEqual(engine.parse("read line 3 to 7"), .readLines(3, 7))
    }

    func testGoToLineParsing() {
        XCTAssertEqual(engine.parse("go to line 15"), .readLine(15))
        XCTAssertEqual(engine.parse("jump to line 8"), .readLine(8))
    }

    // MARK: - Navigation Commands

    func testGoToFunctionParsing() {
        XCTAssertEqual(engine.parse("go to function main"), .goToFunction("main"))
        XCTAssertEqual(engine.parse("find function processData"), .goToFunction("processdata"))
        XCTAssertEqual(engine.parse("jump to method handleInput"), .goToFunction("handleinput"))
        XCTAssertEqual(engine.parse("go to def calculate"), .goToFunction("calculate"))
    }

    func testListFunctionsParsing() {
        XCTAssertEqual(engine.parse("list functions"), .listFunctions(nil))
        XCTAssertEqual(engine.parse("show functions"), .listFunctions(nil))
    }

    func testSearchCodeParsing() {
        XCTAssertEqual(engine.parse("search for handleInput"), .searchCode("handleinput"))
        XCTAssertEqual(engine.parse("grep TODO"), .searchCode("todo"))
    }

    // MARK: - Code Understanding Commands

    func testExplainParsing() {
        XCTAssertEqual(engine.parse("explain this"), .explainCode(nil))
        XCTAssertEqual(engine.parse("explain the code"), .explainCode(nil))
        XCTAssertEqual(engine.parse("explain"), .explainCode(nil))
    }

    func testFixErrorParsing() {
        XCTAssertEqual(engine.parse("fix this"), .fixError(nil))
        XCTAssertEqual(engine.parse("fix the error"), .fixError(nil))
        XCTAssertEqual(engine.parse("debug this"), .fixError(nil))
        XCTAssertEqual(engine.parse("what's wrong"), .fixError(nil))
    }

    func testRefactorParsing() {
        XCTAssertEqual(engine.parse("refactor"), .refactor(nil))
        XCTAssertEqual(engine.parse("refactor this"), .refactor(nil))
    }

    func testSpellParsing() {
        XCTAssertEqual(engine.parse("spell handleInput"), .spellIdentifier("handleinput"))
        XCTAssertEqual(engine.parse("spell out VoiceCodingEngine"), .spellIdentifier("voicecodingengine"))
    }

    // MARK: - Editing Commands

    func testDeleteLineParsing() {
        XCTAssertEqual(engine.parse("delete line 5"), .deleteLine(5))
    }

    func testCopyLineParsing() {
        XCTAssertEqual(engine.parse("copy line 3"), .copyCode(3))
        XCTAssertEqual(engine.parse("copy this"), .copyCode(nil))
    }

    // MARK: - File Commands

    func testSaveParsing() {
        XCTAssertEqual(engine.parse("save to sort.py"), .saveToFile("sort.py", nil))
        XCTAssertEqual(engine.parse("save as output.txt"), .saveToFile("output.txt", nil))
    }

    func testCreateFileParsing() {
        XCTAssertEqual(engine.parse("create file test.py"), .createFile("test.py", nil))
        // "helpers.swift" contains "swift" which triggers language detection
        let result = engine.parse("new file helpers.swift")
        if case .createFile(let name, _) = result {
            XCTAssertEqual(name, "helpers.swift")
        } else {
            XCTFail("Expected createFile, got \(result)")
        }
    }

    func testCloseFileParsing() {
        XCTAssertEqual(engine.parse("close file"), .closeFile)
    }

    // MARK: - Git Commands

    func testGitStatusParsing() {
        XCTAssertEqual(engine.parse("git status"), .gitStatus)
        XCTAssertEqual(engine.parse("check status"), .gitStatus)
        XCTAssertEqual(engine.parse("what's changed"), .gitStatus)
    }

    func testGitDiffParsing() {
        XCTAssertEqual(engine.parse("git diff"), .gitDiff)
        XCTAssertEqual(engine.parse("show diff"), .gitDiff)
        XCTAssertEqual(engine.parse("show changes"), .gitDiff)
    }

    func testCommitParsing() {
        XCTAssertEqual(engine.parse("commit add voice coding"), .commitChanges("add voice coding"))
    }

    // MARK: - Run Tests

    func testRunTestsParsing() {
        XCTAssertEqual(engine.parse("run tests"), .runTests(nil))
        XCTAssertEqual(engine.parse("run the tests"), .runTests(nil))
    }

    // MARK: - Meta Commands

    func testUndoParsing() {
        XCTAssertEqual(engine.parse("undo"), .undoLast)
        XCTAssertEqual(engine.parse("undo last"), .undoLast)
        XCTAssertEqual(engine.parse("undo that"), .undoLast)
    }

    func testRepeatParsing() {
        XCTAssertEqual(engine.parse("repeat"), .repeatLast)
        XCTAssertEqual(engine.parse("again"), .repeatLast)
        XCTAssertEqual(engine.parse("do it again"), .repeatLast)
    }

    // MARK: - Replace Commands

    func testReplaceParsing() {
        XCTAssertEqual(engine.parse("replace foo with bar"), .replaceText("foo", "bar"))
        XCTAssertEqual(engine.parse("replace 'hello' with 'world'"), .replaceText("hello", "world"))
    }

    // MARK: - Insert Commands

    func testInsertLineParsing() {
        let result = engine.parse("insert at line 5 print('hi')")
        if case .insertLine(let n, let content) = result {
            XCTAssertEqual(n, 5)
            XCTAssertTrue(content.contains("print"))
        } else {
            XCTFail("Expected insertLine, got \(result)")
        }
    }

    // MARK: - Open / Read File Commands

    func testOpenFileParsing() {
        XCTAssertEqual(engine.parse("open file test.py"), .openFile("test.py"))
        XCTAssertEqual(engine.parse("open main.swift"), .openFile("main.swift"))
        XCTAssertEqual(engine.parse("read file utils.js"), .openFile("utils.js"))
    }

    // MARK: - Create Function Commands

    func testCreateFunctionParsing() {
        let result = engine.parse("create function calculate")
        if case .createFunction(let name, _) = result {
            XCTAssertEqual(name, "calculate")
        } else {
            XCTFail("Expected createFunction, got \(result)")
        }
    }

    // MARK: - Non-commands

    func testNonCommandReturnsNone() {
        XCTAssertEqual(engine.parse("hello world"), .none)
        XCTAssertEqual(engine.parse("what's the weather"), .none)
    }

    // MARK: - isVoiceCodingCommand

    func testIsVoiceCodingCommand() {
        XCTAssertTrue(engine.isVoiceCodingCommand("read line 5"))
        XCTAssertTrue(engine.isVoiceCodingCommand("go to function main"))
        XCTAssertTrue(engine.isVoiceCodingCommand("explain this"))
        XCTAssertTrue(engine.isVoiceCodingCommand("fix this"))
        XCTAssertTrue(engine.isVoiceCodingCommand("commit add new feature"))
        XCTAssertFalse(engine.isVoiceCodingCommand("hello"))
        XCTAssertFalse(engine.isVoiceCodingCommand("what time is it"))
    }

    // MARK: - Spoken Confirmations

    func testSpokenConfirmations() {
        XCTAssertEqual(VoiceCodingAction.readLine(10).spokenConfirmation, "Reading line 10")
        XCTAssertEqual(VoiceCodingAction.readLines(5, 15).spokenConfirmation, "Reading lines 5 through 15")
        XCTAssertEqual(VoiceCodingAction.goToFunction("main").spokenConfirmation, "Going to function main")
        XCTAssertEqual(VoiceCodingAction.explainCode(nil).spokenConfirmation, "Explaining the code")
        XCTAssertEqual(VoiceCodingAction.fixError(nil).spokenConfirmation, "Looking for a fix")
        XCTAssertEqual(VoiceCodingAction.gitStatus.spokenConfirmation, "Checking git status")
        XCTAssertEqual(VoiceCodingAction.none.spokenConfirmation, "")
    }
}

// MARK: - CodeSpeaker Tests

final class CodeSpeakerTests: XCTestCase {

    let speaker = CodeSpeaker()

    func testFormatLineWithContent() {
        let result = speaker.formatLine(number: 5, content: "    let x = 10")
        XCTAssertTrue(result.hasPrefix("Line 5:"))
        XCTAssertTrue(result.contains("let x"))
    }

    func testFormatBlankLine() {
        let result = speaker.formatLine(number: 3, content: "   ")
        XCTAssertEqual(result, "Line 3: blank")
    }

    func testFormatCodeBlock() {
        let code = "def hello():\n    print('hello')"
        let result = speaker.formatForSpeech(code, language: "Python")
        XCTAssertTrue(result.contains("Python code, 2 lines"))
        XCTAssertTrue(result.contains("Line 1:"))
        XCTAssertTrue(result.contains("Line 2:"))
        XCTAssertTrue(result.contains("End of code"))
    }

    func testPronounceOperators() {
        XCTAssertTrue(speaker.pronounceCode("x != y").contains("not equal to"))
        XCTAssertTrue(speaker.pronounceCode("x == y").contains("equals equals"))
        XCTAssertTrue(speaker.pronounceCode("x >= y").contains("greater than or equal to"))
        XCTAssertTrue(speaker.pronounceCode("a -> b").contains("returns"))
        XCTAssertTrue(speaker.pronounceCode("a && b").contains("and"))
        XCTAssertTrue(speaker.pronounceCode("a || b").contains("or"))
    }

    func testPronounceKeywords() {
        let result = speaker.pronounceCode("def main():")
        XCTAssertTrue(result.contains("define function"))
    }

    func testPronounceBraces() {
        XCTAssertEqual(speaker.pronounceCode("{"), "open brace")
        XCTAssertEqual(speaker.pronounceCode("}"), "close brace")
    }

    func testSpellSnakeCase() {
        let result = speaker.spellIdentifier("my_function_name")
        XCTAssertTrue(result.contains("snake case"))
        XCTAssertTrue(result.contains("3 parts"))
    }

    func testSpellCamelCase() {
        let result = speaker.spellIdentifier("HandleInput")
        XCTAssertTrue(result.contains("Pascal case"))
        XCTAssertTrue(result.contains("2 parts"))
    }

    func testSpellCamelCaseLowerStart() {
        let result = speaker.spellIdentifier("handleInput")
        XCTAssertTrue(result.contains("camel case"))
        XCTAssertTrue(result.contains("2 parts"))
        XCTAssertTrue(result.contains("handle"))
        XCTAssertTrue(result.contains("Input"))
    }

    func testFormatRange() {
        let lines = ["first", "second", "third", "fourth", "fifth"]
        let result = speaker.formatRange(lines: lines, from: 2, to: 4)
        XCTAssertTrue(result.contains("Line 2:"))
        XCTAssertTrue(result.contains("Line 3:"))
        XCTAssertTrue(result.contains("Line 4:"))
        XCTAssertFalse(result.contains("Line 1:"))
        XCTAssertFalse(result.contains("Line 5:"))
    }

    func testPronounceMoreOperators() {
        XCTAssertTrue(speaker.pronounceCode("x += 1").contains("plus equals"))
        XCTAssertTrue(speaker.pronounceCode("x -= 1").contains("minus equals"))
        XCTAssertTrue(speaker.pronounceCode("x <= y").contains("less than or equal to"))
        XCTAssertTrue(speaker.pronounceCode("a => b").contains("arrow"))
        XCTAssertTrue(speaker.pronounceCode("x...y").contains("dot dot dot"))
        XCTAssertTrue(speaker.pronounceCode("0..<10").contains("up to"))
        XCTAssertTrue(speaker.pronounceCode("Foo::bar").contains("scope"))
    }

    func testDetectLanguageFromFilename() {
        XCTAssertEqual(CodeSpeaker.detectLanguageFromFilename("test.py"), "Python")
        XCTAssertEqual(CodeSpeaker.detectLanguageFromFilename("app.swift"), "Swift")
        XCTAssertEqual(CodeSpeaker.detectLanguageFromFilename("index.js"), "JavaScript")
        XCTAssertEqual(CodeSpeaker.detectLanguageFromFilename("main.ts"), "TypeScript")
        XCTAssertEqual(CodeSpeaker.detectLanguageFromFilename("Cargo.rs"), "Rust")
        XCTAssertNil(CodeSpeaker.detectLanguageFromFilename("readme"))
    }

    func testDetectLanguageFromCode() {
        XCTAssertEqual(CodeSpeaker.detectLanguageFromCode("def main():\n    pass"), "Python")
        XCTAssertEqual(CodeSpeaker.detectLanguageFromCode("func main() -> Void {"), "Swift")
    }
}
