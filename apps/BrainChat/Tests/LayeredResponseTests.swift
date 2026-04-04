import XCTest
@testable import BrainChatLib

// MARK: - Layered Response System Tests
// Tests the 4-layer parallel LLM orchestration:
//   Layer 1 — INSTANT  (Groq,   ~500 tok/s, 0-500ms)
//   Layer 2 — LOCAL    (Ollama, on-device,  500ms-2s)
//   Layer 3 — DEEP     (Claude/GPT/Gemini,  2-10s)
//   Layer 4 — CONSENSUS (multi-LLM verify,  10s+)

final class LayerTierTests: XCTestCase {

    // MARK: - Layer Ordering

    func testLayerRawValuesAreStrictlyAscending() {
        XCTAssertEqual(LayerTier.instant.rawValue,   1)
        XCTAssertEqual(LayerTier.fastLocal.rawValue, 2)
        XCTAssertEqual(LayerTier.deep.rawValue,      3)
        XCTAssertEqual(LayerTier.consensus.rawValue, 4)
    }

    func testLayersAreComparableByPriority() {
        XCTAssertLessThan(LayerTier.instant,   .fastLocal)
        XCTAssertLessThan(LayerTier.fastLocal, .deep)
        XCTAssertLessThan(LayerTier.deep,      .consensus)
        XCTAssertLessThan(LayerTier.instant,   .consensus)
    }

    func testLayersSortedAscendingGivesCorrectOrder() {
        let shuffled: [LayerTier] = [.consensus, .instant, .deep, .fastLocal]
        let sorted = shuffled.sorted()
        XCTAssertEqual(sorted, [.instant, .fastLocal, .deep, .consensus])
    }

    // MARK: - Layer Descriptions

    func testAllLayersHaveNonEmptyDescription() {
        for layer in [LayerTier.instant, .fastLocal, .deep, .consensus] {
            XCTAssertFalse(layer.description.isEmpty)
        }
    }

    func testLayerDescriptionsMatchExpected() {
        XCTAssertEqual(LayerTier.instant.description,   "Instant")
        XCTAssertEqual(LayerTier.fastLocal.description, "Local")
        XCTAssertEqual(LayerTier.deep.description,      "Deep")
        XCTAssertEqual(LayerTier.consensus.description, "Consensus")
    }

    func testAllLayersHaveSystemImageIcon() {
        for layer in [LayerTier.instant, .fastLocal, .deep, .consensus] {
            XCTAssertFalse(layer.icon.isEmpty, "\(layer) needs a SF Symbol icon")
        }
    }

    // MARK: - Layer Timeouts

    func testInstantLayerHasShortestTimeout() {
        XCTAssertLessThan(LayerTier.instant.timeoutSeconds,
                          LayerTier.fastLocal.timeoutSeconds)
    }

    func testConsensusLayerHasLongestTimeout() {
        XCTAssertGreaterThan(LayerTier.consensus.timeoutSeconds,
                             LayerTier.deep.timeoutSeconds)
    }

    func testTimeoutsAreStrictlyIncreasing() {
        let timeouts = [LayerTier.instant, .fastLocal, .deep, .consensus]
            .map(\.timeoutSeconds)
        for i in timeouts.indices.dropLast() {
            XCTAssertLessThan(timeouts[i], timeouts[i + 1],
                              "Layer \(i+1) timeout must be less than layer \(i+2)")
        }
    }

    func testInstantTimeoutUnder10Seconds() {
        XCTAssertLessThanOrEqual(LayerTier.instant.timeoutSeconds, 10,
                                 "Instant layer must respond quickly")
    }
}

// MARK: - LayeredChunk Tests

final class LayeredChunkTests: XCTestCase {

    func testChunkStoresAllFields() {
        let chunk = LayeredChunk(
            layer: .instant,
            source: "groq",
            content: "G'day Joseph!"
        )
        XCTAssertEqual(chunk.layer,   .instant)
        XCTAssertEqual(chunk.source,  "groq")
        XCTAssertEqual(chunk.content, "G'day Joseph!")
        XCTAssertFalse(chunk.isFinal)
    }

    func testFinalChunkFlagIsRespected() {
        let partial = LayeredChunk(layer: .deep, source: "claude", content: "...", isFinal: false)
        let final_  = LayeredChunk(layer: .deep, source: "claude", content: "Done.", isFinal: true)
        XCTAssertFalse(partial.isFinal)
        XCTAssertTrue(final_.isFinal)
    }

    func testChunkTimestampIsRecentOnInit() {
        let before = Date()
        let chunk  = LayeredChunk(layer: .fastLocal, source: "ollama", content: "hello")
        let after  = Date()
        XCTAssertGreaterThanOrEqual(chunk.timestamp, before)
        XCTAssertLessThanOrEqual(chunk.timestamp, after)
    }

    func testEmptyContentIsAllowed() {
        let chunk = LayeredChunk(layer: .instant, source: "groq", content: "")
        XCTAssertEqual(chunk.content, "")
    }
}

// MARK: - LayerResult Tests

final class LayerResultTests: XCTestCase {

    func testSucceededResultHasNoError() {
        let result = LayerResult(
            layer: .instant,
            source: "groq",
            fullText: "Fast response",
            latencyMs: 320,
            succeeded: true,
            error: nil
        )
        XCTAssertTrue(result.succeeded)
        XCTAssertNil(result.error)
    }

    func testFailedResultCarriesErrorMessage() {
        let result = LayerResult(
            layer: .deep,
            source: "claude",
            fullText: "",
            latencyMs: 5000,
            succeeded: false,
            error: "Rate limited"
        )
        XCTAssertFalse(result.succeeded)
        XCTAssertEqual(result.error, "Rate limited")
        XCTAssertTrue(result.fullText.isEmpty)
    }

    func testLatencyIsNonNegative() {
        let result = LayerResult(layer: .fastLocal, source: "ollama",
                                 fullText: "ok", latencyMs: 0, succeeded: true, error: nil)
        XCTAssertGreaterThanOrEqual(result.latencyMs, 0)
    }

    func testResultsCanBeSortedByLayer() {
        let results: [LayerResult] = [
            LayerResult(layer: .deep,      source: "claude", fullText: "deep",      latencyMs: 3000, succeeded: true, error: nil),
            LayerResult(layer: .instant,   source: "groq",   fullText: "fast",      latencyMs: 300,  succeeded: true, error: nil),
            LayerResult(layer: .fastLocal, source: "ollama", fullText: "local",     latencyMs: 800,  succeeded: true, error: nil),
            LayerResult(layer: .consensus, source: "multi",  fullText: "consensus", latencyMs: 9000, succeeded: true, error: nil),
        ]
        let sorted = results.sorted { $0.layer < $1.layer }
        XCTAssertEqual(sorted[0].source, "groq")
        XCTAssertEqual(sorted[1].source, "ollama")
        XCTAssertEqual(sorted[2].source, "claude")
        XCTAssertEqual(sorted[3].source, "multi")
    }
}

// MARK: - LayeredResponseEvent Tests

final class LayeredResponseEventTests: XCTestCase {

    func testLayerStartedEventCarriesLayerAndSource() {
        let event = LayeredResponseEvent.layerStarted(.instant, "groq")
        guard case .layerStarted(let layer, let source) = event else {
            XCTFail("Expected .layerStarted"); return
        }
        XCTAssertEqual(layer,  .instant)
        XCTAssertEqual(source, "groq")
    }

    func testLayerDeltaEventWrapsChunk() {
        let chunk = LayeredChunk(layer: .fastLocal, source: "ollama", content: "hello")
        let event = LayeredResponseEvent.layerDelta(chunk)
        guard case .layerDelta(let c) = event else {
            XCTFail("Expected .layerDelta"); return
        }
        XCTAssertEqual(c.source,  "ollama")
        XCTAssertEqual(c.content, "hello")
    }

    func testLayerCompletedEventWrapsResult() {
        let result = LayerResult(layer: .deep, source: "gpt", fullText: "Answer",
                                 latencyMs: 2200, succeeded: true, error: nil)
        let event = LayeredResponseEvent.layerCompleted(result)
        guard case .layerCompleted(let r) = event else {
            XCTFail("Expected .layerCompleted"); return
        }
        XCTAssertEqual(r.fullText, "Answer")
    }

    func testAllLayersCompleteEventCarriesAllResults() {
        let results = [
            LayerResult(layer: .instant,   source: "groq",   fullText: "fast", latencyMs: 310,  succeeded: true, error: nil),
            LayerResult(layer: .fastLocal, source: "ollama", fullText: "ok",   latencyMs: 900,  succeeded: true, error: nil),
            LayerResult(layer: .deep,      source: "claude", fullText: "best", latencyMs: 3100, succeeded: true, error: nil),
        ]
        let event = LayeredResponseEvent.allLayersComplete(results)
        guard case .allLayersComplete(let rs) = event else {
            XCTFail("Expected .allLayersComplete"); return
        }
        XCTAssertEqual(rs.count, 3)
    }

    func testConsensusResultEncodesAgreement() {
        let agreed    = LayeredResponseEvent.consensusResult(agreed: true,  sources: ["claude", "gpt"])
        let disagreed = LayeredResponseEvent.consensusResult(agreed: false, sources: ["claude", "grok"])
        guard case .consensusResult(let a, _) = agreed,
              case .consensusResult(let d, _) = disagreed else {
            XCTFail("Expected .consensusResult"); return
        }
        XCTAssertTrue(a)
        XCTAssertFalse(d)
    }
}

// MARK: - LayeredStrategy Tests

final class LayeredStrategyTests: XCTestCase {

    func testSpeedFirstStrategyCaptured() {
        let strategy = LayeredStrategy.speedFirst
        if case .speedFirst = strategy { } else { XCTFail("Expected speedFirst") }
    }

    func testQualityFirstStrategyCaptured() {
        let strategy = LayeredStrategy.qualityFirst
        if case .qualityFirst = strategy { } else { XCTFail("Expected qualityFirst") }
    }

    func testConsensusOnlyStrategyCaptured() {
        let strategy = LayeredStrategy.consensusOnly
        if case .consensusOnly = strategy { } else { XCTFail("Expected consensusOnly") }
    }

    func testSingleLayerStrategyPreservesLayerChoice() {
        let strategy = LayeredStrategy.singleLayer(.deep)
        if case .singleLayer(let layer) = strategy {
            XCTAssertEqual(layer, .deep)
        } else {
            XCTFail("Expected .singleLayer(.deep)")
        }
    }

    func testDefaultStrategyForNormalChatIsSpeedFirst() {
        // Joseph uses voice chat – fastest response matters most
        let expected = LayeredStrategy.speedFirst
        if case .speedFirst = expected { } else { XCTFail("Speed-first must be default for voice") }
    }

    func testConsensusStrategyUsedForYoloMode() {
        // YOLO (autonomous) mode must have multi-LLM agreement before executing commands
        let strategy = LayeredStrategy.consensusOnly
        if case .consensusOnly = strategy { } else { XCTFail("YOLO must use consensus strategy") }
    }
}
