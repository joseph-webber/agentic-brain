import AppKit
import Foundation
import Speech
import SwiftUI

enum BrainChatCLICommand: Equatable {
    case send(String)
    case speak(String)
    case listen
    case help

    init?(arguments: [String]) {
        let remaining = Array(arguments.dropFirst())
        guard let first = remaining.first else { return nil }

        switch first {
        case "--send":
            let text = remaining.dropFirst().joined(separator: " ").trimmingCharacters(in: .whitespacesAndNewlines)
            self = text.isEmpty ? .help : .send(text)
        case "--speak":
            let text = remaining.dropFirst().joined(separator: " ").trimmingCharacters(in: .whitespacesAndNewlines)
            self = text.isEmpty ? .help : .speak(text)
        case "--listen":
            self = .listen
        case "--help", "-h", "help":
            self = .help
        default:
            return nil
        }
    }
}

@MainActor
enum BrainChatCLIHandler {
    static let command = BrainChatCLICommand(arguments: CommandLine.arguments)

    private static let runtimeDirectory = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("brain/agentic-brain/apps/BrainChat/runtime", isDirectory: true)

    static var isActive: Bool {
        command != nil
    }

    static var usage: String {
        """
        BrainChat AppleScript CLI

        Usage:
          BrainChat --send <message>
          BrainChat --listen
          BrainChat --speak <text>
          BrainChat --help
        """
    }

    static func run(_ command: BrainChatCLICommand) async -> Int32 {
        writeRuntimeMarker("last-cli-command.txt", value: String(describing: command))

        switch command {
        case .help:
            print(usage)
            return 0
        case .send(let text):
            return await handleSend(text)
        case .speak(let text):
            return await handleSpeak(text)
        case .listen:
            return await handleListen()
        }
    }

    private static func handleSend(_ text: String) async -> Int32 {
        let settings = AppSettings()
        let router = LLMRouter()
        let configuration = settings.routerConfiguration(provider: router.selectedProvider, yoloMode: router.yoloMode)
        let response = await router.streamReply(
            history: [ChatMessage(role: .user, content: text)],
            configuration: configuration
        ) { _ in }

        let trimmed = response.trimmingCharacters(in: .whitespacesAndNewlines)
        writeRuntimeMarker("last-cli-prompt.txt", value: text)
        writeRuntimeMarker("last-cli-response.txt", value: trimmed)
        if trimmed.isEmpty {
            fputs("BrainChat returned an empty response.\n", stderr)
            return 1
        }

        print(trimmed)
        return trimmed.localizedCaseInsensitiveContains("all llm providers are unavailable") ? 1 : 0
    }

    private static func handleSpeak(_ text: String) async -> Int32 {
        let voiceManager = VoiceManager()
        voiceManager.speakImmediately(text)
        writeRuntimeMarker("last-cli-spoken.txt", value: text)
        await waitForSpeechToFinish(voiceManager)
        return 0
    }

    private static func handleListen() async -> Int32 {
        let speechManager = SpeechManager()
        speechManager.setEngine(.appleDictation)

        let speechAuthorized = await ensureSpeechAuthorization(for: speechManager)
        guard speechAuthorized else {
            let message = speechManager.errorMessage ?? "Speech recognition not authorized."
            writeRuntimeMarker("last-cli-error.txt", value: message)
            fputs("\(message)\n", stderr)
            return 1
        }

        let microphoneAuthorized = await ensureMicrophoneAuthorization(for: speechManager)
        guard microphoneAuthorized else {
            let message = speechManager.errorMessage ?? "Microphone access not authorized."
            writeRuntimeMarker("last-cli-error.txt", value: message)
            fputs("\(message)\n", stderr)
            return 1
        }

        return await withCheckedContinuation { continuation in
            var hasCompleted = false

            @MainActor
            func finish(code: Int32, output: String?, error: String?) {
                guard !hasCompleted else { return }
                hasCompleted = true
                if let output {
                    writeRuntimeMarker("last-cli-listen.txt", value: output)
                    print(output)
                }
                if let error {
                    writeRuntimeMarker("last-cli-error.txt", value: error)
                    fputs("\(error)\n", stderr)
                }
                speechManager.stopListening()
                continuation.resume(returning: code)
            }

            speechManager.onTranscriptFinalized = { transcript in
                let trimmed = transcript.trimmingCharacters(in: .whitespacesAndNewlines)
                Task { @MainActor in
                    if trimmed.isEmpty {
                        finish(code: 1, output: nil, error: "BrainChat did not hear any speech.")
                    } else {
                        finish(code: 0, output: trimmed, error: nil)
                    }
                }
            }

            speechManager.startListening()

            Task { @MainActor in
                let timeoutNanoseconds = UInt64(60 * 1_000_000_000)
                let pollNanoseconds = UInt64(250_000_000)
                var waited: UInt64 = 0

                while waited < timeoutNanoseconds && !hasCompleted {
                    try? await Task.sleep(nanoseconds: pollNanoseconds)
                    waited += pollNanoseconds

                    if let error = speechManager.errorMessage?.trimmingCharacters(in: .whitespacesAndNewlines),
                       !error.isEmpty {
                        finish(code: 1, output: nil, error: error)
                        return
                    }
                }

                if !hasCompleted {
                    finish(code: 1, output: nil, error: "BrainChat listen command timed out after 60 seconds.")
                }
            }
        }
    }

    private static func ensureSpeechAuthorization(for speechManager: SpeechManager) async -> Bool {
        if speechManager.authorizationStatus == .authorized {
            return true
        }

        speechManager.requestAuthorization()
        return await waitFor {
            switch speechManager.authorizationStatus {
            case .authorized:
                return true
            case .denied, .restricted:
                speechManager.errorMessage = "Speech recognition not authorized. Enable in System Settings > Privacy > Speech Recognition."
                return true
            case .notDetermined:
                return false
            @unknown default:
                speechManager.errorMessage = "Speech recognition authorization is unavailable."
                return true
            }
        } && speechManager.authorizationStatus == .authorized
    }

    private static func ensureMicrophoneAuthorization(for speechManager: SpeechManager) async -> Bool {
        if speechManager.isMicrophoneAuthorized() {
            return true
        }

        let granted = await withCheckedContinuation { continuation in
            speechManager.requestMicrophonePermissionWithCompletion { granted in
                continuation.resume(returning: granted)
            }
        }

        if !granted {
            speechManager.errorMessage = "Microphone access not authorized. Enable in System Settings > Privacy > Microphone."
        }
        return granted
    }

    private static func waitForSpeechToFinish(_ voiceManager: VoiceManager) async {
        let timeoutNanoseconds = UInt64(120 * 1_000_000_000)
        let pollNanoseconds = UInt64(250_000_000)
        var waited: UInt64 = 0

        repeat {
            try? await Task.sleep(nanoseconds: pollNanoseconds)
            waited += pollNanoseconds
        } while voiceManager.isSpeaking && waited < timeoutNanoseconds
    }

    private static func waitFor(
        timeoutNanoseconds: UInt64 = 10 * 1_000_000_000,
        pollNanoseconds: UInt64 = 100_000_000,
        condition: @escaping @MainActor () -> Bool
    ) async -> Bool {
        var waited: UInt64 = 0
        while waited < timeoutNanoseconds {
            if condition() {
                return true
            }
            try? await Task.sleep(nanoseconds: pollNanoseconds)
            waited += pollNanoseconds
        }
        return condition()
    }

    private static func writeRuntimeMarker(_ filename: String, value: String) {
        try? FileManager.default.createDirectory(at: runtimeDirectory, withIntermediateDirectories: true)
        try? value.write(to: runtimeDirectory.appendingPathComponent(filename), atomically: true, encoding: .utf8)
    }
}
