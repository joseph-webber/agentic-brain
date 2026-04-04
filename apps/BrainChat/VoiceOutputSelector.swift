import SwiftUI

/// A picker to choose the text-to-speech output engine
/// Mirrors SpeechEngineSelector pattern for voice input
struct VoiceOutputSelector: View {
    @EnvironmentObject var settings: AppSettings

    var body: some View {
        Menu {
            ForEach(VoiceOutputEngine.allCases) { engine in
                Button(action: { settings.voiceOutputEngine = engine }) {
                    HStack {
                        Image(systemName: engine.icon)
                        VStack(alignment: .leading) {
                            HStack {
                                Text(engine.rawValue)
                                if engine.crossPlatform {
                                    Text("🌐")
                                        .accessibilityHidden(true)
                                }
                            }
                            Text(engine.description)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        if settings.voiceOutputEngine == engine {
                            Image(systemName: "checkmark")
                        }
                    }
                }
                .disabled(!isEngineAvailable(engine))
                .accessibilityLabel(engine.rawValue)
                .accessibilityValue(settings.voiceOutputEngine == engine ? "Selected" : "")
                .accessibilityHint(accessibilityHint(for: engine))
            }
        } label: {
            HStack(spacing: 4) {
                Image(systemName: settings.voiceOutputEngine.icon)
                    .foregroundColor(.purple)
                Text(shortName(settings.voiceOutputEngine))
                    .font(.caption)
                    .lineLimit(1)
                Image(systemName: "chevron.down")
                    .font(.caption2)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(Color.purple.opacity(0.1))
            .cornerRadius(6)
        }
        .accessibilityLabel("Voice output: \(settings.voiceOutputEngine.rawValue)")
        .accessibilityHint("Double tap to change text-to-speech engine")
    }

    private func shortName(_ engine: VoiceOutputEngine) -> String {
        switch engine {
        case .macOS: return "macOS"
        case .cartesia: return "Cartesia"
        case .piper: return "Piper"
        case .elevenLabs: return "ElevenLabs"
        }
    }

    private func isEngineAvailable(_ engine: VoiceOutputEngine) -> Bool {
        switch engine {
        case .macOS:
            return true
        case .cartesia:
            return APIKeyManager.shared.hasKey(for: "cartesia")
        case .piper:
            return ShellPiperCommandRunner().isAvailable
        case .elevenLabs:
            return APIKeyManager.shared.hasKey(for: "elevenlabs")
        }
    }

    private func accessibilityHint(for engine: VoiceOutputEngine) -> String {
        if !isEngineAvailable(engine) {
            switch engine {
            case .cartesia:
                return "Unavailable until a Cartesia API key is configured"
            case .piper:
                return "Unavailable until Piper and a compatible voice model are installed"
            case .elevenLabs:
                return "Unavailable until an ElevenLabs API key is configured"
            case .macOS:
                return engine.description
            }
        }
        var hint = engine.description
        if engine.crossPlatform {
            hint += ". Works on Mac, Windows, and Linux"
        }
        if engine.isOffline {
            hint += ". Works offline"
        }
        return hint
    }
}

#Preview {
    VoiceOutputSelector()
        .environmentObject(AppSettings())
}
