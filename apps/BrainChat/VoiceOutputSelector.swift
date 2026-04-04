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
        guard engine.requiresAPIKey else { return true }
        switch engine {
        case .cartesia:
            return !settings.claudeAPIKey.isEmpty // Cartesia key loaded alongside others
        case .elevenLabs:
            return !settings.openAIKey.isEmpty // Placeholder until dedicated key added
        default:
            return true
        }
    }

    private func accessibilityHint(for engine: VoiceOutputEngine) -> String {
        if !isEngineAvailable(engine) {
            return "Unavailable until an API key is configured"
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
