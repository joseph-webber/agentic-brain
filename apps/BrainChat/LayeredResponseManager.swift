import Foundation

// =============================================================================
// LayeredResponseManager — Parallel multi-LLM response orchestrator
//
// Fires all layers concurrently, merges results by priority:
//   Layer 1 — INSTANT (Groq llama-3.1-8b, ~500 tok/s)     0-500ms
//   Layer 2 — FAST LOCAL (Ollama llama3.2:3b)              500ms-2s
//   Layer 3 — DEEP (Claude/GPT/Gemini)                     2-10s
//   Layer 4 — CONSENSUS (multi-LLM verification)           10s+
//
// The UI shows Layer 1 immediately, then weaves in deeper answers.
// Voice speaks Layer 1 first, then additions from Layer 3.
// =============================================================================

// MARK: - Data Types

/// Public alias so tests and event-bus code can use the descriptive name.
typealias LLMResponseLayer = LayerTier

enum LayerTier: Int, Comparable, Sendable, CustomStringConvertible {
    case instant = 1     // Groq — ultra-fast cloud inference
    case fastLocal = 2   // Ollama — on-device, no network
    case deep = 3        // Claude/GPT/Gemini — full reasoning
    case consensus = 4   // Multi-LLM agreement (critical ops)

    static func < (lhs: LayerTier, rhs: LayerTier) -> Bool {
        lhs.rawValue < rhs.rawValue
    }

    var description: String {
        switch self {
        case .instant:   return "Instant"
        case .fastLocal: return "Local"
        case .deep:      return "Deep"
        case .consensus: return "Consensus"
        }
    }

    var icon: String {
        switch self {
        case .instant:   return "bolt.fill"
        case .fastLocal: return "desktopcomputer"
        case .deep:      return "brain.head.profile"
        case .consensus: return "checkmark.shield.fill"
        }
    }

    var timeoutSeconds: TimeInterval {
        switch self {
        case .instant:   return 5
        case .fastLocal: return 10
        case .deep:      return 30
        case .consensus: return 45
        }
    }
}

struct LayeredChunk: Sendable {
    let layer: LayerTier
    let source: String    // "groq", "ollama", "claude", etc.
    let content: String
    let isFinal: Bool
    let timestamp: Date

    init(layer: LayerTier, source: String, content: String, isFinal: Bool = false) {
        self.layer = layer
        self.source = source
        self.content = content
        self.isFinal = isFinal
        self.timestamp = Date()
    }
}

struct LayerResult: Sendable {
    let layer: LayerTier
    let source: String
    let fullText: String
    let latencyMs: Int
    let succeeded: Bool
    let error: String?

    init(layer: LayerTier, source: String, fullText: String, latencyMs: Int, succeeded: Bool, error: String? = nil) {
        self.layer = layer
        self.source = source
        self.fullText = fullText
        self.latencyMs = latencyMs
        self.succeeded = succeeded
        self.error = error
    }
}

enum LayeredResponseEvent: Sendable {
    case layerStarted(LayerTier, String)          // layer + source name
    case layerDelta(LayeredChunk)                      // streaming chunk
    case layerCompleted(LayerResult)                    // layer finished
    case deepThinkingStarted                           // show "thinking deeper" UI
    case enhancedResponseReady(String)                 // final merged deep answer
    case consensusResult(agreed: Bool, sources: [String])
    case allLayersComplete([LayerResult])               // everything done
}

/// Strategy for how to use layered responses
enum LayeredStrategy: Sendable {
    case speedFirst       // Show Layer 1 ASAP, weave in deeper layers
    case qualityFirst     // Wait for Layer 3, use Layer 1 as preview only
    case consensusOnly    // Require multi-LLM agreement (critical commands)
    case singleLayer(LayerTier)  // Bypass layering, use one layer
}

// MARK: - Configuration

struct LayeredResponseConfiguration: Sendable {
    let strategy: LayeredStrategy
    let enableLayer1: Bool  // Groq instant
    let enableLayer2: Bool  // Ollama local
    let enableLayer3: Bool  // Claude/GPT deep
    let enableLayer4: Bool  // Consensus
    let layer3Provider: LLMProvider  // Which deep provider to use
    let groqAPIKey: String
    let groqModel: String
    let routerConfig: LLMRouterConfiguration

    static func from(
        settings: LLMRouterConfiguration,
        groqAPIKey: String,
        strategy: LayeredStrategy = .speedFirst
    ) -> LayeredResponseConfiguration {
        LayeredResponseConfiguration(
            strategy: strategy,
            enableLayer1: !groqAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
            enableLayer2: true,  // Ollama is always available locally
            enableLayer3: true,
            enableLayer4: false, // Only for critical commands
            layer3Provider: settings.provider,
            groqAPIKey: groqAPIKey,
            groqModel: "llama-3.1-8b-instant",
            routerConfig: settings
        )
    }
}

// MARK: - LayeredResponseManager

@MainActor
final class LayeredResponseManager: ObservableObject {
    @Published private(set) var activeLayer: LayerTier?
    @Published private(set) var layerStatuses: [LayerTier: String] = [:]
    @Published private(set) var isThinkingDeeper = false
    @Published private(set) var lastResults: [LayerResult] = []

    private let groqClient: any GroqStreaming
    private let ollamaAPI: any OllamaStreaming
    private let claudeAPI: any ClaudeStreaming
    private let openAIAPI: any OpenAIStreaming
    private let grokClient: any GrokStreaming
    private let geminiClient: any GeminiStreaming

    init(
        groqClient: any GroqStreaming = GroqClient(),
        ollamaAPI: any OllamaStreaming = OllamaAPI(),
        claudeAPI: any ClaudeStreaming = ClaudeAPI(),
        openAIAPI: any OpenAIStreaming = OpenAIAPI(),
        grokClient: any GrokStreaming = GrokClient(),
        geminiClient: any GeminiStreaming = GeminiClient()
    ) {
        self.groqClient = groqClient
        self.ollamaAPI = ollamaAPI
        self.claudeAPI = claudeAPI
        self.openAIAPI = openAIAPI
        self.grokClient = grokClient
        self.geminiClient = geminiClient
    }

    /// Fire all enabled layers in parallel, streaming chunks via the callback.
    /// Returns the best final response text.
    func getLayeredResponse(
        messages: [AIChatMessage],
        configuration: LayeredResponseConfiguration,
        onEvent: @escaping @Sendable (LayeredResponseEvent) -> Void
    ) async -> String {
        lastResults = []
        isThinkingDeeper = false

        switch configuration.strategy {
        case .singleLayer(let layer):
            return await runSingleLayer(
                layer: layer, messages: messages,
                configuration: configuration, onEvent: onEvent
            )
        case .consensusOnly:
            return await runConsensus(
                messages: messages, configuration: configuration, onEvent: onEvent
            )
        case .speedFirst, .qualityFirst:
            return await runParallelLayers(
                messages: messages, configuration: configuration, onEvent: onEvent
            )
        }
    }

    // MARK: - Parallel Layer Execution

    private func runParallelLayers(
        messages: [AIChatMessage],
        configuration: LayeredResponseConfiguration,
        onEvent: @escaping @Sendable (LayeredResponseEvent) -> Void
    ) async -> String {
        let results = ManagedCriticalState<[LayerResult]>([])
        let instantResponseReady = ManagedCriticalState<Bool>(false)
        let deepResponseText = ManagedCriticalState<String?>(nil)

        await withTaskGroup(of: LayerResult.self) { group in
            // Layer 1: Groq Instant
            if configuration.enableLayer1 {
                group.addTask { [groqClient] in
                    await self.runLayer(
                        layer: .instant, source: "Groq",
                        onEvent: onEvent
                    ) {
                        try await groqClient.streamResponse(
                            apiKey: configuration.groqAPIKey,
                            model: configuration.groqModel,
                            messages: messages,
                            onDelta: { text in
                                onEvent(.layerDelta(LayeredChunk(
                                    layer: .instant, source: "Groq", content: text
                                )))
                            }
                        )
                    }
                }
            }

            // Layer 2: Ollama Fast Local
            if configuration.enableLayer2 {
                group.addTask { [ollamaAPI] in
                    await self.runLayer(
                        layer: .fastLocal, source: "Ollama",
                        onEvent: onEvent
                    ) {
                        try await ollamaAPI.streamResponse(
                            endpoint: configuration.routerConfig.ollamaEndpoint,
                            model: configuration.routerConfig.ollamaModel,
                            messages: messages,
                            onDelta: { text in
                                onEvent(.layerDelta(LayeredChunk(
                                    layer: .fastLocal, source: "Ollama", content: text
                                )))
                            }
                        )
                    }
                }
            }

            // Layer 3: Deep Provider
            if configuration.enableLayer3 {
                let provider = configuration.layer3Provider
                group.addTask {
                    // Signal "thinking deeper" once Layer 1 has had time to respond
                    try? await Task.sleep(nanoseconds: 500_000_000)  // 500ms
                    await MainActor.run { self.isThinkingDeeper = true }
                    onEvent(.deepThinkingStarted)

                    let result = await self.runDeepLayer(
                        provider: provider, messages: messages,
                        configuration: configuration, onEvent: onEvent
                    )

                    if result.succeeded {
                        deepResponseText.withLock { $0 = result.fullText }
                        onEvent(.enhancedResponseReady(result.fullText))
                    }

                    return result
                }
            }

            // Collect all results
            for await result in group {
                results.withLock { $0.append(result) }

                if result.layer == .instant && result.succeeded {
                    instantResponseReady.withLock { $0 = true }
                }
            }
        }

        let allResults = results.withLock { $0 }
        await MainActor.run {
            self.lastResults = allResults
            self.isThinkingDeeper = false
            self.activeLayer = nil
        }
        onEvent(.allLayersComplete(allResults))

        return selectBestResponse(from: allResults, strategy: configuration.strategy)
    }

    // MARK: - Single Layer

    private func runSingleLayer(
        layer: LayerTier,
        messages: [AIChatMessage],
        configuration: LayeredResponseConfiguration,
        onEvent: @escaping @Sendable (LayeredResponseEvent) -> Void
    ) async -> String {
        let result: LayerResult
        switch layer {
        case .instant:
            result = await runLayer(layer: .instant, source: "Groq", onEvent: onEvent) { [groqClient] in
                try await groqClient.streamResponse(
                    apiKey: configuration.groqAPIKey,
                    model: configuration.groqModel,
                    messages: messages,
                    onDelta: { onEvent(.layerDelta(LayeredChunk(layer: .instant, source: "Groq", content: $0))) }
                )
            }
        case .fastLocal:
            result = await runLayer(layer: .fastLocal, source: "Ollama", onEvent: onEvent) { [ollamaAPI] in
                try await ollamaAPI.streamResponse(
                    endpoint: configuration.routerConfig.ollamaEndpoint,
                    model: configuration.routerConfig.ollamaModel,
                    messages: messages,
                    onDelta: { onEvent(.layerDelta(LayeredChunk(layer: .fastLocal, source: "Ollama", content: $0))) }
                )
            }
        case .deep:
            result = await runDeepLayer(
                provider: configuration.layer3Provider,
                messages: messages, configuration: configuration, onEvent: onEvent
            )
        case .consensus:
            let text = await runConsensus(messages: messages, configuration: configuration, onEvent: onEvent)
            return text
        }

        let finalResults = [result]
        await MainActor.run { self.lastResults = finalResults }
        onEvent(.allLayersComplete(finalResults))
        return result.fullText
    }

    // MARK: - Layer Runner

    private nonisolated func runLayer(
        layer: LayerTier,
        source: String,
        onEvent: @escaping @Sendable (LayeredResponseEvent) -> Void,
        work: @escaping @Sendable () async throws -> String
    ) async -> LayerResult {
        onEvent(.layerStarted(layer, source))
        let startTime = ContinuousClock.now

        do {
            let text = try await withThrowingTaskGroup(of: String.self) { group in
                group.addTask { try await work() }
                group.addTask {
                    try await Task.sleep(nanoseconds: UInt64(layer.timeoutSeconds * 1_000_000_000))
                    throw CancellationError()
                }

                guard let first = try await group.next() else {
                    throw AIServiceError.emptyResponse("\(source) timed out")
                }
                group.cancelAll()
                return first
            }

            let elapsed = startTime.duration(to: .now)
            let ms = Int(elapsed.components.seconds * 1000 + elapsed.components.attoseconds / 1_000_000_000_000_000)
            let result = LayerResult(layer: layer, source: source, fullText: text, latencyMs: ms, succeeded: true, error: nil)
            onEvent(.layerCompleted(result))
            return result

        } catch is CancellationError {
            let result = LayerResult(layer: layer, source: source, fullText: "", latencyMs: Int(layer.timeoutSeconds * 1000), succeeded: false, error: "Timed out after \(Int(layer.timeoutSeconds))s")
            onEvent(.layerCompleted(result))
            return result

        } catch {
            let elapsed = startTime.duration(to: .now)
            let ms = Int(elapsed.components.seconds * 1000 + elapsed.components.attoseconds / 1_000_000_000_000_000)
            let result = LayerResult(layer: layer, source: source, fullText: "", latencyMs: ms, succeeded: false, error: error.localizedDescription)
            onEvent(.layerCompleted(result))
            return result
        }
    }

    // MARK: - Deep Layer (Provider-specific)

    private func runDeepLayer(
        provider: LLMProvider,
        messages: [AIChatMessage],
        configuration: LayeredResponseConfiguration,
        onEvent: @escaping @Sendable (LayeredResponseEvent) -> Void
    ) async -> LayerResult {
        let config = configuration.routerConfig
        let source = provider.shortName

        return await runLayer(layer: .deep, source: source, onEvent: onEvent) {
            switch provider {
            case .claude:
                return try await self.claudeAPI.streamResponse(
                    apiKey: config.claudeAPIKey, model: config.claudeModel,
                    systemPrompt: config.effectiveSystemPrompt, messages: messages,
                    onDelta: { onEvent(.layerDelta(LayeredChunk(layer: .deep, source: source, content: $0))) }
                )
            case .gpt:
                return try await self.openAIAPI.streamResponse(
                    apiKey: config.openAIAPIKey, model: config.openAIModel,
                    messages: messages,
                    onDelta: { onEvent(.layerDelta(LayeredChunk(layer: .deep, source: source, content: $0))) }
                )
            case .grok:
                return try await self.grokClient.streamResponse(
                    apiKey: config.grokAPIKey, model: config.grokModel,
                    messages: messages,
                    onDelta: { onEvent(.layerDelta(LayeredChunk(layer: .deep, source: source, content: $0))) }
                )
            case .groq:
                return try await self.groqClient.streamResponse(
                    apiKey: config.groqAPIKey, model: config.groqModel,
                    messages: messages,
                    onDelta: { onEvent(.layerDelta(LayeredChunk(layer: .deep, source: source, content: $0))) }
                )
            case .gemini:
                return try await self.geminiClient.streamResponse(
                    apiKey: config.geminiAPIKey, model: config.geminiModel,
                    systemPrompt: config.effectiveSystemPrompt, messages: messages,
                    onDelta: { onEvent(.layerDelta(LayeredChunk(layer: .deep, source: source, content: $0))) }
                )
            case .ollama:
                return try await self.ollamaAPI.streamResponse(
                    endpoint: config.ollamaEndpoint, model: config.ollamaModel,
                    messages: messages,
                    onDelta: { onEvent(.layerDelta(LayeredChunk(layer: .deep, source: source, content: $0))) }
                )
            case .copilot:
                return try await self.ollamaAPI.streamResponse(
                    endpoint: config.ollamaEndpoint, model: config.ollamaModel,
                    messages: messages,
                    onDelta: { onEvent(.layerDelta(LayeredChunk(layer: .deep, source: "Ollama", content: $0))) }
                )
            }
        }
    }

    // MARK: - Consensus (Layer 4)

    private func runConsensus(
        messages: [AIChatMessage],
        configuration: LayeredResponseConfiguration,
        onEvent: @escaping @Sendable (LayeredResponseEvent) -> Void
    ) async -> String {
        // Run at least 2 providers in parallel and compare
        let config = configuration.routerConfig
        var providers: [(LLMProvider, String)] = []

        if !config.claudeAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            providers.append((.claude, "Claude"))
        }
        if !config.openAIAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            providers.append((.gpt, "GPT"))
        }
        if !config.grokAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            providers.append((.grok, "Grok"))
        }
        // Always include Ollama as a tiebreaker
        providers.append((.ollama, "Ollama"))

        // Need at least 2 for consensus
        let activePairs = Array(providers.prefix(3))

        let consensusResults = ManagedCriticalState<[LayerResult]>([])

        await withTaskGroup(of: LayerResult.self) { group in
            for (provider, _) in activePairs {
                group.addTask {
                    await self.runDeepLayer(
                        provider: provider, messages: messages,
                        configuration: configuration, onEvent: onEvent
                    )
                }
            }

            for await result in group {
                consensusResults.withLock { $0.append(result) }
            }
        }

        let results = consensusResults.withLock { $0 }
        let successful = results.filter { $0.succeeded }
        let sources = successful.map { $0.source }

        if successful.count >= 2 {
            // Check rough agreement (responses should be semantically similar)
            let agreed = checkAgreement(successful.map { $0.fullText })
            onEvent(.consensusResult(agreed: agreed, sources: sources))

            if agreed {
                // Return the longest response (most detail)
                let best = successful.max(by: { $0.fullText.count < $1.fullText.count })!
                return "✅ Consensus (\(sources.joined(separator: ", "))): \(best.fullText)"
            } else {
                let best = successful.first!
                return "⚠️ No consensus — using \(best.source): \(best.fullText)"
            }
        } else if let single = successful.first {
            onEvent(.consensusResult(agreed: false, sources: [single.source]))
            return "⚠️ Only \(single.source) responded: \(single.fullText)"
        } else {
            onEvent(.consensusResult(agreed: false, sources: []))
            return "❌ All providers failed for consensus check."
        }
    }

    // MARK: - Response Selection

    private func selectBestResponse(from results: [LayerResult], strategy: LayeredStrategy) -> String {
        let successful = results.filter { $0.succeeded }.sorted { $0.layer < $1.layer }

        switch strategy {
        case .speedFirst:
            // Prefer deep if available, else instant, else local
            if let deep = successful.first(where: { $0.layer == .deep }) {
                return deep.fullText
            }
            if let instant = successful.first(where: { $0.layer == .instant }) {
                return instant.fullText
            }
            return successful.first?.fullText ?? "No response available."

        case .qualityFirst:
            // Always prefer deepest layer
            if let deep = successful.first(where: { $0.layer == .deep }) {
                return deep.fullText
            }
            return successful.last?.fullText ?? "No response available."

        case .consensusOnly:
            return successful.first?.fullText ?? "No consensus reached."

        case .singleLayer:
            return successful.first?.fullText ?? "No response available."
        }
    }

    // MARK: - Agreement Check

    /// Simple heuristic: responses agree if they share significant keywords.
    private func checkAgreement(_ responses: [String]) -> Bool {
        guard responses.count >= 2 else { return false }

        let stopWords: Set<String> = ["the", "a", "an", "is", "are", "was", "were", "to", "of", "in",
                                       "for", "and", "or", "but", "not", "it", "this", "that", "with"]

        func keywords(_ text: String) -> Set<String> {
            Set(text.lowercased()
                .components(separatedBy: .alphanumerics.inverted)
                .filter { $0.count > 3 && !stopWords.contains($0) })
        }

        let sets = responses.map { keywords($0) }
        guard let first = sets.first, !first.isEmpty else { return true }

        // Check pairwise overlap — at least 30% keyword overlap
        for i in 1..<sets.count {
            let overlap = first.intersection(sets[i])
            let overlapRatio = Double(overlap.count) / Double(max(first.count, sets[i].count, 1))
            if overlapRatio < 0.3 {
                return false
            }
        }

        return true
    }
}

// MARK: - Thread-Safe Wrapper

/// Lightweight lock-based mutable state for use in concurrent tasks.
final class ManagedCriticalState<Value: Sendable>: @unchecked Sendable {
    private var _value: Value
    private let lock = NSLock()

    init(_ value: Value) { _value = value }

    @discardableResult
    func withLock<R>(_ body: (inout Value) -> R) -> R {
        lock.lock()
        defer { lock.unlock() }
        return body(&_value)
    }
}
