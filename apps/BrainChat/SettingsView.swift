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
                // MARK: Behavior Profile Group
                Section("Behavior & Connectivity") {
                    Picker("Profile", selection: $settings.behaviorProfile) {
                        ForEach(BrainChatBehaviorProfile.allCases) { profile in
                            Text(profile.displayName).tag(profile)
                        }
                    }
                    .accessibilityLabel("Behavior profile")
                    .accessibilityHint("Choose beginner, developer, or enterprise behavior")

                    Picker("Connectivity Mode", selection: $settings.agenticBrainMode) {
                        ForEach(AgenticBrainConnectionMode.allCases) { mode in
                            Text(mode.accessibilityLabel).tag(mode)
                        }
                    }
                    .accessibilityLabel("Connectivity mode")
                    .accessibilityHint("Select airlocked, hybrid, or cloud mode")
                }

                // MARK: Feature Toggles Group
                Section("Features") {
                    Toggle("Continuous Listening", isOn: $settings.continuousListening)
                        .accessibilityLabel("Continuous listening")
                        .accessibilityHint("Keep microphone on for continuous transcription")

                    Toggle("Auto-Speak Responses", isOn: $settings.autoSpeak)
                        .accessibilityLabel("Auto-speak responses")
                        .accessibilityHint("Read responses aloud automatically")

                    Toggle("YOLO Mode", isOn: $llmRouter.yoloMode)
                        .accessibilityLabel("YOLO autonomous mode")
                        .accessibilityHint(
                            securityManager.canUseYolo()
                                ? "Allow autonomous actions without confirmation"
                                : "Unavailable outside admin testing mode"
                        )
                        .disabled(!securityManager.canUseYolo())
                }

                // MARK: Security Group
                Section("Security") {
                    SecurityModeView(securityManager: securityManager)
                        .accessibilityElement(children: .contain)
                        .accessibilityLabel("Security mode settings")
                }

                // MARK: Layered Responses Group
                Section("Response Strategy") {
                    LayerStrategyPicker(
                        strategy: Binding(
                            get: { settings.layeredStrategy },
                            set: { settings.layeredStrategy = $0 }
                        ),
                        layeredModeEnabled: $settings.layeredModeEnabled
                    )
                    .accessibilityElement(children: .contain)
                    .accessibilityLabel("Response layer strategy")
                }
            }
            .formStyle(.grouped)
            .tabItem { Label("General", systemImage: "gear") }

            // MARK: Voice tab
            Form {
                // MARK: TTS Engine Selection
                Section("Voice Output") {
                    HStack {
                        Text("TTS Engine")
                        Spacer()
                        VoiceOutputSelector()
                            .environmentObject(settings)
                    }
                    .accessibilityElement(children: .contain)
                    .accessibilityLabel("Text-to-speech engine")
                    .accessibilityHint("Select voice engine: macOS, Cartesia, or ElevenLabs")
                }

                // MARK: Voice Customization
                Section("Voice Settings") {
                    Picker("Voice", selection: $settings.voiceName) {
                        ForEach(voiceManager.availableVoices) { voice in
                            Text(voice.name).tag(voice.name)
                        }
                    }
                    .accessibilityLabel("Voice")
                    .accessibilityHint("Choose voice for spoken responses")
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
                            .accessibilityHint("Adjust voice speed. Drag right to increase.")
                            .onChange(of: settings.speechRate) { _, newValue in
                                voiceManager.speechRate = Float(newValue)
                            }
                    }

                    Button("Test Voice") {
                        voiceManager.speakImmediately("Brain Chat voice bridge ready. Speech rate is \(Int(settings.speechRate)) words per minute.")
                    }
                    .accessibilityHint("Hear sample at current rate and voice")
                }
            }
            .formStyle(.grouped)
            .tabItem { Label("Voice", systemImage: "waveform") }

            // MARK: API tab
            Form {
                // MARK: Voice Bridge
                Section("Voice Bridge") {
                    TextField("WebSocket URL", text: $settings.bridgeWebSocketURL)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Voice Bridge WebSocket URL")
                        .accessibilityHint("Local bridge server address, e.g. ws://localhost:8765")
                }

                // MARK: Agentic Brain Backend
                Section("Agentic Brain Backend") {
                    Toggle("Enable Agentic Brain", isOn: $settings.agenticBrainEnabled)
                        .accessibilityLabel("Enable Agentic Brain")
                        .accessibilityHint("Route through agentic-brain API before direct providers")

                    TextField("REST Base URL", text: $settings.agenticBrainAPIBaseURL)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Agentic Brain REST URL")
                        .accessibilityHint("Example: http://localhost:8000")

                    TextField("WebSocket URL", text: $settings.agenticBrainWebSocketURL)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Agentic Brain WebSocket URL")
                        .accessibilityHint("Optional, derived from REST URL if blank")

                    TextField("Session ID", text: $settings.agenticBrainSessionID)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Agentic Brain session ID")

                    TextField("User ID", text: $settings.agenticBrainUserID)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Agentic Brain user ID")

                    Toggle("Enable Graph RAG", isOn: $settings.graphRAGEnabled)
                        .accessibilityLabel("Graph RAG metadata")
                        .accessibilityHint("Add graph retrieval hints to requests")

                    TextField("Graph RAG Scope", text: $settings.graphRAGScope)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Graph RAG scope")
                        .accessibilityHint("Example: session, workspace, or enterprise")
                }

                // MARK: LLM API Keys
                Section("LLM Providers") {
                    APIKeyField(
                        label: "Groq API Key",
                        placeholder: "Groq API key (groq.com)",
                        text: $settings.groqAPIKey,
                        isVisible: $showingGroqKey
                    )
                    .accessibilityElement(children: .contain)
                    .accessibilityLabel("Groq API key (instant layer)")

                    APIKeyField(
                        label: "Claude API Key",
                        placeholder: "Anthropic API key",
                        text: $settings.claudeAPIKey,
                        isVisible: $showingClaudeKey
                    )
                    .accessibilityElement(children: .contain)
                    .accessibilityLabel("Claude API key")

                    APIKeyField(
                        label: "OpenAI API Key",
                        placeholder: "OpenAI API key",
                        text: $settings.openAIKey,
                        isVisible: $showingOpenAIKey
                    )
                    .accessibilityElement(children: .contain)
                    .accessibilityLabel("OpenAI API key")
                }

                // MARK: Backend Authentication
                Section("Backend Auth") {
                    APIKeyField(
                        label: "Agentic Brain API Key",
                        placeholder: "X-API-Key for the backend",
                        text: $settings.agenticBrainAPIKey,
                        isVisible: $showingBackendAPIKey
                    )
                    .accessibilityElement(children: .contain)
                    .accessibilityLabel("Agentic Brain API key")

                    APIKeyField(
                        label: "Agentic Brain Bearer Token",
                        placeholder: "Bearer token for backend auth",
                        text: $settings.agenticBrainBearerToken,
                        isVisible: $showingBackendBearerToken
                    )
                    .accessibilityElement(children: .contain)
                    .accessibilityLabel("Agentic Brain bearer token")
                }

                // MARK: ADL Configuration
                Section("ADL Configuration") {
                    TextField("ADL File Path", text: $settings.adlConfigPath)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("ADL file path")
                        .accessibilityHint("Absolute path to ADL configuration file")

                    Button("Load ADL Configuration") {
                        settings.loadADLConfiguration()
                    }
                    .accessibilityHint("Parse ADL file and apply settings")
                }

                // MARK: Key Management
                Section("Keychain Management") {
                    Button("Save Keys") { settings.saveAPIKeys() }
                        .accessibilityHint("Save all API keys to system Keychain")

                    Button("Reload Keys") { settings.loadAPIKeys() }
                        .accessibilityHint("Load API keys from system Keychain")

                    Button("Clear All Keys", role: .destructive) {
                        showClearKeysConfirmation = true
                    }
                    .accessibilityHint("Delete all API keys from Keychain")
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

                    if !settings.keychainStatusMessage.isEmpty {
                        HStack(spacing: 8) {
                            Image(systemName: settings.keychainStatusMessage.contains("saved") || settings.keychainStatusMessage.contains("removed") ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                                .foregroundColor(settings.keychainStatusMessage.contains("saved") || settings.keychainStatusMessage.contains("removed") ? .green : .orange)
                                .accessibilityHidden(true)
                            Text(settings.keychainStatusMessage)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        .accessibilityElement(children: .combine)
                        .accessibilityLabel("Keychain status")
                        .accessibilityValue(settings.keychainStatusMessage)
                    }
                }

                // MARK: Local Models
                Section("Local Models (Ollama)") {
                    TextField("Ollama Endpoint", text: $settings.apiEndpoint)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Ollama endpoint")
                        .accessibilityHint("HTTP address: http://localhost:11434/api/chat")

                    TextField("Ollama Model", text: $settings.modelName)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Ollama model")
                        .accessibilityHint("Example: llama3.2:3b")
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

// MARK: - Reusable API Key Field (WCAG AAA: Accessible form input)

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
                .accessibilityLabel(isVisible ? "Hide" : "Show")
                .accessibilityHint(isVisible ? "Mask the key" : "Reveal the key")
            }
        }
    }
}
