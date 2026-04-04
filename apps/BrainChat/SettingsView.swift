import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var voiceManager: VoiceManager
    @EnvironmentObject var llmRouter: LLMRouter
    @StateObject private var securityManager = SecurityManager.shared
    @State private var showingClaudeKey = false
    @State private var showingOpenAIKey = false
    @State private var showingGroqKey = false
    @State private var showingBackendAPIKey = false
    @State private var showingBackendBearerToken = false
    @State private var showClearKeysConfirmation = false

    var body: some View {
        TabView {
            // MARK: General tab
            Form {
                Section("Behavior Profile") {
                    Picker("Profile", selection: $settings.behaviorProfile) {
                        ForEach(BrainChatBehaviorProfile.allCases) { profile in
                            Text(profile.displayName).tag(profile)
                        }
                    }
                    .accessibilityLabel("Brain Chat behavior profile")
                    .accessibilityHint("Switch between beginner, developer, and enterprise behaviors")

                    Picker("Connectivity Mode", selection: $settings.agenticBrainMode) {
                        ForEach(AgenticBrainConnectionMode.allCases) { mode in
                            Text(mode.accessibilityLabel).tag(mode)
                        }
                    }
                    .accessibilityLabel("Agentic Brain connectivity mode")
                    .accessibilityHint("Choose airlocked, hybrid, or cloud mode")
                }

                Toggle("Continuous Listening Mode", isOn: $settings.continuousListening)
                    .accessibilityHint("When enabled, the microphone stays on and transcribes continuously")

                Toggle("Auto-Speak Responses", isOn: $settings.autoSpeak)
                    .accessibilityHint("When enabled, Brain Chat reads every response aloud automatically")

                Toggle("YOLO Mode", isOn: $llmRouter.yoloMode)
                    .accessibilityHint(
                        securityManager.canUseYolo()
                            ? "Autonomous mode: Brain Chat takes actions without asking for confirmation"
                            : "Unavailable outside Admin testing mode"
                    )
                    .disabled(!securityManager.canUseYolo())

                Section("Security Mode (Testing)") {
                    SecurityModeView(securityManager: securityManager)
                }

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

                Section("Agentic Brain Backend") {
                    Toggle("Enable Agentic Brain Backend", isOn: $settings.agenticBrainEnabled)
                        .accessibilityHint("When enabled, Brain Chat routes through the agentic-brain API before direct provider fallbacks")

                    TextField("REST Base URL", text: $settings.agenticBrainAPIBaseURL)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Agentic Brain REST base URL")
                        .accessibilityHint("For example http://localhost:8000")

                    TextField("WebSocket URL", text: $settings.agenticBrainWebSocketURL)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Agentic Brain WebSocket URL")
                        .accessibilityHint("Optional. Leave blank to derive ws slash ws chat from the REST base URL")

                    TextField("Session ID", text: $settings.agenticBrainSessionID)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Agentic Brain session identifier")

                    TextField("User ID", text: $settings.agenticBrainUserID)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Agentic Brain user identifier")

                    Toggle("Enable Graph RAG Metadata", isOn: $settings.graphRAGEnabled)
                        .accessibilityHint("Adds graph retrieval hints to backend chat requests")

                    TextField("Graph RAG Scope", text: $settings.graphRAGScope)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Graph RAG scope")
                        .accessibilityHint("For example session, workspace, or enterprise")
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

                Section("Agentic Brain Authentication") {
                    APIKeyField(
                        label: "Agentic Brain API Key",
                        placeholder: "X-API-Key for the backend",
                        text: $settings.agenticBrainAPIKey,
                        isVisible: $showingBackendAPIKey
                    )

                    APIKeyField(
                        label: "Agentic Brain Bearer Token",
                        placeholder: "Bearer token for backend auth",
                        text: $settings.agenticBrainBearerToken,
                        isVisible: $showingBackendBearerToken
                    )
                }

                Section("ADL Configuration") {
                    TextField("ADL File Path", text: $settings.adlConfigPath)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("ADL file path")
                        .accessibilityHint("Absolute path to an ADL configuration file")

                    Button("Load ADL Configuration") {
                        settings.loadADLConfiguration()
                    }
                    .accessibilityHint("Parses the ADL file and applies Brain Chat profile, mode, routing, and Graph RAG settings")
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
        .onChange(of: securityManager.currentRole) { _, _ in
            if !securityManager.canUseYolo() {
                llmRouter.yoloMode = false
            }
        }
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
