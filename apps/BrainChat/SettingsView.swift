import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var voiceManager: VoiceManager
    @EnvironmentObject var llmRouter: LLMRouter
    @State private var showingClaudeKey = false
    @State private var showingOpenAIKey = false
    @State private var showingGroqKey = false
    @State private var showClearKeysConfirmation = false

    var body: some View {
        TabView {
            // MARK: General tab
            Form {
                Toggle("Continuous Listening Mode", isOn: $settings.continuousListening)
                    .accessibilityHint("When enabled, the microphone stays on and transcribes continuously")

                Toggle("Auto-Speak Responses", isOn: $settings.autoSpeak)
                    .accessibilityHint("When enabled, Brain Chat reads every response aloud automatically")

                Toggle("YOLO Mode", isOn: $llmRouter.yoloMode)
                    .accessibilityHint("Autonomous mode: Brain Chat takes actions without asking for confirmation")

                Section("Layered Responses") {
                    LayerStrategyPicker(
                        strategy: Binding(
                            get: { settings.layeredStrategy },
                            set: { settings.layeredStrategy = $0 }
                        ),
                        layeredModeEnabled: $settings.layeredModeEnabled
                    )
                }
            }
            .formStyle(.grouped)
            .tabItem { Label("General", systemImage: "gear") }

            // MARK: Voice tab
            Form {
                Section("Voice Output Engine") {
                    HStack {
                        Text("TTS Engine")
                        Spacer()
                        VoiceOutputSelector()
                            .environmentObject(settings)
                    }
                    .accessibilityElement(children: .contain)
                    .accessibilityLabel("Text-to-speech engine selector")
                }

                Section("Voice Settings") {
                    Picker("Voice", selection: $settings.voiceName) {
                        ForEach(voiceManager.availableVoices) { voice in
                            Text(voice.name).tag(voice.name)
                        }
                    }
                    .accessibilityLabel("Voice selection")
                    .accessibilityHint("Choose the voice used for spoken responses")
                    .onChange(of: settings.voiceName) { _, newValue in
                        voiceManager.selectVoice(named: newValue)
                    }

                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text("Speech Rate")
                            Spacer()
                            Text("\(Int(settings.speechRate)) wpm")
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .monospacedDigit()
                        }
                        Slider(value: $settings.speechRate, in: 100...250, step: 5)
                            .accessibilityLabel("Speech rate")
                            .accessibilityValue("\(Int(settings.speechRate)) words per minute")
                            .accessibilityHint("Adjust how fast the voice speaks. Swipe right to increase speed.")
                            .onChange(of: settings.speechRate) { _, newValue in
                                voiceManager.speechRate = Float(newValue)
                            }
                    }

                    Button("Test Voice") {
                        voiceManager.speakImmediately("Brain Chat voice bridge is ready. Speech rate is \(Int(settings.speechRate)) words per minute.")
                    }
                    .accessibilityHint("Plays a sample sentence at the current speech rate and voice")
                }
            }
            .formStyle(.grouped)
            .tabItem { Label("Voice", systemImage: "waveform") }

            // MARK: API tab
            Form {
                Section("Voice Bridge") {
                    TextField("WebSocket URL", text: $settings.bridgeWebSocketURL)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Voice Bridge WebSocket URL")
                        .accessibilityHint("Address of the local voice bridge server, e.g. ws://localhost:8765")
                }

                Section("Groq (Instant Layer)") {
                    APIKeyField(
                        label: "Groq API Key",
                        placeholder: "Groq API key (groq.com)",
                        text: $settings.groqAPIKey,
                        isVisible: $showingGroqKey
                    )
                    .accessibilityElement(children: .contain)
                    .accessibilityLabel("Groq API key field for instant layer responses")
                }

                Section("Claude & OpenAI") {
                    APIKeyField(
                        label: "Claude API Key",
                        placeholder: "Anthropic API key",
                        text: $settings.claudeAPIKey,
                        isVisible: $showingClaudeKey
                    )
                    APIKeyField(
                        label: "OpenAI API Key",
                        placeholder: "OpenAI API key",
                        text: $settings.openAIKey,
                        isVisible: $showingOpenAIKey
                    )
                }

                Section {
                    Button("Save Keys") { settings.saveAPIKeys() }
                        .accessibilityHint("Saves all API keys securely to the system Keychain")

                    Button("Reload Keys") { settings.loadAPIKeys() }
                        .accessibilityHint("Loads API keys from the system Keychain")

                    Button("Clear All Keys", role: .destructive) {
                        showClearKeysConfirmation = true
                    }
                    .accessibilityHint("Removes all API keys from the Keychain. A confirmation will appear.")
                    .confirmationDialog(
                        "Clear all API keys?",
                        isPresented: $showClearKeysConfirmation,
                        titleVisibility: .visible
                    ) {
                        Button("Clear All Keys", role: .destructive) { settings.clearAPIKeys() }
                        Button("Cancel", role: .cancel) {}
                    } message: {
                        Text("This will remove all API keys from the Keychain. You will need to re-enter them.")
                    }
                }

                // Keychain status feedback (errors or success confirmations)
                if !settings.keychainStatusMessage.isEmpty {
                    Section {
                        HStack(spacing: 8) {
                            Image(systemName: settings.keychainStatusMessage.contains("saved") || settings.keychainStatusMessage.contains("removed") ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                                .foregroundColor(settings.keychainStatusMessage.contains("saved") || settings.keychainStatusMessage.contains("removed") ? .green : .orange)
                                .accessibilityHidden(true)
                            Text(settings.keychainStatusMessage)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel("Keychain status: \(settings.keychainStatusMessage)")
                }

                Section("Local Models") {
                    TextField("Ollama Endpoint", text: $settings.apiEndpoint)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Ollama endpoint URL")
                        .accessibilityHint("The HTTP address of your local Ollama server, e.g. http://localhost:11434/api/chat")

                    TextField("Ollama Model", text: $settings.modelName)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Ollama model name")
                        .accessibilityHint("The model to use, e.g. llama3.2:3b")
                }
            }
            .formStyle(.grouped)
            .tabItem { Label("API", systemImage: "key") }
        }
        .padding(20)
    }
}

// MARK: - Reusable API Key Field

/// A labelled field that can toggle between secure and visible entry.
/// All states are fully accessible via VoiceOver.
private struct APIKeyField: View {
    let label: String
    let placeholder: String
    @Binding var text: String
    @Binding var isVisible: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)

            HStack {
                if isVisible {
                    TextField(placeholder, text: $text)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel(label)
                } else {
                    SecureField(placeholder, text: $text)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel(label)
                }

                Button(action: { isVisible.toggle() }) {
                    Image(systemName: isVisible ? "eye.slash" : "eye")
                }
                .buttonStyle(.plain)
                .accessibilityLabel(isVisible ? "Hide \(label)" : "Show \(label)")
                .accessibilityHint(isVisible ? "Masks the key so it is not visible on screen" : "Reveals the key so you can read or edit it")
            }
        }
    }
}
