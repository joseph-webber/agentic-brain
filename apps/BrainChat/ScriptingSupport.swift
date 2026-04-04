import AppKit
import Foundation

// MARK: - Shared scripting bridge

/// Container that the App layer populates on launch so that
/// NSScriptCommand handlers can reach the live objects they need.
/// Properties are only written from MainActor (on launch) and read
/// from NSScriptCommand handlers via main-thread dispatch.
final class ScriptingBridge: @unchecked Sendable {
    static let shared = ScriptingBridge()

    nonisolated(unsafe) var conversationStore: ConversationStore?
    nonisolated(unsafe) var speechManager: SpeechManager?
    nonisolated(unsafe) var voiceManager: VoiceManager?
    nonisolated(unsafe) var settings: AppSettings?
    nonisolated(unsafe) var llmRouter: LLMRouter?

    private init() {}
}

// MARK: - Send Message

final class SendMessageCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let message = directParameter as? String,
              !message.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "No message text provided."
            return nil
        }

        let bridge = ScriptingBridge.shared

        // Check bridge readiness on main thread
        let ready: Bool = onMain {
            MainActor.assumeIsolated {
                bridge.conversationStore != nil && bridge.settings != nil && bridge.llmRouter != nil
            }
        }

        guard ready else {
            return "error: BrainChat scripting bridge not ready"
        }

        // Add user message on main thread
        onMain {
            MainActor.assumeIsolated {
                bridge.conversationStore?.addMessage(role: .user, content: message)
            }
        }

        // Cannot await async LLM call from the main thread (deadlock).
        // Real AppleScript invocations come from a background thread.
        guard !Thread.isMainThread else {
            return "error: cannot await LLM on main thread (use osascript)"
        }

        // Fire the async LLM call and wait for it
        let semaphore = DispatchSemaphore(value: 0)
        var response = ""

        DispatchQueue.main.async {
            MainActor.assumeIsolated {
                let store = bridge.conversationStore!
                let settings = bridge.settings!
                let router = bridge.llmRouter!

                let history = store.recentConversation
                let configuration = settings.routerConfiguration(
                    provider: router.selectedProvider,
                    yoloMode: router.yoloMode
                )

                Task {
                    let reply = await router.streamReply(
                        history: history,
                        configuration: configuration
                    ) { _ in }

                    await MainActor.run {
                        store.addMessage(role: .assistant, content: reply)
                        if let voiceManager = bridge.voiceManager, settings.autoSpeak {
                            voiceManager.speak(reply)
                        }
                    }
                    response = reply
                    semaphore.signal()
                }
            }
        }

        let timeout = semaphore.wait(timeout: .now() + 120)
        if timeout == .timedOut {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "LLM response timed out after 120 seconds."
            return nil
        }
        return response
    }
}

// MARK: - Get Last Response

final class GetLastResponseCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        let bridge = ScriptingBridge.shared
        return onMain {
            MainActor.assumeIsolated {
                guard let store = bridge.conversationStore else { return "" }
                
                // Find the last assistant response
                for message in store.messages.reversed() {
                    if message.role == .assistant {
                        return message.content
                    }
                }
                return ""
            }
        }
    }
}

// MARK: - Get Selected LLM

final class GetSelectedLLMCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        let bridge = ScriptingBridge.shared
        return onMain {
            MainActor.assumeIsolated {
                guard let router = bridge.llmRouter else { return "" }
                return router.selectedProvider.rawValue
            }
        }
    }
}

// MARK: - Set Selected LLM

final class SetSelectedLLMCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let name = directParameter as? String else {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "No provider name provided."
            return nil
        }

        let lowered = name.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        let provider: LLMProvider? = {
            switch lowered {
            case "ollama":  return .ollama
            case "groq":    return .groq
            case "claude":  return .claude
            case "gpt":     return .gpt
            case "grok":    return .grok
            case "gemini":  return .gemini
            case "copilot": return .copilot
            default:        return LLMProvider.allCases.first { $0.rawValue.lowercased().contains(lowered) }
            }
        }()

        guard let resolved = provider else {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "Unknown provider: \(name). Use: ollama, groq, claude, gpt, grok, gemini, copilot."
            return nil
        }

        let bridge = ScriptingBridge.shared
        onMain { MainActor.assumeIsolated { bridge.llmRouter?.selectedProvider = resolved } }
        return nil
    }
}

// MARK: - Set Provider (Deprecated, kept for backward compatibility)

final class SetProviderCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let name = directParameter as? String else {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "No provider name provided."
            return nil
        }

        let lowered = name.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        let provider: LLMProvider? = {
            switch lowered {
            case "ollama":  return .ollama
            case "groq":    return .groq
            case "claude":  return .claude
            case "gpt":     return .gpt
            case "grok":    return .grok
            case "gemini":  return .gemini
            case "copilot": return .copilot
            default:        return LLMProvider.allCases.first { $0.rawValue.lowercased().contains(lowered) }
            }
        }()

        guard let resolved = provider else {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "Unknown provider: \(name). Use: ollama, groq, claude, gpt, grok, gemini, copilot."
            return nil
        }

        let bridge = ScriptingBridge.shared
        onMain { MainActor.assumeIsolated { bridge.llmRouter?.selectedProvider = resolved } }
        return nil
    }
}

// MARK: - Get Mic Status

final class GetMicStatusCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        let bridge = ScriptingBridge.shared
        return onMain {
            MainActor.assumeIsolated {
                guard let speechManager = bridge.speechManager else { return "" }
                // Check if listening is active
                return speechManager.isListening ? "live" : "muted"
            }
        }
    }
}

// MARK: - Toggle Mic

final class ToggleMicCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        let bridge = ScriptingBridge.shared
        return onMain {
            MainActor.assumeIsolated {
                guard let speechManager = bridge.speechManager else { return "" }
                if speechManager.isListening {
                    speechManager.stopListening()
                    return "muted"
                } else {
                    speechManager.startListening()
                    return "live"
                }
            }
        }
    }
}

// MARK: - Start Listening

final class StartListeningCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        let bridge = ScriptingBridge.shared
        onMain { MainActor.assumeIsolated { bridge.speechManager?.startListening() } }
        return nil
    }
}

// MARK: - Stop Listening

final class StopListeningCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        let bridge = ScriptingBridge.shared
        onMain { MainActor.assumeIsolated { bridge.speechManager?.stopListening() } }
        return nil
    }
}

// MARK: - Speak

final class SpeakTextCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let text = directParameter as? String,
              !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "No text provided to speak."
            return nil
        }

        let bridge = ScriptingBridge.shared
        onMain { MainActor.assumeIsolated { bridge.voiceManager?.speak(text) } }
        return nil
    }
}

// MARK: - Get Conversation

final class GetConversationCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        let bridge = ScriptingBridge.shared
        return onMain {
            MainActor.assumeIsolated {
                guard let store = bridge.conversationStore else { return "" }

                let lines = store.messages.map { msg -> String in
                    let prefix: String
                    switch msg.role {
                    case .user:      prefix = "You"
                    case .assistant: prefix = "Karen"
                    case .copilot:   prefix = "Copilot"
                    case .system:    prefix = "System"
                    }
                    return "[\(prefix)] \(msg.content)"
                }
                return lines.joined(separator: "\n")
            }
        }
    }
}

// MARK: - Get Whisper Engine

final class GetWhisperEngineCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        let bridge = ScriptingBridge.shared
        return onMain {
            MainActor.assumeIsolated {
                guard let speechManager = bridge.speechManager else { return "unknown" }
                return speechManager.currentEngine.rawValue
            }
        }
    }
}

// MARK: - Set Whisper Engine

final class SetWhisperEngineCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let engineName = directParameter as? String else {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "No engine name provided."
            return nil
        }

        let lowered = engineName.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        
        // Map user-friendly names to SpeechEngine cases
        let engine: SpeechEngine? = {
            switch lowered {
            case "whisperkit", "faster-whisper", "local":
                return .whisperKit
            case "whisperapi", "openai", "remote":
                return .whisperAPI
            case "whispercpp", "cpp":
                return .whisperCpp
            case "appledictation", "apple", "builtin":
                return .appleDictation
            default:
                // Try raw value match
                return SpeechEngine.allCases.first { $0.rawValue.lowercased() == lowered }
            }
        }()

        guard let resolved = engine else {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "Unknown engine: \(engineName). Use: whisperKit, whisperAPI, whisperCpp, or appleDictation."
            return nil
        }

        let bridge = ScriptingBridge.shared
        onMain {
            MainActor.assumeIsolated {
                bridge.speechManager?.setEngine(resolved)
            }
        }
        return nil
    }
}

// MARK: - Get Copilot Status

final class GetCopilotStatusCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        let bridge = ScriptingBridge.shared
        return onMain {
            MainActor.assumeIsolated {
                var status: [String: String] = [:]
                
                if let router = bridge.llmRouter {
                    status["provider"] = router.selectedProvider.rawValue
                    status["activeProvider"] = router.activeProviderName
                    status["status"] = router.statusMessage
                    if let error = router.lastErrorMessage {
                        status["error"] = error
                    }
                }
                
                if let speechManager = bridge.speechManager {
                    status["micStatus"] = speechManager.isListening ? "live" : "muted"
                }
                
                if let store = bridge.conversationStore {
                    status["messageCount"] = String(store.messages.count)
                    status["isProcessing"] = store.isProcessing ? "true" : "false"
                }
                
                // Format as key=value pairs for AppleScript readability
                let pairs = status.map { "\($0.key): \($0.value)" }
                return pairs.joined(separator: ", ")
            }
        }
    }
}

// MARK: - LLM Orchestration Commands

final class SetLLMModeCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let modeString = directParameter as? String else {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "No mode provided. Use: single, multi_bot, consensus"
            return nil
        }
        return onMain {
            MainActor.assumeIsolated {
                let success = LLMOrchestrator.shared.setLLMMode(modeString)
                if !success {
                    self.scriptErrorNumber = errOSAGeneralError
                    self.scriptErrorString = "Unknown mode: \(modeString). Use: single, multi_bot, consensus"
                    return nil
                }
                return "OK" as Any
            }
        }
    }
}

final class SetPrimaryLLMCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let providerString = directParameter as? String else {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "No provider provided. Use: ollama, groq, claude, gpt, grok, gemini, copilot"
            return nil
        }
        return onMain {
            MainActor.assumeIsolated {
                let success = LLMOrchestrator.shared.setPrimaryLLM(providerString)
                if !success {
                    self.scriptErrorNumber = errOSAGeneralError
                    self.scriptErrorString = "Unknown provider: \(providerString)"
                    return nil
                }
                return "OK" as Any
            }
        }
    }
}

final class GetLLMStatusCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        onMain {
            MainActor.assumeIsolated {
                LLMOrchestrator.shared.getStatus()
            }
        }
    }
}

final class AddSecondaryLLMCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let providerString = directParameter as? String else {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "No provider provided."
            return nil
        }
        return onMain {
            MainActor.assumeIsolated {
                let success = LLMOrchestrator.shared.addSecondaryLLM(providerString)
                return success ? "OK" as Any : nil
            }
        }
    }
}

final class RemoveSecondaryLLMCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let providerString = directParameter as? String else {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "No provider provided."
            return nil
        }
        return onMain {
            MainActor.assumeIsolated {
                let success = LLMOrchestrator.shared.removeSecondaryLLM(providerString)
                return success ? "OK" as Any : nil
            }
        }
    }
}

final class GetLLMModeCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        onMain {
            MainActor.assumeIsolated {
                LLMOrchestrator.shared.mode.rawValue
            }
        }
    }
}

// MARK: - Helpers

/// Execute a block on the main thread, returning its result.
/// Uses DispatchQueue.main.sync when off-main, direct call when on-main.
@discardableResult
private func onMain<T>(_ block: @escaping () -> T) -> T {
    if Thread.isMainThread {
        return block()
    } else {
        return DispatchQueue.main.sync { block() }
    }
}
