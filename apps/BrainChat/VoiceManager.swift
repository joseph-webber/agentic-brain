import AppKit
import AVFoundation
import Combine
import Foundation

@MainActor
final class VoiceManager: ObservableObject {
    @Published var isSpeaking = false
    @Published var availableVoices: [VoiceInfo] = []
    @Published var selectedVoiceName: String = "Karen (Premium)"
    @Published var speechRate: Float = 160.0

    private let synthesizer = NSSpeechSynthesizer()
    private var delegate: SpeechDelegate?
    private var speechQueue: [String] = []
    private var isProcessingQueue = false

    struct VoiceInfo: Identifiable, Hashable {
        let id: String
        let name: String
        let language: String
        let isPremium: Bool
    }

    init() {
        delegate = SpeechDelegate(manager: self)
        synthesizer.delegate = delegate
        loadVoices()
        selectVoice(named: selectedVoiceName)
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
            if left.name.contains("Karen") && !right.name.contains("Karen") { return true }
            if !left.name.contains("Karen") && right.name.contains("Karen") { return false }
            return left.name < right.name
        }
    }

    func selectVoice(named name: String) {
        selectedVoiceName = name
        if let voice = availableVoices.first(where: {
            $0.name.localizedCaseInsensitiveContains(name) ||
            $0.name.localizedCaseInsensitiveContains(name.replacingOccurrences(of: " (Premium)", with: ""))
        }) {
            synthesizer.setVoice(NSSpeechSynthesizer.VoiceName(rawValue: voice.id))
        } else if let karenVoice = NSSpeechSynthesizer.availableVoices.first(where: { $0.rawValue.lowercased().contains("karen") }) {
            synthesizer.setVoice(karenVoice)
        }
    }

    func speak(_ text: String) {
        speechQueue.append(text)
        processQueue()
    }

    func speakImmediately(_ text: String) {
        stop()
        speechQueue.removeAll()
        synthesizer.rate = speechRate
        synthesizer.startSpeaking(text)
        isSpeaking = true
    }

    func stop() {
        synthesizer.stopSpeaking()
        speechQueue.removeAll()
        isProcessingQueue = false
        isSpeaking = false
    }

    private func processQueue() {
        guard !isProcessingQueue, !speechQueue.isEmpty else { return }
        isProcessingQueue = true
        let text = speechQueue.removeFirst()
        synthesizer.rate = speechRate
        synthesizer.startSpeaking(text)
        isSpeaking = true
    }

    fileprivate func didFinishSpeaking() {
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
        Task { @MainActor in
            manager?.didFinishSpeaking()
        }
    }
}
