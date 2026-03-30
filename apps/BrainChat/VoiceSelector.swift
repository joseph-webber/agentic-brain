import SwiftUI

struct VoiceSelector: View {
    @ObservedObject var cartesia: CartesiaVoice
    @ObservedObject var audioPlayer: AudioPlayer

    @State private var apiKeyDraft = ""
    @State private var previewText = "G'day Joseph, Brain Chat is speaking with Cartesia now."

    var body: some View {
        Form {
            Section("Cartesia") {
                HStack(alignment: .top, spacing: 12) {
                    SecureField("Cartesia API key", text: $apiKeyDraft)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Cartesia API key")

                    Button("Save Key") {
                        do {
                            try cartesia.setAPIKey(apiKeyDraft)
                            apiKeyDraft = ""
                        } catch {
                            cartesia.setStatusMessage(error.localizedDescription)
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .accessibilityLabel("Save Cartesia API key")

                    Button("Remove Key") {
                        apiKeyDraft = ""
                        cartesia.removeAPIKey()
                    }
                    .buttonStyle(.bordered)
                    .accessibilityLabel("Remove Cartesia API key")
                }

                Label(
                    cartesia.hasStoredAPIKey ? "API key saved in Keychain" : "No Cartesia key stored yet",
                    systemImage: cartesia.hasStoredAPIKey ? "checkmark.shield" : "key.slash"
                )
                .foregroundStyle(cartesia.hasStoredAPIKey ? .green : .secondary)
                .accessibilityLabel(cartesia.hasStoredAPIKey ? "Cartesia API key saved in Keychain" : "No Cartesia API key stored")
            }

            Section("Voice") {
                Picker("Voice", selection: $cartesia.selectedVoiceID) {
                    ForEach(cartesia.availableVoices) { voice in
                        VStack(alignment: .leading) {
                            Text(voice.name)
                            Text(voice.accentDescription)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        .tag(voice.voiceID)
                        .accessibilityLabel("\(voice.name), \(voice.accentDescription)")
                    }
                }
                .accessibilityLabel("Select a Cartesia voice")

                Text(selectedVoiceSummary)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .accessibilityLabel(selectedVoiceSummary)
            }

            Section("Playback") {
                TextField("Preview text", text: $previewText, axis: .vertical)
                    .lineLimit(2...5)
                    .textFieldStyle(.roundedBorder)
                    .accessibilityLabel("Preview text")

                HStack(spacing: 12) {
                    Button("Speak Preview") {
                        cartesia.enqueue(previewText)
                    }
                    .buttonStyle(.borderedProminent)
                    .accessibilityLabel("Speak preview text")

                    Button("Queue Twice") {
                        cartesia.enqueue(previewText)
                        cartesia.enqueue("Second queued utterance. Cartesia should speak this after the first line finishes.")
                    }
                    .buttonStyle(.bordered)
                    .accessibilityLabel("Queue two utterances")

                    Button("Cancel Speech") {
                        cartesia.cancelCurrentSpeech(clearQueue: true)
                    }
                    .buttonStyle(.bordered)
                    .tint(.red)
                    .accessibilityLabel("Cancel current speech and clear the queue")
                }

                VStack(alignment: .leading, spacing: 8) {
                    Label(audioPlayer.currentRoute.name, systemImage: audioPlayer.currentRoute.isAirPods ? "airpodspro" : "speaker.wave.2")
                        .accessibilityLabel("Current audio output device: \(audioPlayer.currentRoute.name)")
                    Text(audioPlayer.currentRoute.isAirPods ? "AirPods detected. Playback will use the active Bluetooth route automatically." : "AirPods not detected. Brain Chat will use the current macOS output device.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .accessibilityLabel(audioPlayer.currentRoute.isAirPods ? "AirPods are connected" : "AirPods are not connected")
                }
            }

            Section("Status") {
                Text(cartesia.statusMessage)
                    .accessibilityLabel("Cartesia status: \(cartesia.statusMessage)")
            }
        }
        .formStyle(.grouped)
        .navigationTitle("Voice Selector")
        .onAppear {
            audioPlayer.refreshOutputRoute()
        }
    }

    private var selectedVoiceSummary: String {
        let selected = cartesia.availableVoices.first(where: { $0.voiceID == cartesia.selectedVoiceID }) ?? CartesiaVoiceOption.defaultOption
        return "Selected voice: \(selected.name). \(selected.accentDescription)."
    }
}
