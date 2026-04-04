import Foundation

// MARK: - Voice Output (TTS) Engines
enum VoiceOutputEngine: String, CaseIterable, Identifiable {
    case macOS = "macOS Native"
    case cartesia = "Cartesia"
    case piper = "Piper TTS"
    case elevenLabs = "ElevenLabs"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .macOS: return "apple.logo"
        case .cartesia: return "bolt.fill"
        case .piper: return "cpu"
        case .elevenLabs: return "star.fill"
        }
    }

    var description: String {
        switch self {
        case .macOS: return "AVSpeechSynthesizer - Karen voice, works offline"
        case .cartesia: return "Cloud TTS - high quality, low latency"
        case .piper: return "Local neural TTS - cross-platform, offline, open source"
        case .elevenLabs: return "Cloud TTS - premium quality voices"
        }
    }

    var requiresAPIKey: Bool {
        switch self {
        case .macOS, .piper: return false
        case .cartesia, .elevenLabs: return true
        }
    }

    var isOffline: Bool {
        switch self {
        case .macOS, .piper: return true
        case .cartesia, .elevenLabs: return false
        }
    }

    var crossPlatform: Bool {
        switch self {
        case .macOS: return false
        case .cartesia, .piper, .elevenLabs: return true
        }
    }

    static var platformDefault: VoiceOutputEngine {
        #if os(macOS)
        return .macOS
        #else
        return .piper
        #endif
    }
}

// MARK: - Speech-to-Text Engines
enum SpeechEngine: String, CaseIterable, Identifiable {
    case appleDictation = "apple"
    case whisperKit = "whisperKit"
    case whisperAPI = "whisperAPI"
    case whisperCpp = "whisperCpp"

    init?(storedValue: String) {
        switch storedValue {
        case Self.appleDictation.rawValue, "Apple Dictation":
            self = .appleDictation
        case Self.whisperKit.rawValue, "WhisperKit (Local)", "faster-whisper (Local)":
            self = .whisperKit
        case Self.whisperAPI.rawValue, "OpenAI Whisper API":
            self = .whisperAPI
        case Self.whisperCpp.rawValue, "whisper.cpp (Local)":
            self = .whisperCpp
        default:
            return nil
        }
    }

    var id: String { rawValue }

    var description: String {
        switch self {
        case .appleDictation:
            return "Apple Dictation"
        case .whisperKit:
            return "faster-whisper (Local)"
        case .whisperAPI:
            return "OpenAI Whisper API"
        case .whisperCpp:
            return "whisper.cpp (Local)"
        }
    }

    var detail: String {
        switch self {
        case .appleDictation:
            return "Built-in macOS speech recognition."
        case .whisperKit:
            return "Local Python faster-whisper bridge for private offline transcription."
        case .whisperAPI:
            return "Cloud transcription using your OpenAI API key."
        case .whisperCpp:
            return "Local whisper.cpp transcription using a native model file."
        }
    }

    var shortName: String {
        switch self {
        case .appleDictation:
            return "Apple"
        case .whisperKit:
            return "faster-whisper"
        case .whisperAPI:
            return "Whisper API"
        case .whisperCpp:
            return "whisper.cpp"
        }
    }

    var icon: String {
        switch self {
        case .appleDictation:
            return "apple.logo"
        case .whisperKit:
            return "cpu"
        case .whisperAPI:
            return "cloud"
        case .whisperCpp:
            return "terminal"
        }
    }

    var requiresAPIKey: Bool {
        self == .whisperAPI
    }

    var isLocal: Bool {
        self == .whisperKit || self == .whisperCpp
    }
}
