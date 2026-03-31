import SwiftUI

/// A picker to choose between speech-to-text engines
/// Similar to LLMSelector but for voice input
struct SpeechEngineSelector: View {
    @EnvironmentObject var settings: AppSettings
    @State private var isExpanded = false
    
    var body: some View {
        Menu {
            ForEach(SpeechEngine.allCases) { engine in
                Button(action: { selectEngine(engine) }) {
                    HStack {
                        Image(systemName: engine.icon)
                        VStack(alignment: .leading) {
                            Text(engine.rawValue)
                            Text(engine.description)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        if settings.speechEngine == engine {
                            Image(systemName: "checkmark")
                        }
                    }
                }
                .disabled(engine.requiresAPIKey && settings.openAIKey.isEmpty)
                .accessibilityLabel(engine.rawValue)
                .accessibilityValue(settings.speechEngine == engine ? "Selected" : "")
                .accessibilityHint(engine.requiresAPIKey && settings.openAIKey.isEmpty ? "Unavailable until an OpenAI API key is added" : engine.description)
            }
        } label: {
            HStack(spacing: 4) {
                Image(systemName: settings.speechEngine.icon)
                    .foregroundColor(.blue)
                Text(shortName(settings.speechEngine))
                    .font(.caption)
                    .lineLimit(1)
                Image(systemName: "chevron.down")
                    .font(.caption2)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(Color.blue.opacity(0.1))
            .cornerRadius(6)
        }
        .accessibilityLabel("Speech engine: \(settings.speechEngine.rawValue)")
        .accessibilityHint("Double tap to change speech-to-text engine")
    }
    
    private func shortName(_ engine: SpeechEngine) -> String {
        switch engine {
        case .apple: return "Apple"
        case .whisperKit: return "faster-whisper"
        case .whisperAPI: return "Whisper API"
        case .whisperCpp: return "whisper.cpp"
        }
    }
    
    private func selectEngine(_ engine: SpeechEngine) {
        settings.speechEngine = engine
    }
}

#Preview {
    SpeechEngineSelector()
        .environmentObject(AppSettings())
}
