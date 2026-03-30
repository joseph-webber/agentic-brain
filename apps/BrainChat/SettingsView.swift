import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var voiceManager: VoiceManager
    @EnvironmentObject var llmRouter: LLMRouter
    @State private var showingClaudeKey = false
    @State private var showingOpenAIKey = false

    var body: some View {
        TabView {
            Form {
                Toggle("Continuous Listening Mode", isOn: $settings.continuousListening)
                Toggle("Auto-Speak Responses", isOn: $settings.autoSpeak)
                Toggle("YOLO Mode", isOn: $llmRouter.yoloMode)
            }
            .formStyle(.grouped)
            .tabItem { Label("General", systemImage: "gear") }

            Form {
                Picker("Voice", selection: $settings.voiceName) {
                    ForEach(voiceManager.availableVoices) { voice in
                        Text(voice.name).tag(voice.name)
                    }
                }
                .onChange(of: settings.voiceName) { _, newValue in voiceManager.selectVoice(named: newValue) }

                Slider(value: $settings.speechRate, in: 100...250, step: 5) { Text("Speech Rate") }
                    .onChange(of: settings.speechRate) { _, newValue in voiceManager.speechRate = Float(newValue) }

                Button("Test Voice") { voiceManager.speakImmediately("Brain Chat voice bridge is ready.") }
            }
            .formStyle(.grouped)
            .tabItem { Label("Voice", systemImage: "waveform") }

            Form {
                TextField("Voice Bridge WebSocket", text: $settings.bridgeWebSocketURL)
                    .textFieldStyle(.roundedBorder)
                VStack(alignment: .leading) {
                    Text("Claude API Key")
                    if showingClaudeKey { TextField("Anthropic API key", text: $settings.claudeAPIKey).textFieldStyle(.roundedBorder) }
                    else { SecureField("Anthropic API key", text: $settings.claudeAPIKey).textFieldStyle(.roundedBorder) }
                    Button(showingClaudeKey ? "Hide" : "Show") { showingClaudeKey.toggle() }
                }
                VStack(alignment: .leading) {
                    Text("OpenAI API Key")
                    if showingOpenAIKey { TextField("OpenAI API key", text: $settings.openAIKey).textFieldStyle(.roundedBorder) }
                    else { SecureField("OpenAI API key", text: $settings.openAIKey).textFieldStyle(.roundedBorder) }
                    Button(showingOpenAIKey ? "Hide" : "Show") { showingOpenAIKey.toggle() }
                }
                Button("Save Keys") { settings.saveAPIKeys() }
                Button("Reload Keys") { settings.loadAPIKeys() }
                Button("Clear Keys") { settings.clearAPIKeys() }
                TextField("Ollama Endpoint", text: $settings.apiEndpoint).textFieldStyle(.roundedBorder)
                TextField("Ollama Model", text: $settings.modelName).textFieldStyle(.roundedBorder)
            }
            .formStyle(.grouped)
            .tabItem { Label("API", systemImage: "key") }
        }
        .padding(20)
    }
}
