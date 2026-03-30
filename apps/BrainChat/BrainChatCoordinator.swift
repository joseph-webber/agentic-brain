import Foundation

@MainActor
final class BrainChatCoordinator {
    let store: ConversationStore
    let voiceManager: VoiceManager
    let speechManager: SpeechManager
    let aiManager: AIManager
    let codeAssistant: CodeAssistant

    var configuration: AIServiceConfig
    var autoSpeak = true
    var continuousListening = false

    init(
        store: ConversationStore,
        voiceManager: VoiceManager,
        speechManager: SpeechManager,
        aiManager: AIManager,
        codeAssistant: CodeAssistant,
        configuration: AIServiceConfig = AIServiceConfig()
    ) {
        self.store = store
        self.voiceManager = voiceManager
        self.speechManager = speechManager
        self.aiManager = aiManager
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
            aiManager: AIManager(),
            codeAssistant: CodeAssistant(),
            configuration: configuration
        )
    }

    func sendUserMessage(_ text: String, completion: ((String) -> Void)? = nil) {
        store.addMessage(role: .user, content: text)
        store.isProcessing = true

        aiManager.send(message: text, history: store.messages, config: configuration) { [weak self] response in
            guard let self else { return }
            DispatchQueue.main.async {
                self.store.isProcessing = false
                self.store.addMessage(role: .assistant, content: response.text)
                if self.autoSpeak {
                    self.voiceManager.speak(response.text)
                }
                if self.continuousListening {
                    self.speechManager.startListening()
                }
                completion?(response.text)
            }
        }
    }

    func handleTranscript(_ transcript: String) {
        sendUserMessage(transcript)
    }

    func runCopilotWorkflow(prompt: String, completion: @escaping (AssistantResponse) -> Void) {
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
