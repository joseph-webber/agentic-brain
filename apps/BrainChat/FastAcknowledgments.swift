import AVFoundation
import Combine
import Foundation

/// OPTIMIZATION: Ultra-fast acknowledgment system for instant feedback
/// Uses pre-cached audio and system sounds instead of TTS synthesis
@MainActor
final class FastAcknowledgments: ObservableObject {
    enum AcknowledgmentType {
        case thinking      // "I'm thinking..."
        case processing    // "Processing..."
        case searching     // "Searching..."
        case loading       // "Loading..."
        case ready         // "Ready"
        case success       // "Got it"
        case error         // "Error"
    }
    
    private let audioSession = AVAudioSession.sharedInstance()
    @Published private(set) var isPlaying = false
    
    private let systemSoundIDs: [AcknowledgmentType: SystemSoundID] = [
        .thinking:   1054,  // Pop sound
        .processing: 1053,  // Morse code
        .searching:  1057,  // Beacon
        .loading:    1104,  // Glass
        .ready:      1103,  // Bell
        .success:    1051,  // Glass bell
        .error:      1050,  // Glass error
    ]
    
    init() {
        try? audioSession.setCategory(.playback, options: .duckOthers)
    }
    
    /// Play system sound acknowledgment (< 5ms latency)
    /// Use this instead of "I'm thinking..." for instant feedback
    func playAcknowledgment(_ type: AcknowledgmentType) {
        guard let soundID = systemSoundIDs[type] else { return }
        
        isPlaying = true
        AudioServicesAddSystemSoundCompletion(soundID, nil, nil, { _, _ in
            Task { @MainActor [weak self] in
                self?.isPlaying = false
            }
        }, nil)
        AudioServicesPlaySystemSound(soundID)
    }
    
    /// Fast microphone click for "listening" feedback (< 2ms)
    func playMicClick() {
        AudioServicesPlaySystemSound(1113)  // Tock sound
    }
    
    /// Success fanfare for confirmations (< 10ms)
    func playSuccess() {
        playAcknowledgment(.success)
    }
    
    /// Error buzz (< 5ms)
    func playError() {
        playAcknowledgment(.error)
    }
}
