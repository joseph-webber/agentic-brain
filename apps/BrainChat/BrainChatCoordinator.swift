import Foundation

/// Legacy configuration used by BrainChatCoordinator.
/// Maps onto LLMRouterConfiguration for the active LLMRouter.
struct AIServiceConfig {
    var systemPrompt: String
    var claudeAPIKey: String
    var openAIAPIKey: String
    var groqAPIKey: String
    var grokAPIKey: String
    var geminiAPIKey: String
    var ollamaEndpoint: String
    var ollamaModel: String
    var claudeModel: String
    var openAIModel: String
    var groqModel: String
    var grokModel: String
    var geminiModel: String
    var provider: LLMProvider
    var yoloMode: Bool
    var bridgeWebSocketURL: String

    init(
        systemPrompt: String = "You are Karen, an Australian AI assistant helping users code",
        claudeAPIKey: String = "",
        openAIAPIKey: String = "",
        groqAPIKey: String = "",
        grokAPIKey: String = "",
        geminiAPIKey: String = "",
        ollamaEndpoint: String = "http://localhost:11434/api/chat",
        ollamaModel: String = "llama3.2:3b",
        claudeModel: String = "claude-sonnet-4-20250514",
        openAIModel: String = "gpt-4o",
        groqModel: String = "llama-3.1-8b-instant",
        grokModel: String = "grok-3-latest",
        geminiModel: String = "gemini-2.5-flash",
        provider: LLMProvider = .ollama,
        yoloMode: Bool = false,
        bridgeWebSocketURL: String = "ws://localhost:8765"
    ) {
        self.systemPrompt = systemPrompt
        self.claudeAPIKey = claudeAPIKey
        self.openAIAPIKey = openAIAPIKey
        self.groqAPIKey = groqAPIKey
        self.grokAPIKey = grokAPIKey
        self.geminiAPIKey = geminiAPIKey
        self.ollamaEndpoint = ollamaEndpoint
        self.ollamaModel = ollamaModel
        self.claudeModel = claudeModel
        self.openAIModel = openAIModel
        self.groqModel = groqModel
        self.grokModel = grokModel
        self.geminiModel = geminiModel
        self.provider = provider
        self.yoloMode = yoloMode
        self.bridgeWebSocketURL = bridgeWebSocketURL
    }

    var routerConfiguration: LLMRouterConfiguration {
        LLMRouterConfiguration(
            provider: provider,
            systemPrompt: systemPrompt,
            yoloMode: yoloMode,
            bridgeWebSocketURL: bridgeWebSocketURL,
            claudeAPIKey: claudeAPIKey,
            openAIAPIKey: openAIAPIKey,
            groqAPIKey: groqAPIKey,
            grokAPIKey: grokAPIKey,
            geminiAPIKey: geminiAPIKey,
            ollamaEndpoint: ollamaEndpoint,
            ollamaModel: ollamaModel,
            claudeModel: claudeModel,
            openAIModel: openAIModel,
            groqModel: groqModel,
            grokModel: grokModel,
            geminiModel: geminiModel
        )
    }
}

@MainActor
final class BrainChatCoordinator {
    let store: ConversationStore
    let voiceManager: VoiceManager
    let speechManager: SpeechManager
    let llmRouter: LLMRouter
    let codeAssistant: CodeAssistant

    var configuration: AIServiceConfig
    var autoSpeak = true
    var continuousListening = false

    init(
        store: ConversationStore,
        voiceManager: VoiceManager,
        speechManager: SpeechManager,
        llmRouter: LLMRouter,
        codeAssistant: CodeAssistant,
        configuration: AIServiceConfig = AIServiceConfig()
    ) {
        self.store = store
        self.voiceManager = voiceManager
        self.speechManager = speechManager
        self.llmRouter = llmRouter
        self.codeAssistant = codeAssistant
        self.configuration = configuration

        self.speechManager.onTranscriptFinalized = { [weak self] transcript in
            self?.handleTranscript(transcript)
        }
    }

    convenience init(configuration: AIServiceConfig = AIServiceConfig()) {
        self.init(
            store: ConversationStore(),
            voiceManager: VoiceManager(),
            speechManager: SpeechManager(),
            llmRouter: LLMRouter(),
            codeAssistant: CodeAssistant(),
            configuration: configuration
        )
    }

    func sendUserMessage(_ text: String, completion: ((String) -> Void)? = nil) {
        store.addMessage(role: .user, content: text)
        store.isProcessing = true
        let history = store.recentConversation
        let routerConfig = configuration.routerConfiguration

        Task {
            let response = await llmRouter.streamReply(history: history, configuration: routerConfig) { _ in }
            store.isProcessing = false
            store.addMessage(role: .assistant, content: response)
            if autoSpeak {
                voiceManager.speak(response)
            }
            if continuousListening {
                speechManager.startListening()
            }
            completion?(response)
        }
    }

    func handleTranscript(_ transcript: String) {
        sendUserMessage(transcript)
    }

    func runCopilotWorkflow(prompt: String, completion: @escaping @Sendable (AssistantResponse) -> Void) {
        store.addMessage(role: .user, content: prompt)
        store.isProcessing = true
        codeAssistant.process(prompt) { [weak self] response in
            DispatchQueue.main.async {
                self?.store.isProcessing = false
                self?.store.addMessage(role: .assistant, content: response.text)
                completion(response)
            }
        }
    }
}
