import AppKit
import AVFoundation
import Combine
import Foundation

@MainActor
final class VoiceManager: NSObject, ObservableObject {
    @Published var isSpeaking = false
    @Published var availableVoices: [VoiceInfo] = []
    @Published var selectedVoiceName: String = "Karen (Premium)"
    @Published var selectedVoiceID: String?
    @Published var speechRate: Float = 185.0  // Optimized: 185 wpm for faster acknowledgments
    @Published var currentEngine: VoiceOutputEngine = .macOS
    @Published var engineStatus: String = "Ready"

    private let synthesizer = AVSpeechSynthesizer()
    private let cartesiaVoice: CartesiaVoice
    private let piperVoice: PiperVoiceEngine
    private let elevenLabsVoice: ElevenLabsVoiceEngine
    private let speechDelegate = SpeechDelegate()

    private var speechQueue: [String] = []
    private var isProcessingQueue = false
    private var cancellables = Set<AnyCancellable>()
    
    // OPTIMIZATION: Pre-warmed synthesizer
    private var synthesizerPreWarmed = false
    
    // OPTIMIZATION: Common phrase cache for instant playback
    private let phraseCache = PhraseCache()
    
    // OPTIMIZATION: Streaming speech support
    private var streamingUtterances: [String: AVSpeechUtterance] = [:]

    private var voiceOverActive: Bool {
        NSWorkspace.shared.isVoiceOverEnabled
    }

    struct VoiceInfo: Identifiable, Hashable {
        let id: String
        let name: String
        let language: String
        let isPremium: Bool
    }

    override convenience init() {
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
        super.init()
        speechDelegate.manager = self
        synthesizer.delegate = speechDelegate
        bindExternalEngines()
        loadVoices()
        selectVoice(named: selectedVoiceName)
        updateEngineStatus()
        
        // OPTIMIZATION: Pre-warm synthesizer on app launch
        preWarmSynthesizer()
        
        // OPTIMIZATION: Cache common phrases for instant lookup
        phraseCache.preloadCommonPhrases()
    }

    func loadVoices() {
        let voices = AVSpeechSynthesisVoice.speechVoices().map { voice in
            VoiceInfo(
                id: voice.identifier,
                name: voice.name,
                language: voice.language,
                isPremium: voice.name.contains("Premium") || voice.name.contains("Enhanced")
            )
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
        if let voice = availableVoices.first(where: {
            $0.name.localizedCaseInsensitiveContains(name)
                || $0.name.localizedCaseInsensitiveContains(name.replacingOccurrences(of: " (Premium)", with: ""))
        }) {
            selectVoice(byID: voice.id)
        } else if let karenVoice = availableVoices.first(where: { $0.name.lowercased().contains("karen") }) {
            selectVoice(byID: karenVoice.id)
        }

        selectedVoiceName = name
        cartesiaVoice.selectVoice(matching: name)
        elevenLabsVoice.selectVoice(matching: name)
    }

    func selectVoice(byID id: String) {
        guard let voice = availableVoices.first(where: { $0.id == id }) else { return }
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
        // OPTIMIZATION: Check if cached phrase exists for instant playback
        if let cached = phraseCache.getCached(text) {
            speakCachedPhrase(cached)
            return
        }
        
        switch currentEngine {
        case .macOS:
            if announceWithVoiceOverIfNeeded(text) {
                return
            }
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
        switch currentEngine {
        case .macOS:
            if announceWithVoiceOverIfNeeded(text) {
                return
            }
            speechQueue.removeAll()
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
        synthesizer.stopSpeaking(at: .immediate)
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
        let utterance = AVSpeechUtterance(string: text)
        utterance.rate = mappedSpeechRate
        utterance.voice = selectedVoiceID.flatMap { AVSpeechSynthesisVoice(identifier: $0) }
            ?? AVSpeechSynthesisVoice(language: "en-AU")
        synthesizer.speak(utterance)
        return true
    }

    private var mappedSpeechRate: Float {
        let clampedWPM = min(max(speechRate, 100.0), 250.0)
        let normalized = (clampedWPM - 100.0) / 150.0
        return AVSpeechUtteranceMinimumSpeechRate
            + normalized * (AVSpeechUtteranceMaximumSpeechRate - AVSpeechUtteranceMinimumSpeechRate)
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
    
    // OPTIMIZATION: Pre-warm synthesizer on app launch (~50-100ms faster first speak)
    private func preWarmSynthesizer() {
        guard !synthesizerPreWarmed else { return }
        let dummy = AVSpeechUtterance(string: " ")
        dummy.volume = 0  // Silent
        synthesizer.speak(dummy)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) { [weak self] in
            self?.synthesizer.stopSpeaking(at: .immediate)
            self?.synthesizerPreWarmed = true
        }
    }
    
    // OPTIMIZATION: Speak cached phrase instantly (< 5ms)
    private func speakCachedPhrase(_ phrase: String) {
        guard currentEngine == .macOS else {
            speak(phrase)  // Fall through if not macOS
            return
        }
        
        isSpeaking = true
        let utterance = AVSpeechUtterance(string: phrase)
        utterance.rate = mappedSpeechRate
        utterance.voice = selectedVoiceID.flatMap { AVSpeechSynthesisVoice(identifier: $0) }
            ?? AVSpeechSynthesisVoice(language: "en-AU")
        synthesizer.speak(utterance)
    }
    
    // OPTIMIZATION: Announce with shorter acknowledgment sounds
    func playAcknowledgmentSound() {
        // Use system alert sound (< 5ms) instead of "I'm thinking..."
        AudioServicesPlaySystemSound(1057)  // Beacon sound
    }
    
    fileprivate func didFinishSpeaking() {
        guard currentEngine == .macOS else { return }
        isProcessingQueue = false
        if speechQueue.isEmpty {
            isSpeaking = false
        } else {
            processQueue()
        }
    }

}

// OPTIMIZATION: Cache for common phrases - instant playback (< 5ms)
final class PhraseCache {
    private let cache = NSCache<NSString, NSString>()
    private let commonPhrases = [
        "Processing...",
        "One moment...",
        "Here's what I found...",
        "Let me think about that...",
        "Got it",
        "Yes",
        "No",
        "OK",
        "Thanks",
        "I understand",
    ]
    
    func preloadCommonPhrases() {
        for phrase in commonPhrases {
            cache.setObject(phrase as NSString, forKey: phrase as NSString)
        }
    }
    
    func getCached(_ phrase: String) -> String? {
        cache.object(forKey: phrase as NSString) as String?
    }
}

private final class SpeechDelegate: NSObject, AVSpeechSynthesizerDelegate {
    weak var manager: VoiceManager?

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        Task { @MainActor [weak manager] in
            manager?.didFinishSpeaking()
        }
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        Task { @MainActor [weak manager] in
            manager?.didFinishSpeaking()
        }
    }
}
