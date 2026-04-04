import AppKit
import AVFoundation
import Combine
import Foundation

@MainActor
final class VoiceManager: ObservableObject {
    @Published var isSpeaking = false
    @Published var availableVoices: [VoiceInfo] = []
    @Published var selectedVoiceName: String = "Karen (Premium)"
    @Published var selectedVoiceID: String?
    @Published var speechRate: Float = 160.0
    @Published var currentEngine: VoiceOutputEngine = .macOS
    @Published var engineStatus: String = "Ready"

    private let synthesizer = NSSpeechSynthesizer()
    private let cartesiaVoice: CartesiaVoice
    private let piperVoice: PiperVoiceEngine
    private let elevenLabsVoice: ElevenLabsVoiceEngine

    private var delegate: SpeechDelegate?
    private var speechQueue: [String] = []
    private var isProcessingQueue = false
    private var currentUtteranceID: UUID?
    private var cancellables = Set<AnyCancellable>()

    private var voiceOverActive: Bool {
        NSWorkspace.shared.isVoiceOverEnabled
    }

    struct VoiceInfo: Identifiable, Hashable {
        let id: String
        let name: String
        let language: String
        let isPremium: Bool
    }

    convenience init() {
        self.init(cartesiaVoice: CartesiaVoice(), piperVoice: PiperVoiceEngine(), elevenLabsVoice: ElevenLabsVoiceEngine())
    }

    init(
        cartesiaVoice: CartesiaVoice,
        piperVoice: PiperVoiceEngine,
        elevenLabsVoice: ElevenLabsVoiceEngine
    ) {
        self.cartesiaVoice = cartesiaVoice
        self.piperVoice = piperVoice
        self.elevenLabsVoice = elevenLabsVoice
        delegate = SpeechDelegate(manager: self)
        synthesizer.delegate = delegate
        bindExternalEngines()
        loadVoices()
        selectVoice(named: selectedVoiceName)
        updateEngineStatus()
    }

    func loadVoices() {
        let voices = NSSpeechSynthesizer.availableVoices.compactMap { voiceID -> VoiceInfo? in
            guard
                let attributes = NSSpeechSynthesizer.attributes(forVoice: voiceID) as? [String: Any],
                let name = attributes[NSSpeechSynthesizer.VoiceAttributeKey.name.rawValue] as? String,
                let language = attributes[NSSpeechSynthesizer.VoiceAttributeKey.localeIdentifier.rawValue] as? String
            else {
                return nil
            }
            return VoiceInfo(id: voiceID.rawValue, name: name, language: language, isPremium: name.contains("Premium") || name.contains("Enhanced"))
        }

        availableVoices = voices.sorted { left, right in
            let leftIsKaren = left.name.lowercased().contains("karen")
            let rightIsKaren = right.name.lowercased().contains("karen")
            if leftIsKaren != rightIsKaren { return leftIsKaren }

            let leftIsAustralian = left.language.replacingOccurrences(of: "_", with: "-").lowercased() == "en-au"
            let rightIsAustralian = right.language.replacingOccurrences(of: "_", with: "-").lowercased() == "en-au"
            if leftIsAustralian != rightIsAustralian { return leftIsAustralian }

            return left.name < right.name
        }
    }

    func selectVoice(named name: String) {
        selectedVoiceName = name
        if let voice = availableVoices.first(where: {
            $0.name.localizedCaseInsensitiveContains(name)
                || $0.name.localizedCaseInsensitiveContains(name.replacingOccurrences(of: " (Premium)", with: ""))
        }) {
            selectVoice(byID: voice.id)
        } else if let karenVoice = availableVoices.first(where: { $0.name.lowercased().contains("karen") }) {
            selectVoice(byID: karenVoice.id)
        }

        cartesiaVoice.selectVoice(matching: selectedVoiceName)
        elevenLabsVoice.selectVoice(matching: selectedVoiceName)
    }

    func selectVoice(byID id: String) {
        guard let voice = availableVoices.first(where: { $0.id == id }) else { return }
        synthesizer.setVoice(NSSpeechSynthesizer.VoiceName(rawValue: voice.id))
        selectedVoiceID = voice.id
        selectedVoiceName = voice.name
    }

    func setOutputEngine(_ engine: VoiceOutputEngine) {
        currentEngine = engine
        updateEngineStatus()
    }

    func refreshEngineStatus() {
        updateEngineStatus()
    }

    func speak(_ text: String) {
        if announceWithVoiceOverIfNeeded(text) {
            return
        }

        switch currentEngine {
        case .macOS:
            speechQueue.append(text)
            processQueue()
        case .cartesia:
            cartesiaVoice.enqueue(text, voiceID: cartesiaVoice.selectedVoiceID)
        case .piper:
            piperVoice.enqueue(text, preferredVoiceName: selectedVoiceName)
        case .elevenLabs:
            elevenLabsVoice.enqueue(text, preferredVoiceName: selectedVoiceName)
        }
    }

    func speakImmediately(_ text: String) {
        stop()
        if announceWithVoiceOverIfNeeded(text) {
            return
        }

        switch currentEngine {
        case .macOS:
            speechQueue.removeAll()
            synthesizer.rate = speechRate
            isProcessingQueue = true
            let started = startSpeaking(text)
            if !started {
                isSpeaking = false
                isProcessingQueue = false
                processQueue()
                return
            }
            isSpeaking = true
        case .cartesia:
            cartesiaVoice.enqueue(text, voiceID: cartesiaVoice.selectedVoiceID)
        case .piper:
            piperVoice.speakImmediately(text, preferredVoiceName: selectedVoiceName)
        case .elevenLabs:
            elevenLabsVoice.speakImmediately(text, preferredVoiceName: selectedVoiceName)
        }
    }

    func stop() {
        currentUtteranceID = nil
        synthesizer.stopSpeaking()
        speechQueue.removeAll()
        isProcessingQueue = false
        cartesiaVoice.cancelCurrentSpeech(clearQueue: true)
        piperVoice.cancelCurrentSpeech(clearQueue: true)
        elevenLabsVoice.cancelCurrentSpeech(clearQueue: true)
        isSpeaking = false
    }

    private func bindExternalEngines() {
        cartesiaVoice.$isSpeaking
            .sink { [weak self] speaking in
                guard let self, self.currentEngine == .cartesia else { return }
                self.isSpeaking = speaking
            }
            .store(in: &cancellables)

        cartesiaVoice.$statusMessage
            .sink { [weak self] status in
                guard let self, self.currentEngine == .cartesia else { return }
                self.engineStatus = status
            }
            .store(in: &cancellables)

        piperVoice.$isSpeaking
            .sink { [weak self] speaking in
                guard let self, self.currentEngine == .piper else { return }
                self.isSpeaking = speaking
            }
            .store(in: &cancellables)

        piperVoice.$statusMessage
            .sink { [weak self] status in
                guard let self, self.currentEngine == .piper else { return }
                self.engineStatus = status
            }
            .store(in: &cancellables)

        elevenLabsVoice.$isSpeaking
            .sink { [weak self] speaking in
                guard let self, self.currentEngine == .elevenLabs else { return }
                self.isSpeaking = speaking
            }
            .store(in: &cancellables)

        elevenLabsVoice.$statusMessage
            .sink { [weak self] status in
                guard let self, self.currentEngine == .elevenLabs else { return }
                self.engineStatus = status
            }
            .store(in: &cancellables)
    }

    private func updateEngineStatus() {
        cartesiaVoice.refreshConfiguration()
        elevenLabsVoice.refreshConfiguration()

        switch currentEngine {
        case .macOS:
            engineStatus = "Ready"
            isSpeaking = isProcessingQueue || synthesizer.isSpeaking
        case .cartesia:
            engineStatus = cartesiaVoice.hasStoredAPIKey ? "Ready" : cartesiaVoice.statusMessage
            isSpeaking = cartesiaVoice.isSpeaking
        case .piper:
            engineStatus = piperVoice.isAvailable ? "Ready" : piperVoice.unavailabilityMessage
            isSpeaking = piperVoice.isSpeaking
        case .elevenLabs:
            engineStatus = elevenLabsVoice.hasStoredAPIKey ? "Ready" : elevenLabsVoice.statusMessage
            isSpeaking = elevenLabsVoice.isSpeaking
        }
    }

    private func processQueue() {
        guard currentEngine == .macOS else { return }
        guard !isProcessingQueue, !speechQueue.isEmpty else { return }

        if voiceOverActive {
            let text = speechQueue.removeFirst()
            if announceWithVoiceOverIfNeeded(text) {
                if speechQueue.isEmpty {
                    isSpeaking = false
                } else {
                    processQueue()
                }
            }
            return
        }

        isProcessingQueue = true
        let text = speechQueue.removeFirst()
        synthesizer.rate = speechRate
        let started = startSpeaking(text)
        if !started {
            isSpeaking = false
            isProcessingQueue = false
            processQueue()
            return
        }
        isSpeaking = true
    }

    @discardableResult
    private func startSpeaking(_ text: String) -> Bool {
        let utteranceID = UUID()
        currentUtteranceID = utteranceID
        let started = synthesizer.startSpeaking(text)
        if !started, currentUtteranceID == utteranceID {
            currentUtteranceID = nil
        }
        return started
    }

    fileprivate func currentSpeechUtteranceID() -> UUID? {
        currentUtteranceID
    }

    private func announceWithVoiceOverIfNeeded(_ text: String) -> Bool {
        guard voiceOverActive else { return false }

        let userInfo: [NSAccessibility.NotificationUserInfoKey: Any] = [
            .announcement: text,
            .priority: NSAccessibilityPriorityLevel.high.rawValue,
        ]
        NSAccessibility.post(element: NSApp as Any, notification: .announcementRequested, userInfo: userInfo)
        isSpeaking = false
        isProcessingQueue = false
        return true
    }

    fileprivate func didFinishSpeaking(for utteranceID: UUID?) {
        guard let utteranceID, utteranceID == currentUtteranceID else { return }

        currentUtteranceID = nil
        isProcessingQueue = false
        if speechQueue.isEmpty {
            isSpeaking = false
        } else {
            processQueue()
        }
    }
}

private final class SpeechDelegate: NSObject, NSSpeechSynthesizerDelegate {
    weak var manager: VoiceManager?

    init(manager: VoiceManager) {
        self.manager = manager
    }

    func speechSynthesizer(_ sender: NSSpeechSynthesizer, didFinishSpeaking finishedSpeaking: Bool) {
        let utteranceID = manager?.currentSpeechUtteranceID()
        Task { @MainActor in
            manager?.didFinishSpeaking(for: utteranceID)
        }
    }
}
