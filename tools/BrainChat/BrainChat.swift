import Cocoa
import Speech
import AVFoundation
import Darwin

// MARK: - FourCharCode Helper

extension FourCharCode {
    init(_ string: String) {
        let chars = string.utf8
        var code: FourCharCode = 0
        for (index, char) in chars.prefix(4).enumerated() {
            code |= FourCharCode(char) << (24 - index * 8)
        }
        self = code
    }
}

// MARK: - NSApplication AppleScript Properties Extension

extension NSApplication {
    /// Current chat mode accessible via AppleScript
    @objc var currentMode: String {
        get { ScriptingState.shared.appDelegate?.currentModeForScript.rawValue ?? "chat" }
        set {
            if let mode = ChatMode(rawValue: newValue.lowercased()) {
                DispatchQueue.main.async {
                    ScriptingState.shared.appDelegate?.setModeFromScript(mode)
                }
            }
        }
    }
    
    /// Whether speech recognition is currently active
    @objc var isListening: Bool {
        ScriptingState.shared.appDelegate?.isListeningForScript ?? false
    }
    
    /// The most recent response from the brain
    @objc var lastResponse: String {
        ScriptingState.shared.lastResponse
    }
    
    /// Current status message
    @objc var status: String {
        ScriptingState.shared.currentStatus
    }
    
    /// Whether the Redpanda bridge is connected
    @objc var bridgeConnected: Bool {
        guard let delegate = ScriptingState.shared.appDelegate else { return false }
        switch delegate.bridgeAvailabilityForScript {
        case .connected: return true
        case .unavailable: return false
        }
    }
}

struct BridgeResponse {
    let text: String
    let requestID: String?
    let isPartial: Bool
    let isFinal: Bool
    let containsANSI: Bool

    init(text: String, requestID: String?, isPartial: Bool = false, isFinal: Bool = true) {
        self.text = text
        self.requestID = requestID
        self.isPartial = isPartial
        self.isFinal = isFinal
        self.containsANSI = text.contains("\u{001B}")
    }
}

final class ANSIText {
    private static let ansiRegex = try? NSRegularExpression(pattern: "\\u{001B}\\[[0-9;?]*[ -/]*[@-~]", options: [])

    static func strip(_ text: String) -> String {
        guard let ansiRegex else { return text }
        let range = NSRange(text.startIndex..., in: text)
        return ansiRegex.stringByReplacingMatches(in: text, options: [], range: range, withTemplate: "")
    }
}

final class LocalFallbackResponder {
    private let formatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .full
        formatter.timeStyle = .short
        formatter.locale = Locale(identifier: "en_AU")
        return formatter
    }()

    func response(for input: String, reason: String?) -> String {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        let lowercased = trimmed.lowercased()
        let prefix = reason.map { "Redpanda is unavailable right now (\($0)). " } ?? "Using local fallback mode. "

        if lowercased.contains("time") || lowercased.contains("date") {
            return prefix + "The current local time is \(formatter.string(from: Date()))."
        }

        if lowercased.contains("status") || lowercased.contains("are you there") {
            return prefix + "Brain Chat is ready for voice commands and can keep listening locally until the backend reconnects."
        }

        if lowercased.contains("hello") || lowercased.contains("hi") || lowercased.contains("hey") {
            return prefix + "Hello Joseph. I heard \"\(trimmed)\"."
        }

        if trimmed.isEmpty {
            return prefix + "I did not catch any words. Please try again."
        }

        return prefix + "I heard \"\(trimmed)\". Once Redpanda comes back, I will send your request to the wider brain."
    }
}

final class SpeechVoice {
    private var speakProcess: Process?
    
    /// Gets the current voice name from settings
    private var voiceName: String {
        let voice = VoiceSettings.currentVoice
        // Try premium version first
        return "\(voice.rawValue) (Premium)"
    }
    
    /// Gets the current speech rate from settings
    private var speechRate: Int {
        VoiceSettings.speechRate
    }
    
    init() {}
    
    func speak(_ text: String) {
        let cleanText = ANSIText.strip(text)
        guard !cleanText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        guard VoiceSettings.isEnabled else { return }  // Respect voice enabled setting
        
        // Kill any existing speech
        stopSpeaking()
        
        // Use macOS 'say' command - much more reliable than AVSpeechSynthesizer
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/say")
        process.arguments = ["-v", voiceName, "-r", "\(speechRate)", cleanText]
        
        // Run in background so we don't block
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            do {
                self?.speakProcess = process
                try process.run()
                // Don't wait - let it play in background
            } catch {
                // Fallback to base voice if Premium not available
                let baseVoice = VoiceSettings.currentVoice.rawValue
                let fallbackProcess = Process()
                fallbackProcess.executableURL = URL(fileURLWithPath: "/usr/bin/say")
                fallbackProcess.arguments = ["-v", baseVoice, "-r", "\(self?.speechRate ?? 175)", cleanText]
                try? fallbackProcess.run()
            }
        }
    }
    
    func stopSpeaking() {
        speakProcess?.terminate()
        speakProcess = nil
        // Also kill any lingering say processes
        let killTask = Process()
        killTask.executableURL = URL(fileURLWithPath: "/usr/bin/pkill")
        killTask.arguments = ["-f", "say -v"]
        try? killTask.run()
    }
    
    var isSpeaking: Bool {
        speakProcess?.isRunning ?? false
    }
}

final class RedpandaBridge: NSObject {
    enum Availability {
        case connected
        case unavailable(String)
    }

    var onAvailabilityChanged: ((Availability) -> Void)?
    var onResponse: ((BridgeResponse) -> Void)?

    private let bootstrapServers = "localhost:9092"
    private let inputTopic = "brain.voice.input"
    private let responseTopic = "brain.voice.response"
    private let clientID = "brain-chat-macos-swift"
    private let consumerQueue = DispatchQueue(label: "brainchat.consumer.pty")

    private var consumerProcess: Process?
    private var consumerReadChannel: DispatchIO?
    private var consumerMasterFD: Int32 = -1
    private var consumerSlaveHandle: FileHandle?
    private var consumerBuffer = ""

    func start() {
        guard consumerProcess == nil else { return }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = ["-u", "-c", consumerScript]
        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONUNBUFFERED"] = "1"
        environment["BRAINCHAT_BROKERS"] = bootstrapServers
        environment["BRAINCHAT_RESPONSE_TOPIC"] = responseTopic
        environment["BRAINCHAT_CLIENT_ID"] = clientID
        process.environment = environment

        do {
            try prepareConsumerPTY()
            process.standardOutput = consumerSlaveHandle
            process.standardError = consumerSlaveHandle
            process.terminationHandler = { [weak self] process in
                self?.handleConsumerTermination(status: process.terminationStatus)
            }
            try process.run()
            consumerProcess = process
            beginConsumerReadLoop()
        } catch {
            cleanupConsumerResources()
            onAvailabilityChanged?(.unavailable(error.localizedDescription))
        }
    }

    func stop() {
        consumerReadChannel?.close(flags: .stop)
        consumerReadChannel = nil
        consumerProcess?.terminate()
        consumerProcess = nil
        cleanupConsumerResources()
    }

    func publish(text: String, requestID: String, completion: @escaping (Bool, String?) -> Void) {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = ["-c", producerScript, requestID, clientID, text]
        var environment = ProcessInfo.processInfo.environment
        environment["BRAINCHAT_BROKERS"] = bootstrapServers
        environment["BRAINCHAT_INPUT_TOPIC"] = inputTopic
        process.environment = environment

        let stdout = Pipe()
        let stderr = Pipe()
        process.standardOutput = stdout
        process.standardError = stderr

        process.terminationHandler = { process in
            let outData = stdout.fileHandleForReading.readDataToEndOfFile()
            let errData = stderr.fileHandleForReading.readDataToEndOfFile()
            let outText = String(data: outData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            let errText = String(data: errData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

            DispatchQueue.main.async {
                if process.terminationStatus == 0 {
                    completion(true, nil)
                } else {
                    let message = Self.extractError(from: outText) ?? Self.extractError(from: errText) ?? "Could not publish to Redpanda"
                    completion(false, message)
                }
            }
        }

        do {
            try process.run()
        } catch {
            completion(false, error.localizedDescription)
        }
    }

    private func prepareConsumerPTY() throws {
        cleanupConsumerResources()

        var masterFD: Int32 = -1
        var slaveFD: Int32 = -1
        guard openpty(&masterFD, &slaveFD, nil, nil, nil) == 0 else {
            throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno), userInfo: [NSLocalizedDescriptionKey: String(cString: strerror(errno))])
        }

        consumerMasterFD = masterFD
        consumerSlaveHandle = FileHandle(fileDescriptor: slaveFD, closeOnDealloc: true)
    }

    private func beginConsumerReadLoop() {
        guard consumerMasterFD >= 0 else { return }

        let channel = DispatchIO(type: .stream, fileDescriptor: consumerMasterFD, queue: consumerQueue) { [weak self] _ in
            self?.closeConsumerMasterFD()
        }
        channel.setLimit(lowWater: 1)
        channel.setLimit(highWater: 1)
        consumerReadChannel = channel

        channel.read(offset: 0, length: Int.max, queue: consumerQueue) { [weak self] done, dispatchData, error in
            guard let self else { return }

            if let dispatchData, !dispatchData.isEmpty {
                self.handleConsumerData(Data(dispatchData))
            }

            if error != 0 {
                DispatchQueue.main.async {
                    self.onAvailabilityChanged?(.unavailable(String(cString: strerror(error))))
                }
            }

            if done {
                self.consumerReadChannel = nil
            }
        }
    }

    private func handleConsumerData(_ data: Data) {
        let chunk = String(decoding: data, as: UTF8.self)
        consumerBuffer += chunk
        let lines = consumerBuffer.components(separatedBy: "\n")
        consumerBuffer = lines.last ?? ""

        for line in lines.dropLast() {
            handleLine(line)
        }
    }

    private func handleConsumerTermination(status: Int32) {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.consumerProcess = nil
            if status != 0 {
                self.onAvailabilityChanged?(.unavailable("consumer exited with status \(status)"))
            }
        }
    }

    private func cleanupConsumerResources() {
        consumerSlaveHandle?.closeFile()
        consumerSlaveHandle = nil
        closeConsumerMasterFD()
        consumerBuffer = ""
    }

    private func closeConsumerMasterFD() {
        guard consumerMasterFD >= 0 else { return }
        close(consumerMasterFD)
        consumerMasterFD = -1
    }

    private func handleLine(_ rawLine: String) {
        let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !line.isEmpty else { return }

        if line.hasPrefix("__STATUS__:") {
            let payload = String(line.dropFirst("__STATUS__:".count))
            if let data = payload.data(using: .utf8),
               let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let state = object["state"] as? String {
                if state == "connected" {
                    onAvailabilityChanged?(.connected)
                } else {
                    let reason = object["reason"] as? String ?? "Redpanda unavailable"
                    onAvailabilityChanged?(.unavailable(reason))
                }
            }
            return
        }

        if let response = Self.parseResponse(from: line) {
            onResponse?(response)
        }
    }

    private static func parseResponse(from raw: String) -> BridgeResponse? {
        guard let data = raw.data(using: .utf8) else {
            return BridgeResponse(text: raw, requestID: nil)
        }

        guard let object = try? JSONSerialization.jsonObject(with: data) else {
            return BridgeResponse(text: raw, requestID: nil)
        }

        if let dictionary = object as? [String: Any] {
            let requestID = firstString(in: dictionary, keys: ["request_id", "requestId", "correlation_id", "correlationId", "id"])
            let isPartial = dictionary["partial"] as? Bool
                ?? dictionary["streaming"] as? Bool
                ?? dictionary["stream"] as? Bool
                ?? dictionary["is_partial"] as? Bool
                ?? (dictionary["delta"] != nil || dictionary["chunk"] != nil)
            let isFinal = dictionary["final"] as? Bool
                ?? dictionary["done"] as? Bool
                ?? dictionary["is_final"] as? Bool
                ?? !isPartial
            let text = extractResponseText(from: dictionary)
            return text.map {
                BridgeResponse(text: $0, requestID: requestID, isPartial: isPartial, isFinal: isFinal)
            }
        }

        if let array = object as? [Any] {
            let combined = array.compactMap { item -> String? in
                if let text = item as? String { return text }
                if let dict = item as? [String: Any] { return extractResponseText(from: dict) }
                return nil
            }.joined(separator: "\n")
            return combined.isEmpty ? nil : BridgeResponse(text: combined, requestID: nil)
        }

        return BridgeResponse(text: raw, requestID: nil)
    }

    private static func extractResponseText(from dictionary: [String: Any]) -> String? {
        for key in ["delta", "chunk", "text", "response", "message", "content"] {
            if let value = dictionary[key] as? String, !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                return value
            }
            if let nested = dictionary[key] as? [String: Any], let nestedText = extractResponseText(from: nested) {
                return nestedText
            }
        }
        return nil
    }

    private static func firstString(in dictionary: [String: Any], keys: [String]) -> String? {
        for key in keys {
            if let value = dictionary[key] as? String, !value.isEmpty {
                return value
            }
        }
        return nil
    }

    private static func extractError(from raw: String) -> String? {
        guard !raw.isEmpty else { return nil }
        if let data = raw.data(using: .utf8),
           let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let reason = object["reason"] as? String {
            return reason
        }
        return raw
    }

    private var producerScript: String {
        #"""
import json
import os
import sys
from datetime import datetime, timezone

try:
    from kafka import KafkaProducer
except Exception as exc:
    print(json.dumps({"ok": False, "reason": f"kafka-python unavailable: {exc}"}))
    sys.exit(2)

request_id = sys.argv[1]
client_id = sys.argv[2]
text = sys.argv[3]
bootstrap = os.environ.get("BRAINCHAT_BROKERS", "localhost:9092")
topic = os.environ.get("BRAINCHAT_INPUT_TOPIC", "brain.voice.input")

payload = {
    "request_id": request_id,
    "client_id": client_id,
    "source": "brain-chat",
    "platform": "macOS",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "text": text,
}

try:
    producer = KafkaProducer(
        bootstrap_servers=bootstrap,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        retries=1,
        acks="all",
    )
    future = producer.send(topic, payload)
    future.get(timeout=5)
    producer.flush(timeout=5)
    producer.close()
    print(json.dumps({"ok": True}))
except Exception as exc:
    print(json.dumps({"ok": False, "reason": str(exc)}))
    sys.exit(1)
"""#
    }

    private var consumerScript: String {
        #"""
import json
import os
import sys
import time

bootstrap = os.environ.get("BRAINCHAT_BROKERS", "localhost:9092")
topic = os.environ.get("BRAINCHAT_RESPONSE_TOPIC", "brain.voice.response")
client_id = os.environ.get("BRAINCHAT_CLIENT_ID", "brain-chat-macos-swift")

try:
    from kafka import KafkaConsumer
except Exception as exc:
    print("__STATUS__:" + json.dumps({"state": "unavailable", "reason": f"kafka-python unavailable: {exc}"}), flush=True)
    sys.exit(2)

while True:
    consumer = None
    try:
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap,
            client_id=client_id,
            group_id=f"{client_id}-responses",
            auto_offset_reset="latest",
            enable_auto_commit=True,
            consumer_timeout_ms=1000,
            value_deserializer=lambda value: value.decode("utf-8"),
        )
        consumer.topics()
        print("__STATUS__:" + json.dumps({"state": "connected"}), flush=True)

        while True:
            for message in consumer:
                print(message.value, flush=True)
    except Exception as exc:
        print("__STATUS__:" + json.dumps({"state": "unavailable", "reason": str(exc)}), flush=True)
        time.sleep(3)
    finally:
        if consumer is not None:
            try:
                consumer.close()
            except Exception:
                pass
"""#
    }
}

enum TerminalANSI {
    static let escape = "\u{001B}["
    static let reset = escape + "0m"
    static let bold = escape + "1m"
    static let dim = escape + "2m"
    static let red = escape + "31m"
    static let green = escape + "32m"
    static let yellow = escape + "33m"
    static let blue = escape + "34m"
    static let magenta = escape + "35m"
    static let cyan = escape + "36m"
    static let white = escape + "37m"
    static let clearLine = escape + "2K"
    static let saveCursor = escape + "s"
    static let restoreCursor = escape + "u"
    static let hideCursor = escape + "?25l"
    static let showCursor = escape + "?25h"
}

// MARK: - Chat Modes

enum ChatMode: String, CaseIterable {
    case chat     = "chat"
    case code     = "code"
    case terminal = "terminal"
    case yolo     = "yolo"
    case voice    = "voice"
    case work     = "work"

    var displayName: String {
        switch self {
        case .chat:     return "Chat"
        case .code:     return "Code"
        case .terminal: return "Terminal"
        case .yolo:     return "YOLO"
        case .voice:    return "Voice"
        case .work:     return "Work"
        }
    }

    var switchCommand: String { "/\(rawValue)" }

    var promptANSIColor: String {
        switch self {
        case .chat:     return TerminalANSI.cyan
        case .code:     return TerminalANSI.yellow
        case .terminal: return TerminalANSI.magenta
        case .yolo:     return TerminalANSI.red
        case .voice:    return TerminalANSI.green
        case .work:     return TerminalANSI.blue
        }
    }

    var systemPrompt: String {
        switch self {
        case .chat:     return "You are Iris Lumina, a concise AI assistant for Joseph (blind, VoiceOver user). Be brief and clear."
        case .code:     return "You are an expert coding assistant. Use triple-backtick code blocks with language names. Support: explain, suggest, fix."
        case .terminal: return "You are a macOS terminal expert. Provide exact shell commands, one sentence explanation each."
        case .yolo:     return "You are an autonomous task executor. List all steps, flag destructive operations before proceeding."
        case .voice:    return "You respond to voice commands. Max 2 sentences. No markdown or code blocks. Speak naturally."
        case .work:     return "You are a professional CITB development assistant. Be formal. Help with JIRA, PRs, and technical docs."
        }
    }

    var llmModel: String {
        switch self {
        case .chat, .terminal, .voice: return "llama3.2:3b"
        case .code, .yolo, .work:      return "llama3.1:8b"
        }
    }

    var speaksResponses: Bool {
        // ALWAYS speak responses - Joseph is blind and needs audio feedback
        return true
    }

    var modeDescription: String {
        switch self {
        case .chat:     return "General conversation with voice responses"
        case .code:     return "Code assistance (explain / suggest / fix)"
        case .terminal: return "Shell command help — prefix ! to execute"
        case .yolo:     return "Autonomous task execution via brain.yolo.commands"
        case .voice:    return "Short voice-optimised responses for hands-free use"
        case .work:     return "CITB professional mode: JIRA, PRs, formal tone"
        }
    }
}

struct ModePreferences {
    private static let key = "brainchat.current_mode"
    static func load() -> ChatMode {
        if let raw = UserDefaults.standard.string(forKey: key),
           let mode = ChatMode(rawValue: raw) { return mode }
        return .chat
    }
    static func save(_ mode: ChatMode) {
        UserDefaults.standard.set(mode.rawValue, forKey: key)
    }
}

// MARK: - LLM Orchestration Mode

/// Defines how BrainChat routes LLM queries.
enum LLMMode: String, CaseIterable {
    case single = "single"
    case multiBot = "multi_bot"
    case consensus = "consensus"

    var displayName: String {
        switch self {
        case .single:    return "Single LLM"
        case .multiBot:  return "Multi-Bot"
        case .consensus: return "Consensus"
        }
    }

    var accessibilityDescription: String {
        switch self {
        case .single:    return "Single L L M mode. All queries go to one provider."
        case .multiBot:  return "Multi-bot mode. Primary L L M orchestrates others."
        case .consensus: return "Consensus mode. All L L Ms vote and majority wins."
        }
    }
}

/// Supported LLM providers for orchestration.
enum LLMProvider: String, CaseIterable, Codable {
    case ollama  = "ollama"
    case groq    = "groq"
    case claude  = "claude"
    case gemini  = "gemini"
    case openai  = "openai"

    var displayName: String {
        switch self {
        case .ollama: return "Ollama (Local)"
        case .groq:   return "Groq (Instant)"
        case .claude: return "Claude (Anthropic)"
        case .gemini: return "Gemini (Google)"
        case .openai: return "OpenAI (GPT)"
        }
    }

    var shortName: String {
        switch self {
        case .ollama: return "Ollama"
        case .groq:   return "Groq"
        case .claude: return "Claude"
        case .gemini: return "Gemini"
        case .openai: return "OpenAI"
        }
    }

    var defaultModel: String {
        switch self {
        case .ollama: return "llama3.2:3b"
        case .groq:   return "llama-3.1-8b-instant"
        case .claude: return "claude-sonnet-4-20250514"
        case .gemini: return "gemini-2.5-flash"
        case .openai: return "gpt-4o"
        }
    }

    var baseURL: URL {
        switch self {
        case .ollama: return URL(string: "http://localhost:11434/v1/chat/completions")!
        case .groq:   return URL(string: "https://api.groq.com/openai/v1/chat/completions")!
        case .claude: return URL(string: "https://api.anthropic.com/v1/messages")!
        case .gemini: return URL(string: "https://generativelanguage.googleapis.com/v1beta/models")!
        case .openai: return URL(string: "https://api.openai.com/v1/chat/completions")!
        }
    }

    var requiresAPIKey: Bool {
        switch self {
        case .ollama: return false
        case .groq, .claude, .gemini, .openai: return true
        }
    }

    var isFree: Bool {
        switch self {
        case .ollama, .groq: return true
        case .claude, .gemini, .openai: return false
        }
    }
}

// MARK: - Security Role System

/// Security roles for controlling BrainChat capabilities.
/// Based on 4-tier security model for accessibility-first AI assistants.
enum SecurityRole: String, CaseIterable, Codable {
    case developer = "developer"    // Full access, can modify system
    case admin = "admin"            // Admin access, safe operations only
    case user = "user"              // Standard user, limited capabilities  
    case guest = "guest"            // Read-only, very limited access
    
    var displayName: String {
        switch self {
        case .developer: return "Developer"
        case .admin:     return "Admin"
        case .user:      return "User"
        case .guest:     return "Guest"
        }
    }
    
    var accessibilityDescription: String {
        switch self {
        case .developer: return "Developer role. Full system access including code execution and configuration changes."
        case .admin:     return "Admin role. Administrative access with safety guardrails."
        case .user:      return "User role. Standard access for daily tasks."
        case .guest:     return "Guest role. Read-only access with limited features."
        }
    }
    
    /// What capabilities this role allows
    var allowsCodeExecution: Bool {
        switch self {
        case .developer: return true
        case .admin:     return true
        case .user:      return false
        case .guest:     return false
        }
    }
    
    var allowsYOLOMode: Bool {
        switch self {
        case .developer: return true
        case .admin:     return true
        case .user:      return false
        case .guest:     return false
        }
    }
    
    var allowsSystemCommands: Bool {
        switch self {
        case .developer: return true
        case .admin:     return true
        case .user:      return false
        case .guest:     return false
        }
    }
    
    var allowsRAGStorage: Bool {
        switch self {
        case .developer, .admin, .user: return true
        case .guest: return false
        }
    }
    
    var maxDailyQueries: Int {
        switch self {
        case .developer: return Int.max
        case .admin:     return 10000
        case .user:      return 1000
        case .guest:     return 100
        }
    }
}

/// Persisted security role settings
struct SecuritySettings {
    private static let roleKey = "brainchat.security_role"
    
    static var currentRole: SecurityRole {
        get {
            if let raw = UserDefaults.standard.string(forKey: roleKey),
               let role = SecurityRole(rawValue: raw) { return role }
            return .developer  // Default to developer for Joseph
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: roleKey) }
    }
}

// MARK: - Voice Engine Configuration

/// Available voice engines for text-to-speech output.
enum VoiceEngine: String, CaseIterable, Codable {
    case systemSay = "say"              // macOS `say` command (most reliable)
    case avSpeech = "avspeech"          // AVSpeechSynthesizer (native Swift)
    case cartesia = "cartesia"          // Cartesia TTS API (ultra-fast)
    case elevenLabs = "elevenlabs"      // ElevenLabs (high quality)
    
    var displayName: String {
        switch self {
        case .systemSay:  return "System Say"
        case .avSpeech:   return "AV Speech"
        case .cartesia:   return "Cartesia"
        case .elevenLabs: return "Eleven Labs"
        }
    }
    
    var accessibilityDescription: String {
        switch self {
        case .systemSay:  return "Mac OS system say command. Most reliable for Voice Over users."
        case .avSpeech:   return "Native A V Speech Synthesizer. Good quality, built-in."
        case .cartesia:   return "Cartesia cloud T T S. Ultra-fast, low latency."
        case .elevenLabs: return "Eleven Labs cloud T T S. Highest quality voices."
        }
    }
    
    var isLocal: Bool {
        switch self {
        case .systemSay, .avSpeech: return true
        case .cartesia, .elevenLabs: return false
        }
    }
    
    var requiresAPIKey: Bool {
        switch self {
        case .systemSay, .avSpeech: return false
        case .cartesia, .elevenLabs: return true
        }
    }
}

/// Available voice options for the selected engine
enum VoiceOption: String, CaseIterable, Codable {
    // System voices (macOS)
    case karen = "Karen"                // Australian English (PREFERRED for Joseph)
    case samantha = "Samantha"          // US English
    case daniel = "Daniel"              // British English
    case moira = "Moira"                // Irish English
    case tessa = "Tessa"                // South African English
    case fiona = "Fiona"                // Scottish English
    case veena = "Veena"                // Indian English
    
    var displayName: String { rawValue }
    
    var accessibilityDescription: String {
        switch self {
        case .karen:    return "Karen. Australian English voice. Preferred for Joseph."
        case .samantha: return "Samantha. American English voice."
        case .daniel:   return "Daniel. British English voice."
        case .moira:    return "Moira. Irish English voice."
        case .tessa:    return "Tessa. South African English voice."
        case .fiona:    return "Fiona. Scottish English voice."
        case .veena:    return "Veena. Indian English voice."
        }
    }
    
    var locale: String {
        switch self {
        case .karen:    return "en-AU"
        case .samantha: return "en-US"
        case .daniel:   return "en-GB"
        case .moira:    return "en-IE"
        case .tessa:    return "en-ZA"
        case .fiona:    return "en-SC"
        case .veena:    return "en-IN"
        }
    }
}

/// Persisted voice settings
struct VoiceSettings {
    private static let engineKey = "brainchat.voice_engine"
    private static let voiceKey = "brainchat.voice_option"
    private static let rateKey = "brainchat.voice_rate"
    private static let enabledKey = "brainchat.voice_enabled"
    
    static var currentEngine: VoiceEngine {
        get {
            if let raw = UserDefaults.standard.string(forKey: engineKey),
               let engine = VoiceEngine(rawValue: raw) { return engine }
            return .systemSay  // Default to most reliable
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: engineKey) }
    }
    
    static var currentVoice: VoiceOption {
        get {
            if let raw = UserDefaults.standard.string(forKey: voiceKey),
               let voice = VoiceOption(rawValue: raw) { return voice }
            return .karen  // Default to Karen for Joseph
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: voiceKey) }
    }
    
    static var speechRate: Int {
        get { 
            let rate = UserDefaults.standard.integer(forKey: rateKey)
            return rate > 0 ? rate : 175  // Default 175 WPM
        }
        set { UserDefaults.standard.set(newValue, forKey: rateKey) }
    }
    
    static var isEnabled: Bool {
        get { UserDefaults.standard.object(forKey: enabledKey) as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: enabledKey) }
    }
}

// MARK: - Dictation Engine Configuration

/// Available dictation/speech recognition engines
enum DictationEngine: String, CaseIterable, Codable {
    case apple = "apple"          // Apple SFSpeechRecognizer (default)
    case whisper = "whisper"      // OpenAI Whisper (local or API)
    case deepgram = "deepgram"    // Deepgram API (fast, accurate)
    
    var displayName: String {
        switch self {
        case .apple:    return "Apple Speech"
        case .whisper:  return "Whisper"
        case .deepgram: return "Deepgram"
        }
    }
    
    var accessibilityDescription: String {
        switch self {
        case .apple:    return "Apple Speech Recognition. Built-in, works offline."
        case .whisper:  return "Open A I Whisper. High accuracy, supports many languages."
        case .deepgram: return "Deepgram. Real-time transcription, very fast."
        }
    }
    
    var isLocal: Bool {
        switch self {
        case .apple: return true
        case .whisper: return true  // Can run locally with Whisper.cpp
        case .deepgram: return false
        }
    }
}

/// Persisted dictation settings
struct DictationSettings {
    private static let engineKey = "brainchat.dictation_engine"
    private static let localeKey = "brainchat.dictation_locale"
    
    static var currentEngine: DictationEngine {
        get {
            if let raw = UserDefaults.standard.string(forKey: engineKey),
               let engine = DictationEngine(rawValue: raw) { return engine }
            return .apple  // Default to Apple
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: engineKey) }
    }
    
    static var locale: String {
        get { UserDefaults.standard.string(forKey: localeKey) ?? "en-AU" }
        set { UserDefaults.standard.set(newValue, forKey: localeKey) }
    }
}

// MARK: - RAG (Retrieval Augmented Generation) Service

/// Persisted settings for RAG. Stored in UserDefaults.
struct RAGSettings {
    private static let enabledKey = "brainchat.rag_enabled"
    private static let storeConversationsKey = "brainchat.rag_store_conversations"
    private static let neo4jHostKey = "brainchat.rag_neo4j_host"
    private static let neo4jPortKey = "brainchat.rag_neo4j_port"
    private static let neo4jCredentialsKey = "brainchat.rag_neo4j_credentials"
    
    static var isEnabled: Bool {
        get { UserDefaults.standard.object(forKey: enabledKey) as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: enabledKey) }
    }
    
    static var storeConversations: Bool {
        get { UserDefaults.standard.object(forKey: storeConversationsKey) as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: storeConversationsKey) }
    }
    
    static var neo4jHost: String {
        get { UserDefaults.standard.string(forKey: neo4jHostKey) ?? "localhost" }
        set { UserDefaults.standard.set(newValue, forKey: neo4jHostKey) }
    }
    
    static var neo4jPort: Int {
        get { UserDefaults.standard.integer(forKey: neo4jPortKey) != 0 
              ? UserDefaults.standard.integer(forKey: neo4jPortKey) : 7687 }
        set { UserDefaults.standard.set(newValue, forKey: neo4jPortKey) }
    }
    
    /// Neo4j credentials in format "user:password"
    static var neo4jCredentials: String {
        get {
            // Priority: UserDefaults > ENV > default
            if let saved = UserDefaults.standard.string(forKey: neo4jCredentialsKey), !saved.isEmpty {
                return saved
            }
            if let envAuth = ProcessInfo.processInfo.environment["NEO4J_AUTH"] {
                return envAuth.replacingOccurrences(of: "/", with: ":")
            }
            return "neo4j:Brain2026"  // Default for brain docker-compose
        }
        set { UserDefaults.standard.set(newValue, forKey: neo4jCredentialsKey) }
    }
}

/// RAG Service for knowledge graph retrieval and storage using Neo4j.
/// Enriches prompts with relevant context and stores conversations for future retrieval.
final class RAGService {
    static let shared = RAGService()
    
    private let queue = DispatchQueue(label: "brainchat.rag", qos: .userInitiated)
    private var isNeo4jAvailable = false
    private var lastHealthCheck: Date?
    private let healthCheckInterval: TimeInterval = 60 // Re-check every minute
    
    // Neo4j connection info
    private var neo4jHost: String { RAGSettings.neo4jHost }
    private var neo4jPort: Int { RAGSettings.neo4jPort }
    private var neo4jBoltURL: String { "bolt://\(neo4jHost):\(neo4jPort)" }
    private var neo4jHTTPURL: String { "http://\(neo4jHost):7474" }
    
    // Brain MCP tool endpoint (if available)
    private let brainMCPEndpoint = "http://localhost:8765"
    
    var onStatusUpdate: ((String) -> Void)?
    
    private init() {
        // Check Neo4j availability on init
        checkNeo4jHealth()
    }
    
    // MARK: - Health Check
    
    func checkNeo4jHealth(completion: ((Bool) -> Void)? = nil) {
        queue.async { [weak self] in
            guard let self else { return }
            
            // Use HTTP API for health check (simpler than Bolt protocol)
            let healthURL = URL(string: "\(self.neo4jHTTPURL)/db/neo4j/tx")!
            var request = URLRequest(url: healthURL)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue("Basic \(self.basicAuthHeader)", forHTTPHeaderField: "Authorization")
            request.timeoutInterval = 3
            
            // Simple query to test connection
            let body: [String: Any] = [
                "statements": [["statement": "RETURN 1 as test"]]
            ]
            request.httpBody = try? JSONSerialization.data(withJSONObject: body)
            
            let task = URLSession.shared.dataTask(with: request) { [weak self] _, response, error in
                let available = (response as? HTTPURLResponse)?.statusCode == 200
                self?.isNeo4jAvailable = available
                self?.lastHealthCheck = Date()
                DispatchQueue.main.async { completion?(available) }
            }
            task.resume()
        }
    }
    
    private var basicAuthHeader: String {
        let credentials = RAGSettings.neo4jCredentials
        return Data(credentials.utf8).base64EncodedString()
    }
    
    var isAvailable: Bool {
        // Re-check if stale
        if let lastCheck = lastHealthCheck,
           Date().timeIntervalSince(lastCheck) > healthCheckInterval {
            checkNeo4jHealth()
        }
        return isNeo4jAvailable && RAGSettings.isEnabled
    }
    
    // MARK: - Query RAG for Context
    
    /// Query Neo4j for relevant context based on the user's prompt.
    func queryRAG(topic: String, completion: @escaping ([String]) -> Void) {
        guard isAvailable else {
            completion([])
            return
        }
        
        queue.async { [weak self] in
            guard let self else { completion([]); return }
            
            // Extract keywords from the topic
            let keywords = self.extractKeywords(from: topic)
            guard !keywords.isEmpty else { completion([]); return }
            
            // Build Cypher query to find related knowledge
            // Uses multiple separate queries combined for robustness
            let cypher = """
            // Search emails for relevant context
            MATCH (e:Email)
            WHERE toLower(e.subject) CONTAINS toLower($keyword)
               OR toLower(coalesce(e.body, '')) CONTAINS toLower($keyword)
            WITH 'Email from ' + coalesce(e.sender, 'unknown') + ': ' + e.subject AS context
            RETURN DISTINCT context
            LIMIT 4
            
            UNION
            
            // Search Teams messages
            MATCH (t:TeamsMessage)
            WHERE toLower(coalesce(t.content, '')) CONTAINS toLower($keyword)
            WITH 'Teams: ' + substring(coalesce(t.content, ''), 0, 150) AS context
            RETURN DISTINCT context
            LIMIT 3
            
            UNION
            
            // Search stored conversations
            MATCH (c:Conversation)
            WHERE toLower(c.user_message) CONTAINS toLower($keyword)
               OR toLower(c.ai_response) CONTAINS toLower($keyword)
            WITH 'Previous chat: ' + c.user_message AS context
            RETURN DISTINCT context
            LIMIT 2
            """
            
            self.executeCypherQuery(cypher, params: ["keyword": keywords.first ?? topic]) { results in
                let contexts = results.compactMap { $0["context"] as? String }
                    .filter { !$0.isEmpty }
                DispatchQueue.main.async { completion(contexts) }
            }
        }
    }
    
    /// Async wrapper for queryRAG
    func queryRAG(topic: String) async -> [String] {
        await withCheckedContinuation { continuation in
            queryRAG(topic: topic) { contexts in
                continuation.resume(returning: contexts)
            }
        }
    }
    
    // MARK: - Enrich Prompt with RAG Context
    
    /// Enriches a user prompt with relevant context from the knowledge graph.
    func enrichPromptWithRAG(_ prompt: String, completion: @escaping (String) -> Void) {
        guard RAGSettings.isEnabled else {
            completion(prompt)
            return
        }
        
        updateStatus("Searching knowledge graph…")
        
        queryRAG(topic: prompt) { [weak self] contexts in
            if contexts.isEmpty {
                self?.updateStatus("No RAG context found, using prompt as-is")
                completion(prompt)
                return
            }
            
            self?.updateStatus("Found \(contexts.count) relevant contexts")
            
            let enrichedPrompt = """
            Context from knowledge graph (use if relevant):
            \(contexts.enumerated().map { "[\($0.offset + 1)] \($0.element)" }.joined(separator: "\n"))
            
            User question: \(prompt)
            
            Instructions: Use the context above if it helps answer the question. If the context isn't relevant, ignore it and answer based on your knowledge. Don't mention the context explicitly unless asked.
            """
            
            completion(enrichedPrompt)
        }
    }
    
    /// Async wrapper for enrichPromptWithRAG
    func enrichPromptWithRAG(_ prompt: String) async -> String {
        await withCheckedContinuation { continuation in
            enrichPromptWithRAG(prompt) { enrichedPrompt in
                continuation.resume(returning: enrichedPrompt)
            }
        }
    }
    
    // MARK: - Store Conversations in RAG
    
    /// Stores a conversation in Neo4j for future retrieval.
    func storeConversation(userMessage: String, aiResponse: String, mode: String = "chat") {
        guard RAGSettings.isEnabled && RAGSettings.storeConversations else { return }
        guard isNeo4jAvailable else { return }
        
        queue.async { [weak self] in
            guard let self else { return }
            
            let timestamp = ISO8601DateFormatter().string(from: Date())
            let conversationID = UUID().uuidString
            
            // Store conversation node and link to topics
            let cypher = """
            // Create conversation node
            CREATE (c:Conversation {
                id: $id,
                user_message: $userMessage,
                ai_response: $aiResponse,
                mode: $mode,
                timestamp: datetime($timestamp),
                source: 'BrainChat'
            })
            
            // Extract and link topics (simplified keyword extraction)
            WITH c
            UNWIND $keywords AS keyword
            MERGE (t:Topic {name: toLower(keyword)})
            ON CREATE SET t.created = datetime()
            MERGE (c)-[:ABOUT]->(t)
            
            RETURN c.id AS id
            """
            
            let keywords = self.extractKeywords(from: userMessage + " " + aiResponse)
            
            self.executeCypherQuery(cypher, params: [
                "id": conversationID,
                "userMessage": userMessage,
                "aiResponse": String(aiResponse.prefix(2000)), // Limit response size
                "mode": mode,
                "timestamp": timestamp,
                "keywords": keywords
            ]) { _ in
                // Silently stored
            }
        }
    }
    
    // MARK: - Semantic Search (via Brain MCP)
    
    /// Performs semantic search using brain MCP tools if available.
    func semanticSearch(_ query: String, completion: @escaping ([String]) -> Void) {
        // Try brain-search MCP tool first
        let mcpURL = URL(string: "\(brainMCPEndpoint)/search")!
        var request = URLRequest(url: mcpURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 5
        request.httpBody = try? JSONSerialization.data(withJSONObject: ["term": query])
        
        let task = URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            guard let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let results = json["results"] as? [[String: Any]] else {
                // Fallback to direct Neo4j query
                self?.queryRAG(topic: query, completion: completion)
                return
            }
            
            let contexts = results.compactMap { $0["content"] as? String ?? $0["summary"] as? String }
            DispatchQueue.main.async { completion(contexts) }
        }
        task.resume()
    }
    
    // MARK: - Private Helpers
    
    private func extractKeywords(from text: String) -> [String] {
        // Simple keyword extraction - remove common words and keep meaningful terms
        let stopWords = Set(["the", "a", "an", "is", "are", "was", "were", "be", "been",
                            "being", "have", "has", "had", "do", "does", "did", "will",
                            "would", "could", "should", "may", "might", "can", "to", "of",
                            "in", "for", "on", "with", "at", "by", "from", "as", "into",
                            "through", "during", "before", "after", "above", "below",
                            "between", "under", "again", "further", "then", "once", "here",
                            "there", "when", "where", "why", "how", "all", "each", "few",
                            "more", "most", "other", "some", "such", "no", "nor", "not",
                            "only", "own", "same", "so", "than", "too", "very", "just",
                            "and", "but", "if", "or", "because", "until", "while", "about",
                            "what", "which", "who", "whom", "this", "that", "these", "those",
                            "am", "i", "me", "my", "myself", "we", "our", "ours", "you",
                            "your", "yours", "he", "him", "his", "she", "her", "hers", "it",
                            "its", "they", "them", "their", "theirs"])
        
        let words = text.lowercased()
            .components(separatedBy: CharacterSet.alphanumerics.inverted)
            .filter { $0.count > 2 && !stopWords.contains($0) }
        
        // Return unique keywords, prioritizing longer words
        var seen = Set<String>()
        return words.sorted { $0.count > $1.count }
            .filter { seen.insert($0).inserted }
            .prefix(5)
            .map { String($0) }
    }
    
    private func executeCypherQuery(_ cypher: String, params: [String: Any], completion: @escaping ([[String: Any]]) -> Void) {
        let url = URL(string: "\(neo4jHTTPURL)/db/neo4j/tx/commit")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Basic \(basicAuthHeader)", forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 10
        
        let body: [String: Any] = [
            "statements": [[
                "statement": cypher,
                "parameters": params
            ]]
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        let task = URLSession.shared.dataTask(with: request) { data, _, error in
            guard let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let results = json["results"] as? [[String: Any]],
                  let firstResult = results.first,
                  let dataRows = firstResult["data"] as? [[String: Any]] else {
                completion([])
                return
            }
            
            // Extract column values
            let columns = firstResult["columns"] as? [String] ?? []
            let rows: [[String: Any]] = dataRows.compactMap { row in
                guard let rowData = row["row"] as? [Any] else { return nil }
                var dict: [String: Any] = [:]
                for (i, col) in columns.enumerated() where i < rowData.count {
                    dict[col] = rowData[i]
                }
                return dict
            }
            
            completion(rows)
        }
        task.resume()
    }
    
    private func updateStatus(_ message: String) {
        DispatchQueue.main.async { [weak self] in
            self?.onStatusUpdate?(message)
        }
    }
}

/// UI commands for RAG settings
final class RAGSelectorUI {
    func handleCommand(_ input: String) -> Bool {
        let cmd = input.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        
        if cmd == "/rag" || cmd == "/rag status" {
            printStatus()
            return true
        }
        
        if cmd == "/rag on" || cmd == "/rag enable" {
            RAGSettings.isEnabled = true
            print("✅ RAG enabled - prompts will be enriched with knowledge graph context")
            return true
        }
        
        if cmd == "/rag off" || cmd == "/rag disable" {
            RAGSettings.isEnabled = false
            print("❌ RAG disabled - prompts will be sent without enrichment")
            return true
        }
        
        if cmd == "/rag store on" {
            RAGSettings.storeConversations = true
            print("✅ Conversation storage enabled - chats will be saved to Neo4j")
            return true
        }
        
        if cmd == "/rag store off" {
            RAGSettings.storeConversations = false
            print("❌ Conversation storage disabled")
            return true
        }
        
        if cmd == "/rag health" || cmd == "/rag check" {
            RAGService.shared.checkNeo4jHealth { available in
                if available {
                    print("✅ Neo4j is available at \(RAGSettings.neo4jHost):\(RAGSettings.neo4jPort)")
                } else {
                    print("❌ Neo4j is not available - RAG will be bypassed")
                }
            }
            return true
        }
        
        if cmd.hasPrefix("/rag help") {
            printHelp()
            return true
        }
        
        return false
    }
    
    private func printStatus() {
        let rag = RAGService.shared
        print("""
        RAG Status:
          Enabled: \(RAGSettings.isEnabled ? "Yes" : "No")
          Store Conversations: \(RAGSettings.storeConversations ? "Yes" : "No")
          Neo4j: \(rag.isAvailable ? "Connected" : "Unavailable")
          Host: \(RAGSettings.neo4jHost):\(RAGSettings.neo4jPort)
        """)
    }
    
    private func printHelp() {
        print("""
        RAG Commands:
          /rag              - Show RAG status
          /rag on           - Enable RAG enrichment
          /rag off          - Disable RAG enrichment
          /rag store on     - Enable conversation storage
          /rag store off    - Disable conversation storage
          /rag health       - Check Neo4j connection
          /rag help         - Show this help
        """)
    }
}

/// Persisted settings for LLM orchestration. Stored in UserDefaults (not in repo).
struct LLMOrchestratorSettings {
    private static let modeKey = "brainchat.llm_mode"
    private static let primaryKey = "brainchat.primary_llm"
    private static let secondaryKey = "brainchat.secondary_llms"

    static var mode: LLMMode {
        get {
            if let raw = UserDefaults.standard.string(forKey: modeKey),
               let m = LLMMode(rawValue: raw) { return m }
            return .single
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: modeKey) }
    }

    static var primaryLLM: LLMProvider {
        get {
            if let raw = UserDefaults.standard.string(forKey: primaryKey),
               let p = LLMProvider(rawValue: raw) { return p }
            return .ollama
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: primaryKey) }
    }

    static var secondaryLLMs: [LLMProvider] {
        get {
            guard let data = UserDefaults.standard.data(forKey: secondaryKey),
                  let decoded = try? JSONDecoder().decode([LLMProvider].self, from: data) else {
                return []
            }
            return decoded
        }
        set {
            if let encoded = try? JSONEncoder().encode(newValue) {
                UserDefaults.standard.set(encoded, forKey: secondaryKey)
            }
        }
    }
}

/// Orchestrates multiple LLM providers with single, multi-bot, and consensus modes.
/// Thread-safe and designed for accessibility (VoiceOver-friendly status updates).
final class LLMOrchestrator: NSObject {
    static let shared = LLMOrchestrator()

    var primaryLLM: LLMProvider {
        didSet { LLMOrchestratorSettings.primaryLLM = primaryLLM }
    }
    var secondaryLLMs: [LLMProvider] {
        didSet { LLMOrchestratorSettings.secondaryLLMs = secondaryLLMs }
    }
    var mode: LLMMode {
        didSet { LLMOrchestratorSettings.mode = mode }
    }

    /// API keys indexed by provider (stored in memory, loaded from Keychain/env).
    private var apiKeys: [LLMProvider: String] = [:]

    /// Called on main thread with status updates for VoiceOver.
    var onStatusUpdate: ((String) -> Void)?

    private let queue = DispatchQueue(label: "brainchat.orchestrator", qos: .userInitiated)

    private override init() {
        self.mode = LLMOrchestratorSettings.mode
        self.primaryLLM = LLMOrchestratorSettings.primaryLLM
        self.secondaryLLMs = LLMOrchestratorSettings.secondaryLLMs
        super.init()
        loadAPIKeysFromEnvironment()
    }

    // MARK: - API Key Management

    func setAPIKey(_ key: String, for provider: LLMProvider) {
        apiKeys[provider] = key
    }

    func apiKey(for provider: LLMProvider) -> String? {
        apiKeys[provider]
    }

    private func loadAPIKeysFromEnvironment() {
        let env = ProcessInfo.processInfo.environment
        if let key = env["GROQ_API_KEY"] { apiKeys[.groq] = key }
        if let key = env["CLAUDE_API_KEY"] ?? env["ANTHROPIC_API_KEY"] { apiKeys[.claude] = key }
        if let key = env["GEMINI_API_KEY"] { apiKeys[.gemini] = key }
        if let key = env["OPENAI_API_KEY"] { apiKeys[.openai] = key }
    }

    // MARK: - Query Routing

    /// Main entry point for queries. Routes based on current mode.
    func query(_ prompt: String, systemPrompt: String = "", completion: @escaping (String, Error?) -> Void) {
        queue.async { [weak self] in
            guard let self else { return }
            switch self.mode {
            case .single:
                self.querySingle(prompt, systemPrompt: systemPrompt, completion: completion)
            case .multiBot:
                self.queryMultiBot(prompt, systemPrompt: systemPrompt, completion: completion)
            case .consensus:
                self.queryConsensus(prompt, systemPrompt: systemPrompt, completion: completion)
            }
        }
    }

    /// Async/await wrapper for query.
    func query(_ prompt: String, systemPrompt: String = "") async -> String {
        await withCheckedContinuation { continuation in
            query(prompt, systemPrompt: systemPrompt) { response, _ in
                continuation.resume(returning: response)
            }
        }
    }

    // MARK: - Single LLM Mode

    private func querySingle(_ prompt: String, systemPrompt: String, completion: @escaping (String, Error?) -> Void) {
        updateStatus("Querying \(primaryLLM.shortName)…")
        queryLLM(primaryLLM, prompt: prompt, systemPrompt: systemPrompt, completion: completion)
    }

    // MARK: - Multi-Bot Mode (Primary Routes to Others)

    private func queryMultiBot(_ prompt: String, systemPrompt: String, completion: @escaping (String, Error?) -> Void) {
        updateStatus("Primary \(primaryLLM.shortName) analyzing request…")

        let routingPrompt = """
        You are an LLM orchestrator. Analyze this user request and decide which LLM should handle it.
        Available LLMs: \(secondaryLLMs.map(\.shortName).joined(separator: ", "))
        
        For simple questions, respond directly.
        For complex tasks, specify which LLM to delegate to by responding with:
        [DELEGATE:\(secondaryLLMs.first?.rawValue ?? "ollama")] then your delegation instructions.
        
        User request: \(prompt)
        """

        queryLLM(primaryLLM, prompt: routingPrompt, systemPrompt: systemPrompt) { [weak self] response, error in
            guard let self else { return }

            if let error {
                completion(response, error)
                return
            }

            // Check if primary wants to delegate
            if let delegateMatch = response.range(of: #"\[DELEGATE:(\w+)\]"#, options: .regularExpression) {
                let delegateInfo = String(response[delegateMatch])
                let providerName = delegateInfo.replacingOccurrences(of: "[DELEGATE:", with: "")
                    .replacingOccurrences(of: "]", with: "").lowercased()

                if let targetProvider = LLMProvider(rawValue: providerName),
                   self.secondaryLLMs.contains(targetProvider) {
                    self.updateStatus("Delegating to \(targetProvider.shortName)…")
                    self.queryLLM(targetProvider, prompt: prompt, systemPrompt: systemPrompt, completion: completion)
                    return
                }
            }

            // Primary handled it directly
            completion(response, nil)
        }
    }

    // MARK: - Consensus Mode (All LLMs Vote)

    private func queryConsensus(_ prompt: String, systemPrompt: String, completion: @escaping (String, Error?) -> Void) {
        let allProviders = [primaryLLM] + secondaryLLMs
        guard !allProviders.isEmpty else {
            completion("No LLM providers configured.", nil)
            return
        }

        updateStatus("Querying \(allProviders.count) LLMs for consensus…")

        let group = DispatchGroup()
        var responses: [(provider: LLMProvider, response: String)] = []
        let responseLock = NSLock()

        for provider in allProviders {
            group.enter()
            queryLLM(provider, prompt: prompt, systemPrompt: systemPrompt) { response, _ in
                responseLock.lock()
                if !response.isEmpty {
                    responses.append((provider, response))
                }
                responseLock.unlock()
                group.leave()
            }
        }

        group.notify(queue: queue) { [weak self] in
            guard let self else { return }

            if responses.isEmpty {
                completion("All LLM providers failed to respond.", nil)
                return
            }

            // Synthesize consensus
            let synthesis = self.synthesizeConsensus(responses, originalPrompt: prompt)
            self.updateStatus("Consensus reached from \(responses.count) providers.")
            completion(synthesis, nil)
        }
    }

    private func synthesizeConsensus(_ responses: [(provider: LLMProvider, response: String)], originalPrompt: String) -> String {
        guard responses.count > 1 else {
            return responses.first?.response ?? ""
        }

        // Simple synthesis: use primary LLM to combine responses
        let synthesisPrompt = """
        You are synthesizing responses from multiple AI assistants to find consensus.
        Original question: \(originalPrompt)
        
        Responses:
        \(responses.map { "[\($0.provider.shortName)]: \($0.response)" }.joined(separator: "\n\n"))
        
        Provide a unified response that captures the consensus. Note any disagreements.
        """

        var result = ""
        let semaphore = DispatchSemaphore(value: 0)

        queryLLM(primaryLLM, prompt: synthesisPrompt, systemPrompt: "") { response, _ in
            result = response.isEmpty ? responses.first?.response ?? "" : response
            semaphore.signal()
        }

        _ = semaphore.wait(timeout: .now() + 30)
        return result
    }

    // MARK: - Individual LLM Query

    private func queryLLM(_ provider: LLMProvider, prompt: String, systemPrompt: String, completion: @escaping (String, Error?) -> Void) {
        // Build config based on provider
        let effectiveSystemPrompt = systemPrompt.isEmpty
            ? "You are a helpful AI assistant."
            : systemPrompt

        let config = LLMConfig(
            url: provider.baseURL,
            model: provider.defaultModel,
            systemPrompt: effectiveSystemPrompt,
            apiKey: apiKeys[provider]
        )

        var accumulated = ""
        let client = LLMStreamingClient()

        client.stream(
            config: config,
            userText: prompt,
            onToken: { token in accumulated += token },
            onComplete: { fullText, error in
                DispatchQueue.main.async {
                    completion(fullText.isEmpty ? accumulated : fullText, error)
                }
            }
        )
    }

    // MARK: - Status Updates (Accessibility)

    private func updateStatus(_ message: String) {
        DispatchQueue.main.async { [weak self] in
            self?.onStatusUpdate?(message)
        }
    }

    // MARK: - AppleScript Support

    /// Set LLM mode via AppleScript command.
    @objc func setLLMMode(_ modeString: String) -> Bool {
        guard let newMode = LLMMode(rawValue: modeString.lowercased()) else { return false }
        mode = newMode
        return true
    }

    /// Set primary LLM via AppleScript command.
    @objc func setPrimaryLLM(_ providerString: String) -> Bool {
        guard let provider = LLMProvider(rawValue: providerString.lowercased()) else { return false }
        primaryLLM = provider
        return true
    }

    /// Add a secondary LLM via AppleScript command.
    @objc func addSecondaryLLM(_ providerString: String) -> Bool {
        guard let provider = LLMProvider(rawValue: providerString.lowercased()) else { return false }
        if !secondaryLLMs.contains(provider) {
            secondaryLLMs.append(provider)
        }
        return true
    }

    /// Remove a secondary LLM via AppleScript command.
    @objc func removeSecondaryLLM(_ providerString: String) -> Bool {
        guard let provider = LLMProvider(rawValue: providerString.lowercased()) else { return false }
        secondaryLLMs.removeAll { $0 == provider }
        return true
    }

    /// Get current orchestrator status for AppleScript.
    @objc func getStatus() -> String {
        "mode=\(mode.rawValue), primary=\(primaryLLM.rawValue), secondary=[\(secondaryLLMs.map(\.rawValue).joined(separator: ","))]"
    }
}

// MARK: - LLM Selector UI (Keyboard Accessible)

/// A simple terminal-based LLM selector for keyboard navigation.
final class LLMSelectorUI {
    private let orchestrator = LLMOrchestrator.shared

    func printCurrentConfig() {
        print("""
        
        \(TerminalANSI.bold)LLM Configuration\(TerminalANSI.reset)
        ─────────────────────────────────
        Mode:      \(orchestrator.mode.displayName)
        Primary:   \(orchestrator.primaryLLM.displayName)
        Secondary: \(orchestrator.secondaryLLMs.map(\.shortName).joined(separator: ", ").isEmpty ? "None" : orchestrator.secondaryLLMs.map(\.shortName).joined(separator: ", "))
        
        """)
    }

    func printHelp() {
        print("""
        
        \(TerminalANSI.bold)LLM Commands\(TerminalANSI.reset)
        ─────────────────────────────────
        /llm mode single      - Use single LLM (default)
        /llm mode multibot    - Primary LLM orchestrates others
        /llm mode consensus   - All LLMs vote, majority wins
        
        /llm primary ollama   - Set primary to Ollama (local)
        /llm primary groq     - Set primary to Groq (instant)
        /llm primary claude   - Set primary to Claude
        /llm primary gemini   - Set primary to Gemini
        /llm primary openai   - Set primary to OpenAI
        
        /llm add groq         - Add Groq as secondary
        /llm remove groq      - Remove Groq from secondary
        
        /llm status           - Show current configuration
        
        """)
    }

    func handleCommand(_ input: String) -> Bool {
        let parts = input.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
            .split(separator: " ").map(String.init)

        guard parts.first == "/llm", parts.count >= 2 else { return false }

        switch parts[1] {
        case "mode" where parts.count >= 3:
            let modeStr = parts[2]
            if let mode = LLMMode(rawValue: modeStr == "multibot" ? "multi_bot" : modeStr) {
                orchestrator.mode = mode
                print("\(TerminalANSI.green)LLM mode set to \(mode.displayName)\(TerminalANSI.reset)")
            } else {
                print("\(TerminalANSI.red)Unknown mode. Use: single, multibot, consensus\(TerminalANSI.reset)")
            }
            return true

        case "primary" where parts.count >= 3:
            if let provider = LLMProvider(rawValue: parts[2]) {
                orchestrator.primaryLLM = provider
                print("\(TerminalANSI.green)Primary LLM set to \(provider.displayName)\(TerminalANSI.reset)")
            } else {
                print("\(TerminalANSI.red)Unknown provider. Use: ollama, groq, claude, gemini, openai\(TerminalANSI.reset)")
            }
            return true

        case "add" where parts.count >= 3:
            if let provider = LLMProvider(rawValue: parts[2]) {
                _ = orchestrator.addSecondaryLLM(parts[2])
                print("\(TerminalANSI.green)Added \(provider.shortName) as secondary LLM\(TerminalANSI.reset)")
            } else {
                print("\(TerminalANSI.red)Unknown provider\(TerminalANSI.reset)")
            }
            return true

        case "remove" where parts.count >= 3:
            if let provider = LLMProvider(rawValue: parts[2]) {
                _ = orchestrator.removeSecondaryLLM(parts[2])
                print("\(TerminalANSI.green)Removed \(provider.shortName) from secondary LLMs\(TerminalANSI.reset)")
            } else {
                print("\(TerminalANSI.red)Unknown provider\(TerminalANSI.reset)")
            }
            return true

        case "status":
            printCurrentConfig()
            return true

        case "help":
            printHelp()
            return true

        default:
            printHelp()
            return true
        }
    }
}

// MARK: - AppleScript Commands for LLM Orchestrator

final class SetLLMModeCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let modeString = directParameter as? String else {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "No mode provided. Use: single, multi_bot, consensus"
            return nil
        }
        let success = LLMOrchestrator.shared.setLLMMode(modeString)
        if !success {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "Unknown mode: \(modeString). Use: single, multi_bot, consensus"
        }
        return success ? "OK" : nil
    }
}

final class SetPrimaryLLMCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let providerString = directParameter as? String else {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "No provider provided. Use: ollama, groq, claude, gemini, openai"
            return nil
        }
        let success = LLMOrchestrator.shared.setPrimaryLLM(providerString)
        if !success {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "Unknown provider: \(providerString). Use: ollama, groq, claude, gemini, openai"
        }
        return success ? "OK" : nil
    }
}

final class GetLLMStatusCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        LLMOrchestrator.shared.getStatus()
    }
}

final class AddSecondaryLLMCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let providerString = directParameter as? String else {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "No provider provided. Use: ollama, groq, claude, gemini, openai"
            return nil
        }
        let success = LLMOrchestrator.shared.addSecondaryLLM(providerString)
        if !success {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "Unknown provider: \(providerString). Use: ollama, groq, claude, gemini, openai"
        }
        return success ? "OK" : nil
    }
}

final class RemoveSecondaryLLMCommand: NSScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let providerString = directParameter as? String else {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "No provider provided."
            return nil
        }
        let success = LLMOrchestrator.shared.removeSecondaryLLM(providerString)
        if !success {
            scriptErrorNumber = errOSAGeneralError
            scriptErrorString = "Unknown provider: \(providerString)"
        }
        return success ? "OK" : nil
    }
}

// MARK: - LLM Streaming

/// Configuration for a streaming LLM endpoint (OpenAI-compatible or native Ollama).
struct LLMConfig {
    let url: URL
    let model: String
    let systemPrompt: String
    var apiKey: String?
    var temperature: Double
    var maxTokens: Int

    init(url: URL, model: String, systemPrompt: String,
         apiKey: String? = nil, temperature: Double = 0.7, maxTokens: Int = 1024) {
        self.url = url
        self.model = model
        self.systemPrompt = systemPrompt
        self.apiKey = apiKey
        self.temperature = temperature
        self.maxTokens = maxTokens
    }

    /// Default: local Ollama with the llama3.2:3b fast model.
    static let `default` = LLMConfig(
        url: URL(string: "http://localhost:11434/v1/chat/completions")!,
        model: "llama3.2:3b",
        systemPrompt: "You are Iris Lumina, an AI assistant for Joseph, who is blind and uses VoiceOver on macOS. Keep responses concise and clear. No filler phrases."
    )

    static func mode(_ chatMode: ChatMode) -> LLMConfig {
        LLMConfig(
            url: URL(string: "http://localhost:11434/v1/chat/completions")!,
            model: chatMode.llmModel,
            systemPrompt: chatMode.systemPrompt
        )
    }
}

/// Streams LLM responses token-by-token via URLSession delegate callbacks.
///
/// Supported wire formats (auto-detected per line):
///   - OpenAI chat-completion SSE: `data: {"choices":[{"delta":{"content":"…"}}]}`
///   - Ollama `/api/chat` NDJSON:  `{"message":{"content":"…"},"done":false}`
///   - Ollama `/api/generate` NDJSON: `{"response":"…","done":false}`
///
/// **UTF-8 buffer management**: incoming bytes are merged into a tail buffer; only the
/// longest valid UTF-8 prefix is decoded per chunk, leaving any partial multi-byte
/// sequence in the tail for the next data callback.
///
/// **Retry policy**: connection-level errors (refused, timeout, lost) trigger
/// exponential-backoff retries (0.5 s → 1 s → 2 s) *only* when no content has been
/// accumulated yet.  HTTP errors and mid-stream disconnects are not retried.
final class LLMStreamingClient: NSObject, URLSessionDataDelegate {

    enum StreamError: LocalizedError {
        case httpError(Int)
        case connectionFailed(Error)

        var errorDescription: String? {
            switch self {
            case .httpError(let code):       return "HTTP \(code)"
            case .connectionFailed(let err): return err.localizedDescription
            }
        }
    }

    /// `true` while a stream request is in-flight (including retry back-off waits).
    private(set) var isStreaming = false

    // Callbacks — always invoked on the main thread.
    var onToken: ((String) -> Void)?
    var onComplete: ((String, Error?) -> Void)?

    private lazy var session: URLSession = {
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest  = 10    // fast failure for localhost
        cfg.timeoutIntervalForResource = 120   // allow long completions
        cfg.requestCachePolicy = .reloadIgnoringLocalCacheData
        return URLSession(configuration: cfg, delegate: self, delegateQueue: nil)
    }()

    private var currentTask: URLSessionDataTask?

    // Per-stream state
    private var utf8Tail    = Data()   // incomplete UTF-8 tail bytes from the last chunk
    private var lineBuf     = ""       // text assembled since the last newline
    private var accumulated = ""       // full content received so far

    // Retry state
    private var pendingConfig:   LLMConfig?
    private var pendingMessages: [[String: Any]] = []
    private var retries    = 0
    private let maxRetries = 3

    // MARK: Public API

    func stream(config: LLMConfig, userText: String,
                onToken:    @escaping (String) -> Void,
                onComplete: @escaping (String, Error?) -> Void) {
        self.pendingConfig   = config
        self.pendingMessages = [
            ["role": "system", "content": config.systemPrompt],
            ["role": "user",   "content": userText],
        ]
        self.onToken    = onToken
        self.onComplete = onComplete
        retries     = 0
        accumulated = ""
        utf8Tail    = Data()
        lineBuf     = ""
        isStreaming = true
        sendRequest()
    }

    func cancel() {
        isStreaming = false
        currentTask?.cancel()
        currentTask = nil
        session.invalidateAndCancel()   // break URLSession → delegate retain cycle
    }

    // MARK: Private: request

    private func sendRequest() {
        guard let config = pendingConfig else { return }

        var req = URLRequest(url: config.url)
        req.httpMethod = "POST"
        req.setValue("application/json",                     forHTTPHeaderField: "Content-Type")
        req.setValue("text/event-stream, application/json",  forHTTPHeaderField: "Accept")
        if let key = config.apiKey {
            req.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
        }

        let body: [String: Any] = [
            "model":       config.model,
            "messages":    pendingMessages,
            "stream":      true,
            "temperature": config.temperature,
            "max_tokens":  config.maxTokens,
        ]
        guard let bodyData = try? JSONSerialization.data(withJSONObject: body) else {
            finish(error: StreamError.connectionFailed(
                NSError(domain: "LLM", code: -1,
                        userInfo: [NSLocalizedDescriptionKey: "Request serialization failed"])))
            return
        }
        req.httpBody = bodyData

        // Reset per-attempt buffers; accumulated persists across retries.
        utf8Tail = Data()
        lineBuf  = ""

        let task = session.dataTask(with: req)
        currentTask = task
        task.resume()
    }

    // MARK: URLSessionDataDelegate

    func urlSession(_ session: URLSession,
                    dataTask: URLSessionDataTask,
                    didReceive response: URLResponse,
                    completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        guard let http = response as? HTTPURLResponse else {
            completionHandler(.cancel)
            finish(error: StreamError.httpError(-1))
            return
        }
        if (200..<300).contains(http.statusCode) {
            completionHandler(.allow)
        } else {
            completionHandler(.cancel)
            finish(error: StreamError.httpError(http.statusCode))
        }
    }

    func urlSession(_ session: URLSession,
                    dataTask: URLSessionDataTask,
                    didReceive data: Data) {
        // Merge new bytes with any leftover partial UTF-8 sequence from the last chunk.
        utf8Tail.append(data)

        // Find the longest decodable UTF-8 prefix, leaving incomplete bytes in the tail.
        var validLen = utf8Tail.count
        while validLen > 0, String(data: utf8Tail.prefix(validLen), encoding: .utf8) == nil {
            validLen -= 1
        }
        guard validLen > 0,
              let decoded = String(data: utf8Tail.prefix(validLen), encoding: .utf8) else { return }

        utf8Tail = validLen < utf8Tail.count
            ? Data(utf8Tail.suffix(utf8Tail.count - validLen))
            : Data()

        // Split on newlines; keep the unterminated trailing fragment in lineBuf.
        lineBuf += decoded
        while let nlIdx = lineBuf.range(of: "\n") {
            let line = String(lineBuf[lineBuf.startIndex ..< nlIdx.lowerBound])
            lineBuf  = String(lineBuf[nlIdx.upperBound...])
            processLine(line)
        }
    }

    func urlSession(_ session: URLSession,
                    task: URLSessionTask,
                    didCompleteWithError error: Error?) {
        // Flush any partial last line that arrived without a trailing newline.
        if !lineBuf.isEmpty {
            processLine(lineBuf)
            lineBuf = ""
        }

        if let nsErr = error as NSError?, nsErr.code != NSURLErrorCancelled {
            let retriableCodes: Set<Int> = [
                NSURLErrorCannotConnectToHost,
                NSURLErrorNotConnectedToInternet,
                NSURLErrorTimedOut,
                NSURLErrorNetworkConnectionLost,
            ]
            // Retry connection-level errors when we have no content yet.
            if retriableCodes.contains(nsErr.code), accumulated.isEmpty, retries < maxRetries {
                retries += 1
                let delay = pow(2.0, Double(retries - 1)) * 0.5   // 0.5 / 1.0 / 2.0 s
                DispatchQueue.global().asyncAfter(deadline: .now() + delay) { [weak self] in
                    guard let self, self.isStreaming else { return }
                    self.sendRequest()
                }
                return
            }
            finish(error: accumulated.isEmpty ? StreamError.connectionFailed(nsErr) : nil)
        } else {
            finish(error: nil)
        }
    }

    func urlSession(_ session: URLSession, didBecomeInvalidWithError error: Error?) {
        // Session was intentionally invalidated after completion or cancellation.
    }

    // MARK: Line parsing

    private func processLine(_ raw: String) {
        let line = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !line.isEmpty else { return }

        // Strip SSE "data: " prefix when present.
        let jsonStr: String
        if line.hasPrefix("data: ") {
            let payload = String(line.dropFirst("data: ".count))
            if payload == "[DONE]" { return }
            jsonStr = payload
        } else {
            jsonStr = line
        }

        guard let jsonData = jsonStr.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any] else { return }

        // OpenAI chat-completion chunk: choices[0].delta.content
        if let choices = json["choices"] as? [[String: Any]],
           let delta   = choices.first?["delta"] as? [String: Any],
           let content = delta["content"] as? String, !content.isEmpty {
            emit(content); return
        }

        // Ollama /api/chat: {"message":{"content":"…"},"done":false}
        if let msg     = json["message"] as? [String: Any],
           let content = msg["content"] as? String, !content.isEmpty {
            emit(content); return
        }

        // Ollama /api/generate: {"response":"…","done":false}
        if let response = json["response"] as? String, !response.isEmpty {
            emit(response)
        }
    }

    private func emit(_ content: String) {
        accumulated += content
        DispatchQueue.main.async { [weak self] in self?.onToken?(content) }
    }

    private func finish(error: Error?) {
        isStreaming = false
        session.finishTasksAndInvalidate()   // break URLSession → delegate retain cycle
        let text = accumulated
        DispatchQueue.main.async { [weak self] in self?.onComplete?(text, error) }
    }
}

final class TerminalMode {
    private var original: termios?
    private(set) var isEnabled = false

    func enableRawMode() throws {
        guard isatty(STDIN_FILENO) == 1 else { return }
        guard !isEnabled else { return }

        var attributes = termios()
        guard tcgetattr(STDIN_FILENO, &attributes) == 0 else {
            throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno), userInfo: [NSLocalizedDescriptionKey: String(cString: strerror(errno))])
        }

        original = attributes
        cfmakeraw(&attributes)
        attributes.c_oflag |= tcflag_t(OPOST)

        guard tcsetattr(STDIN_FILENO, TCSAFLUSH, &attributes) == 0 else {
            throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno), userInfo: [NSLocalizedDescriptionKey: String(cString: strerror(errno))])
        }

        isEnabled = true
    }

    func restore() {
        guard isEnabled, var original else { return }
        tcsetattr(STDIN_FILENO, TCSAFLUSH, &original)
        isEnabled = false
    }

    deinit {
        restore()
    }
}

final class TerminalChatController {
    private struct QueuedChunk {
        let requestID: String?
        let text: String
        let finishesMessage: Bool
        let speechText: String?
    }

    static var shouldRunInTerminal: Bool {
        CommandLine.arguments.contains("--terminal") || isatty(STDIN_FILENO) == 1 || isatty(STDOUT_FILENO) == 1
    }

    private let bridge = RedpandaBridge()
    private let fallbackResponder = LocalFallbackResponder()
    private let speaker = SpeechVoice()
    private let terminalMode = TerminalMode()
    private var currentMode: ChatMode = ModePreferences.load()
    private let uiQueue = DispatchQueue(label: "brainchat.terminal.ui")
    private let stdoutHandle = FileHandle.standardOutput

    private var inputSource: DispatchSourceRead?
    private var pendingFallbacks: [String: DispatchWorkItem] = [:]
    private var pendingRequestOrder: [String] = []
    private var availability: RedpandaBridge.Availability = .unavailable("Connecting…")
    private var inputBuffer = ""
    private var pendingChunks: [QueuedChunk] = []
    private var isAnimatingChunk = false
    private var activeResponseRequestID: String?
    private var promptVisible = false
    private var shuttingDown = false
    private var escapeSequencePending = false
    // MARK: - UI Proxy (for CopilotIntegration compatibility)

    enum LogLevel { case info, warning, error }

    struct UIProxy {
        weak var c: TerminalChatController?
        func setStatus(_ text: String)  { c?.writeStatus(text) }
        func speak(_ text: String)      { DispatchQueue.main.async { self.c?.speaker.speak(text) } }
        func log(_ text: String, level: LogLevel = .info) { c?.writeLine(text) }
        func appendChat(role: String, text: String, requestID: String? = nil) {
            c?.writeTranscriptLine(prefix: role, text: text, color: role == "You" ? TerminalANSI.cyan : TerminalANSI.green)
        }
        func appendChatFragment(role: String, requestID: String, text: String) {
            c?.uiQueue.async { self.c?.writeRaw(ANSIText.strip(text)) }
        }
    }

    var ui: UIProxy { UIProxy(c: self) }



    // LLM streaming state
    private var streamingClient: LLMStreamingClient?
    private var currentStreamID: String?
    private var streamPrefixShown = false   // true once "Brain> " has been written

    private lazy var richTTYEnabled: Bool = {
        guard isatty(STDOUT_FILENO) == 1 else { return false }
        let environment = ProcessInfo.processInfo.environment
        if environment["TERM"] == "dumb" { return false }
        if environment["BRAINCHAT_ACCESSIBLE_TERMINAL"] == "1" { return false }
        return true
    }()

    func run() -> Never {
        uiQueue.async { [weak self] in
            self?.bootstrap()
        }
        dispatchMain()
    }

    private func bootstrap() {
        do {
            try terminalMode.enableRawMode()
        } catch {
            writeLine("Brain Chat could not enable raw mode: \(error.localizedDescription)")
        }

        if richTTYEnabled {
            writeRaw(TerminalANSI.hideCursor)
        }

        configureBridge()
        setupInputSource()
        renderWelcome()
        bridge.start()
        renderPrompt()
    }

    private func configureBridge() {
        bridge.onAvailabilityChanged = { [weak self] availability in
            self?.uiQueue.async {
                self?.availability = availability
                switch availability {
                case .connected:
                    self?.writeStatus("Connected to Redpanda at localhost:9092")
                case .unavailable(let reason):
                    self?.writeStatus("Fallback mode: \(reason)")
                }
            }
        }

        bridge.onResponse = { [weak self] response in
            self?.uiQueue.async {
                self?.handleRemoteResponse(response)
            }
        }
    }

    private func setupInputSource() {
        guard isatty(STDIN_FILENO) == 1 else {
            writeLine("Brain Chat terminal mode requires interactive stdin.")
            shutdown(exitCode: 1)
            return
        }

        let source = DispatchSource.makeReadSource(fileDescriptor: STDIN_FILENO, queue: uiQueue)
        source.setEventHandler { [weak self] in
            self?.consumeInput()
        }
        source.setCancelHandler {}
        inputSource = source
        source.resume()
    }

    private func consumeInput() {
        var buffer = [UInt8](repeating: 0, count: 256)
        let bytesRead = Darwin.read(STDIN_FILENO, &buffer, buffer.count)
        guard bytesRead > 0 else {
            shutdown(exitCode: 0)
            return
        }

        for byte in buffer.prefix(bytesRead) {
            handleInputByte(byte)
        }
    }

    private func handleInputByte(_ byte: UInt8) {
        if escapeSequencePending {
            if (64...126).contains(byte) {
                escapeSequencePending = false
            }
            return
        }

        switch byte {
        case 3, 4:
            shutdown(exitCode: 0)
        case 27:
            escapeSequencePending = true
        case 10, 13:
            let text = inputBuffer.trimmingCharacters(in: .whitespacesAndNewlines)
            inputBuffer = ""
            promptVisible = false
            writeRaw("\r\n")
            guard !text.isEmpty else {
                renderPrompt()
                return
            }
            processInput(text)
        case 8, 127:
            guard !inputBuffer.isEmpty else { return }
            inputBuffer.removeLast()
            renderPrompt()
        default:
            guard let scalar = UnicodeScalar(Int(byte)), !CharacterSet.controlCharacters.contains(scalar) else {
                return
            }
            inputBuffer.append(Character(scalar))
            if !isAnimatingChunk {
                renderPrompt()
            }
        }
    }

    private func renderWelcome() {
        let orchestrator = LLMOrchestrator.shared
        let rag = RAGService.shared
        writeLine(colorize("Brain Chat — terminal mode. Ctrl+C exits.", color: TerminalANSI.bold + TerminalANSI.magenta))
        writeLine("Mode: " + colorize(currentMode.displayName, color: currentMode.promptANSIColor + TerminalANSI.bold)
                  + "  " + currentMode.modeDescription)
        writeLine("LLM:  " + colorize(orchestrator.mode.displayName, color: TerminalANSI.cyan + TerminalANSI.bold)
                  + " → Primary: \(orchestrator.primaryLLM.shortName)"
                  + (orchestrator.secondaryLLMs.isEmpty ? "" : ", Secondary: \(orchestrator.secondaryLLMs.map(\.shortName).joined(separator: ", "))"))
        let ragStatus = RAGSettings.isEnabled
            ? (rag.isAvailable ? colorize("ON (Neo4j connected)", color: TerminalANSI.green) : colorize("ON (Neo4j unavailable)", color: TerminalANSI.yellow))
            : colorize("OFF", color: TerminalANSI.dim)
        writeLine("RAG:  " + ragStatus + " → Knowledge graph enrichment")
        writeLine("Switch: /chat  /code  /terminal  /yolo  /voice  /work   (/modes for list)")
        writeLine("LLM:    /llm status  /llm mode <mode>  /llm primary <provider>  (/llm help)")
        writeLine("RAG:    /rag  /rag on  /rag off  /rag health  (/rag help)")
        writeLine("Tip: set BRAINCHAT_ACCESSIBLE_TERMINAL=1 to disable ANSI colours.")
        DispatchQueue.main.async {
            let ragMsg = RAGSettings.isEnabled ? " RAG is \(rag.isAvailable ? "enabled with knowledge graph" : "enabled but Neo4j unavailable")." : ""
            self.speaker.speak("Brain Chat ready in \(self.currentMode.displayName) mode. Using \(orchestrator.primaryLLM.shortName) as primary L L M.\(ragMsg) Type a message and press Return.")
        }
    }

    private func processInput(_ text: String) {
        if text.hasPrefix("/") { handleModeCommand(text); return }
        if currentMode == .yolo { handleYOLOCommand(text); return }
        if currentMode == .terminal, text.hasPrefix("!") {
            let cmd = String(text.dropFirst()).trimmingCharacters(in: .whitespacesAndNewlines)
            if !cmd.isEmpty { executeShellCommand(cmd); return }
        }
        // Cancel any in-progress stream before starting a new request.
        streamingClient?.cancel()
        streamingClient = nil

        writeTranscriptLine(prefix: "You", text: text, color: currentMode.promptANSIColor)
        let requestID = UUID().uuidString
        currentStreamID = requestID
        streamPrefixShown = false
        
        // Store original text for RAG storage
        let originalUserText = text

        // RAG enrichment: enhance prompt with knowledge graph context
        let rag = RAGService.shared
        rag.onStatusUpdate = { [weak self] status in
            self?.uiQueue.async { self?.writeStatus(status) }
        }
        
        rag.enrichPromptWithRAG(text) { [weak self] enrichedText in
            self?.uiQueue.async {
                guard let self, self.currentStreamID == requestID else { return }
                self.processWithLLM(enrichedText, originalText: originalUserText, requestID: requestID)
            }
        }
    }
    
    /// Processes text with LLM after RAG enrichment
    private func processWithLLM(_ text: String, originalText: String, requestID: String) {
        let orchestrator = LLMOrchestrator.shared
        let llmMode = orchestrator.mode

        // Use orchestrator for multi-bot and consensus modes
        if llmMode == .multiBot || llmMode == .consensus {
            writeStatus("Using \(llmMode.displayName) mode…")
            orchestrator.onStatusUpdate = { [weak self] status in
                self?.uiQueue.async { self?.writeStatus(status) }
            }
            orchestrator.query(text, systemPrompt: currentMode.systemPrompt) { [weak self] response, error in
                self?.uiQueue.async {
                    guard let self, self.currentStreamID == requestID else { return }
                    if response.isEmpty {
                        self.writeStatus("LLM orchestrator failed. Trying fallback…")
                        self.useRedpandaPath(text: originalText, requestID: requestID)
                    } else {
                        // Show the response
                        if self.promptVisible {
                            self.writeRaw("\r" + (self.richTTYEnabled ? TerminalANSI.clearLine : ""))
                            self.promptVisible = false
                        }
                        self.writeRaw(self.colorize("Brain> ", color: TerminalANSI.green + TerminalANSI.bold))
                        self.writeRaw(ANSIText.strip(response))
                        self.writeRaw("\r\n")
                        // Store conversation in RAG
                        RAGService.shared.storeConversation(
                            userMessage: originalText,
                            aiResponse: response,
                            mode: self.currentMode.rawValue
                        )
                        self.writeStatus("Ready. \(self.currentMode.displayName) mode (\(llmMode.displayName)).")
                        if self.currentMode.speaksResponses {
                            DispatchQueue.main.async { self.speaker.speak(response) }
                        }
                        self.renderPrompt()
                    }
                }
            }
            return
        }

        // Single LLM mode (default) - use direct streaming
        writeStatus("Connecting to \(orchestrator.primaryLLM.shortName)…")

        let client = LLMStreamingClient()
        streamingClient = client

        // Build config based on orchestrator's primary LLM
        let primaryProvider = orchestrator.primaryLLM
        let config = LLMConfig(
            url: primaryProvider.baseURL,
            model: primaryProvider.defaultModel,
            systemPrompt: currentMode.systemPrompt,
            apiKey: orchestrator.apiKey(for: primaryProvider)
        )

        client.stream(
            config: config,
            userText: text,
            onToken: { [weak self] token in
                self?.uiQueue.async {
                    guard let self, self.currentStreamID == requestID else { return }
                    if !self.streamPrefixShown {
                        self.streamPrefixShown = true
                        // Clear the prompt line before printing the Brain prefix.
                        if self.promptVisible {
                            self.writeRaw("\r" + (self.richTTYEnabled ? TerminalANSI.clearLine : ""))
                            self.promptVisible = false
                        }
                        self.writeRaw(self.colorize("Brain> ", color: TerminalANSI.green + TerminalANSI.bold))
                    }
                    self.writeRaw(ANSIText.strip(token))
                }
            },
            onComplete: { [weak self] fullText, error in
                self?.uiQueue.async {
                    guard let self, self.currentStreamID == requestID else { return }
                    self.streamingClient = nil
                    if fullText.isEmpty {
                        // Stream produced nothing — fall back to Redpanda then local.
                        self.writeStatus("Primary LLM unavailable. Trying Redpanda…")
                        self.useRedpandaPath(text: originalText, requestID: requestID)
                    } else {
                        self.writeRaw("\r\n")
                        // Store conversation in RAG
                        RAGService.shared.storeConversation(
                            userMessage: originalText,
                            aiResponse: fullText,
                            mode: self.currentMode.rawValue
                        )
                        self.writeStatus("Ready. \(self.currentMode.displayName) mode.")
                        if self.currentMode.speaksResponses {
                            DispatchQueue.main.async { self.speaker.speak(fullText) }
                        }
                        self.renderPrompt()
                    }
                }
            }
        )
    }

    private func useRedpandaPath(text: String, requestID: String) {
        pendingRequestOrder.append(requestID)
        bridge.publish(text: text, requestID: requestID) { [weak self] success, reason in
            self?.uiQueue.async {
                guard let self else { return }
                if success {
                    self.writeStatus("Waiting for AI response on brain.voice.response…")
                    self.scheduleFallback(for: requestID, originalText: text)
                } else {
                    self.writeStatus("Redpanda publish failed. Using local fallback.")
                    self.respondLocally(to: text, requestID: requestID, reason: reason ?? "publish failed")
                }
            }
        }
    }

    private func scheduleFallback(for requestID: String, originalText: String) {
        let workItem = DispatchWorkItem { [weak self] in
            self?.respondLocally(to: originalText, requestID: requestID, reason: self?.availabilityReason ?? "no response received")
        }
        pendingFallbacks[requestID] = workItem
        uiQueue.asyncAfter(deadline: .now() + 7, execute: workItem)
    }

    private func handleRemoteResponse(_ response: BridgeResponse) {
        if let requestID = response.requestID {
            resolvePendingRequest(id: requestID)
        } else if let next = pendingRequestOrder.first {
            resolvePendingRequest(id: next)
        }

        writeStatus(response.isPartial && !response.isFinal ? "Streaming AI response…" : "Received AI response")

        let cleanText = richTTYEnabled ? response.text : ANSIText.strip(response.text)
        let spokenText = ANSIText.strip(response.text)
        let chunk = QueuedChunk(
            requestID: response.requestID,
            text: cleanText,
            finishesMessage: response.isFinal,
            speechText: response.isFinal ? spokenText : nil
        )
        pendingChunks.append(chunk)
        pumpChunkQueue()
    }

    private func respondLocally(to text: String, requestID: String, reason: String) {
        resolvePendingRequest(id: requestID)
        let response = fallbackResponder.response(for: text, reason: reason)
        writeStatus("Responding locally")
        pendingChunks.append(QueuedChunk(requestID: requestID, text: response, finishesMessage: true, speechText: response))
        pumpChunkQueue()
    }

    private func pumpChunkQueue() {
        guard !isAnimatingChunk, !pendingChunks.isEmpty else { return }
        isAnimatingChunk = true
        let chunk = pendingChunks.removeFirst()

        if activeResponseRequestID != chunk.requestID {
            if activeResponseRequestID != nil {
                writeRaw("\r\n")
            }
            activeResponseRequestID = chunk.requestID
            writeRaw(colorize("Brain> ", color: TerminalANSI.green + TerminalANSI.bold))
        }

        stream(chunk.text, at: chunk.text.startIndex, finishesMessage: chunk.finishesMessage) { [weak self] in
            guard let self else { return }
            if chunk.finishesMessage {
                self.writeRaw("\r\n")
                self.activeResponseRequestID = nil
                if let speechText = chunk.speechText {
                    DispatchQueue.main.async {
                        self.speaker.speak(speechText)
                    }
                }
            }
            self.isAnimatingChunk = false
            self.renderPrompt()
            self.pumpChunkQueue()
        }
    }

    private func stream(_ text: String, at index: String.Index, finishesMessage: Bool, completion: @escaping () -> Void) {
        guard index < text.endIndex else {
            completion()
            return
        }

        let nextIndex = text.index(after: index)
        let character = String(text[index])
        writeRaw(character)

        let delay: DispatchTimeInterval = character == "\n" ? .milliseconds(0) : .milliseconds(8)
        uiQueue.asyncAfter(deadline: .now() + delay) { [weak self] in
            self?.stream(text, at: nextIndex, finishesMessage: finishesMessage, completion: completion)
        }
    }

    private func resolvePendingRequest(id: String) {
        pendingFallbacks[id]?.cancel()
        pendingFallbacks[id] = nil
        pendingRequestOrder.removeAll { $0 == id }
    }

    private var availabilityReason: String {
        switch availability {
        case .connected:
            return "broker is connected but no response arrived"
        case .unavailable(let reason):
            return reason
        }
    }

    private func renderPrompt() {
        guard !shuttingDown else { return }
        guard !isAnimatingChunk else { return }

        let label = currentMode == .chat ? "You> " : "[\(currentMode.displayName)]> "
        let prompt = colorize(label, color: currentMode.promptANSIColor + TerminalANSI.bold) + inputBuffer
        if richTTYEnabled {
            writeRaw("\r" + TerminalANSI.clearLine + prompt)
        } else {
            writeRaw(promptVisible ? "\r\(label)\(inputBuffer)" : prompt)
        }
        promptVisible = true
    }

    private func writeStatus(_ text: String) {
        writeLine(colorize("Status: \(ANSIText.strip(text))", color: TerminalANSI.dim + TerminalANSI.yellow))
        renderPrompt()
    }

    private func writeTranscriptLine(prefix: String, text: String, color: String) {
        writeLine(colorize("\(prefix)> ", color: color + TerminalANSI.bold) + ANSIText.strip(text))
    }

    private func writeLine(_ text: String) {
        if promptVisible {
            writeRaw("\r" + (richTTYEnabled ? TerminalANSI.clearLine : ""))
            promptVisible = false
        }
        writeRaw(text)
        if !text.hasSuffix("\n") {
            writeRaw("\r\n")
        }
    }

    private func writeRaw(_ text: String) {
        stdoutHandle.write(Data(text.utf8))
    }

    private func colorize(_ text: String, color: String) -> String {
        guard richTTYEnabled else { return ANSIText.strip(text) }
        return color + text + TerminalANSI.reset
    }


    // MARK: - Mode Commands

    private let llmSelector = LLMSelectorUI()
    private let ragSelector = RAGSelectorUI()

    private func handleModeCommand(_ input: String) {
        let cmd = input.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)

        // Handle /llm commands
        if cmd.hasPrefix("/llm") {
            _ = llmSelector.handleCommand(input)
            renderPrompt()
            return
        }
        
        // Handle /rag commands
        if cmd.hasPrefix("/rag") {
            _ = ragSelector.handleCommand(input)
            renderPrompt()
            return
        }

        if cmd == "/modes" || cmd == "/help" || cmd == "/?" {
            writeLine(colorize("Available modes:", color: TerminalANSI.bold))
            for mode in ChatMode.allCases {
                let m = mode == currentMode ? "> " : "  "
                writeLine(colorize(m + mode.switchCommand, color: mode.promptANSIColor + TerminalANSI.bold)
                          + "  " + mode.modeDescription)
            }
            writeLine("")
            writeLine(colorize("LLM Orchestration:", color: TerminalANSI.bold))
            writeLine("  /llm status    - Show LLM configuration")
            writeLine("  /llm help      - Show LLM commands")
            writeLine("")
            writeLine(colorize("RAG (Knowledge Graph):", color: TerminalANSI.bold))
            writeLine("  /rag           - Show RAG status")
            writeLine("  /rag help      - Show RAG commands")
            renderPrompt(); return
        }
        if let mode = ChatMode.allCases.first(where: { cmd == $0.switchCommand }) {
            currentMode = mode
            ModePreferences.save(mode)
            writeLine(colorize("Switched to \(mode.displayName) — \(mode.modeDescription)",
                               color: mode.promptANSIColor + TerminalANSI.bold))
            DispatchQueue.main.async { self.speaker.speak("Switched to \(mode.displayName) mode.") }
            renderPrompt()
        } else {
            writeLine(colorize("Unknown command: \(input). Type /modes for help.", color: TerminalANSI.yellow))
            renderPrompt()
        }
    }

    private func handleYOLOCommand(_ command: String) {
        writeTranscriptLine(prefix: "YOLO", text: command, color: TerminalANSI.red)
        writeStatus("Publishing to brain.yolo.commands…")
        let reqID = UUID().uuidString
        pendingRequestOrder.append(reqID)
        bridge.publish(text: "yolo: \(command)", requestID: reqID) { [weak self] success, reason in
            self?.uiQueue.async {
                guard let self else { return }                
                if success {
                    self.writeStatus("YOLO command published.")
                    DispatchQueue.main.async { self.speaker.speak("YOLO command published.") }
                } else {
                    self.writeStatus("YOLO failed: \(reason ?? "unknown")")
                    self.pendingRequestOrder.removeAll { $0 == reqID }
                }
                self.renderPrompt()
            }
        }
    }

    private func executeShellCommand(_ command: String) {
        writeTranscriptLine(prefix: "Shell", text: "$ \(command)", color: TerminalANSI.magenta)
        writeStatus("Executing…")
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/zsh")
        p.arguments = ["-c", command]
        let o = Pipe(); let e = Pipe()
        p.standardOutput = o; p.standardError = e
        p.terminationHandler = { [weak self] proc in
            let out = String(data: o.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            let err = String(data: e.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            let combined = (out + err).trimmingCharacters(in: .whitespacesAndNewlines)
            DispatchQueue.main.async {
                self?.uiQueue.async {
                    guard let self else { return }
                    if !combined.isEmpty { self.writeLine(combined) }
                    self.writeStatus(proc.terminationStatus == 0 ? "Done (exit 0)" : "Exit \(proc.terminationStatus)")
                    self.renderPrompt()
                }
            }
        }
        do { try p.run() } catch {
            writeStatus("Shell error: \(error.localizedDescription)"); renderPrompt()
        }
    }

    private func shutdown(exitCode: Int32) {
        guard !shuttingDown else { return }
        shuttingDown = true
        pendingFallbacks.values.forEach { $0.cancel() }
        pendingFallbacks.removeAll()
        bridge.stop()
        inputSource?.cancel()
        inputSource = nil
        if richTTYEnabled {
            writeRaw("\r\n" + TerminalANSI.showCursor)
        } else {
            writeRaw("\r\n")
        }
        terminalMode.restore()
        Darwin.exit(exitCode)
    }
}

// MARK: - AppleScript Support

/// Shared state accessible to AppleScript command handlers
final class ScriptingState {
    static let shared = ScriptingState()
    
    var appDelegate: AppDelegate?
    var lastResponse: String = ""
    var lastRequestID: String?
    var currentStatus: String = "Ready"
    var customLLMModel: String?
    
    private init() {}
}

// MARK: - AppleScript Command Classes

/// Base class for Brain Chat scripting commands
class BrainChatScriptCommand: NSScriptCommand {
    var appDelegate: AppDelegate? { ScriptingState.shared.appDelegate }
}

/// set mode "chat" / "code" / "terminal" / "yolo" / "voice" / "work"
@objc(BrainChatSetModeCommand)
final class BrainChatSetModeCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let modeStr = directParameter as? String else {
            scriptErrorNumber = errAEParamMissed
            return "Error: mode parameter required"
        }
        guard let mode = ChatMode(rawValue: modeStr.lowercased()) else {
            scriptErrorNumber = errAECoercionFail
            return "Error: invalid mode '\(modeStr)'. Use: chat, code, terminal, yolo, voice, or work"
        }
        DispatchQueue.main.async {
            self.appDelegate?.setModeFromScript(mode)
        }
        return "Switched to \(mode.displayName) mode"
    }
}

/// get mode
@objc(BrainChatGetModeCommand)
final class BrainChatGetModeCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        return appDelegate?.currentModeForScript.rawValue ?? "chat"
    }
}

/// list modes
@objc(BrainChatListModesCommand)
final class BrainChatListModesCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        return ChatMode.allCases.map { "\($0.rawValue): \($0.modeDescription)" }.joined(separator: "\n")
    }
}

/// start listening
@objc(BrainChatStartListeningCommand)
final class BrainChatStartListeningCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        DispatchQueue.main.async {
            self.appDelegate?.startListeningFromScript()
        }
        return true
    }
}

/// stop listening
@objc(BrainChatStopListeningCommand)
final class BrainChatStopListeningCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        var result = ""
        let sem = DispatchSemaphore(value: 0)
        DispatchQueue.main.async {
            result = self.appDelegate?.stopListeningFromScript() ?? ""
            sem.signal()
        }
        _ = sem.wait(timeout: .now() + 5)
        return result
    }
}

/// speak "text"
@objc(BrainChatSpeakCommand)
final class BrainChatSpeakCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let text = directParameter as? String else {
            scriptErrorNumber = errAEParamMissed
            return nil
        }
        DispatchQueue.main.async {
            self.appDelegate?.speakFromScript(text)
        }
        return nil
    }
}

/// stop speaking
@objc(BrainChatStopSpeakingCommand)
final class BrainChatStopSpeakingCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        DispatchQueue.main.async {
            self.appDelegate?.stopSpeakingFromScript()
        }
        return nil
    }
}

/// send message "text" — synchronous, waits for response
@objc(BrainChatSendMessageCommand)
final class BrainChatSendMessageCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let message = directParameter as? String else {
            scriptErrorNumber = errAEParamMissed
            return "Error: message parameter required"
        }
        
        let sem = DispatchSemaphore(value: 0)
        var response = ""
        
        DispatchQueue.main.async {
            self.appDelegate?.sendMessageFromScript(message) { result in
                response = result
                sem.signal()
            }
        }
        
        // Wait up to 60 seconds for response
        let waitResult = sem.wait(timeout: .now() + 60)
        if waitResult == .timedOut {
            return "Error: response timed out after 60 seconds"
        }
        return response
    }
}

/// send async "text" — returns immediately with request ID
@objc(BrainChatSendAsyncCommand)
final class BrainChatSendAsyncCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let message = directParameter as? String else {
            scriptErrorNumber = errAEParamMissed
            return "Error: message parameter required"
        }
        
        let requestID = UUID().uuidString
        DispatchQueue.main.async {
            self.appDelegate?.sendMessageAsyncFromScript(message, requestID: requestID)
        }
        return requestID
    }
}

/// get response
@objc(BrainChatGetResponseCommand)
final class BrainChatGetResponseCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        return ScriptingState.shared.lastResponse
    }
}

/// get transcript [lines N]
@objc(BrainChatGetTranscriptCommand)
final class BrainChatGetTranscriptCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        let lineCount = evaluatedArguments?["lines"] as? Int
        var result = ""
        let sem = DispatchSemaphore(value: 0)
        DispatchQueue.main.async {
            result = self.appDelegate?.getTranscriptFromScript(lines: lineCount) ?? ""
            sem.signal()
        }
        _ = sem.wait(timeout: .now() + 2)
        return result
    }
}

/// clear transcript
@objc(BrainChatClearTranscriptCommand)
final class BrainChatClearTranscriptCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        DispatchQueue.main.async {
            self.appDelegate?.clearTranscriptFromScript()
        }
        return nil
    }
}

/// execute yolo "command"
@objc(BrainChatExecuteYoloCommand)
final class BrainChatExecuteYoloCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let command = directParameter as? String else {
            scriptErrorNumber = errAEParamMissed
            return "Error: command parameter required"
        }
        
        let sem = DispatchSemaphore(value: 0)
        var result = ""
        
        DispatchQueue.main.async {
            self.appDelegate?.executeYoloFromScript(command) { response in
                result = response
                sem.signal()
            }
        }
        
        _ = sem.wait(timeout: .now() + 30)
        return result.isEmpty ? "YOLO command published: \(command)" : result
    }
}

/// connect bridge
@objc(BrainChatConnectBridgeCommand)
final class BrainChatConnectBridgeCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        DispatchQueue.main.async {
            self.appDelegate?.connectBridgeFromScript()
        }
        return true
    }
}

/// disconnect bridge
@objc(BrainChatDisconnectBridgeCommand)
final class BrainChatDisconnectBridgeCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        DispatchQueue.main.async {
            self.appDelegate?.disconnectBridgeFromScript()
        }
        return nil
    }
}

/// bridge status
@objc(BrainChatBridgeStatusCommand)
final class BrainChatBridgeStatusCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        var result = ""
        let sem = DispatchSemaphore(value: 0)
        DispatchQueue.main.async {
            result = self.appDelegate?.bridgeStatusFromScript() ?? "Unknown"
            sem.signal()
        }
        _ = sem.wait(timeout: .now() + 2)
        return result
    }
}

/// get status
@objc(BrainChatGetStatusCommand)
final class BrainChatGetStatusCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        return ScriptingState.shared.currentStatus
    }
}

/// health check
@objc(BrainChatHealthCheckCommand)
final class BrainChatHealthCheckCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        var result = ""
        let sem = DispatchSemaphore(value: 0)
        DispatchQueue.main.async {
            result = self.appDelegate?.healthCheckFromScript() ?? "Health check unavailable"
            sem.signal()
        }
        _ = sem.wait(timeout: .now() + 5)
        return result
    }
}

/// set llm "model"
@objc(BrainChatSetLLMCommand)
final class BrainChatSetLLMCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let model = directParameter as? String else {
            scriptErrorNumber = errAEParamMissed
            return "Error: model parameter required"
        }
        ScriptingState.shared.customLLMModel = model
        return "LLM set to \(model)"
    }
}

/// get llm
@objc(BrainChatGetLLMCommand)
final class BrainChatGetLLMCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        if let custom = ScriptingState.shared.customLLMModel {
            return custom
        }
        return appDelegate?.currentModeForScript.llmModel ?? "llama3.2:3b"
    }
}

/// show window
@objc(BrainChatShowWindowCommand)
final class BrainChatShowWindowCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        DispatchQueue.main.async {
            self.appDelegate?.showWindowFromScript()
        }
        return nil
    }
}

/// hide window
@objc(BrainChatHideWindowCommand)
final class BrainChatHideWindowCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        DispatchQueue.main.async {
            self.appDelegate?.hideWindowFromScript()
        }
        return nil
    }
}

/// announce "text" [priority "normal"]
@objc(BrainChatAnnounceCommand)
final class BrainChatAnnounceCommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        guard let text = directParameter as? String else {
            scriptErrorNumber = errAEParamMissed
            return nil
        }
        let priority = evaluatedArguments?["priority"] as? String ?? "normal"
        DispatchQueue.main.async {
            self.appDelegate?.announceFromScript(text, priority: priority)
        }
        return nil
    }
}

/// describe ui
@objc(BrainChatDescribeUICommand)
final class BrainChatDescribeUICommand: BrainChatScriptCommand {
    override func performDefaultImplementation() -> Any? {
        var result = ""
        let sem = DispatchSemaphore(value: 0)
        DispatchQueue.main.async {
            result = self.appDelegate?.describeUIFromScript() ?? "UI description unavailable"
            sem.signal()
        }
        _ = sem.wait(timeout: .now() + 2)
        return result
    }
}

// MARK: - Keyboard-Aware Content View for Accessibility
final class KeyboardAwareContentView: NSView {
    weak var appDelegate: AppDelegate?
    
    override func keyDown(with event: NSEvent) {
        let modifiers = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
        let isCmd = modifiers.contains(.command)
        let isShift = modifiers.contains(.shift)
        
        // Cmd+M: Toggle microphone/listening
        if isCmd && event.charactersIgnoringModifiers == "m" {
            appDelegate?.toggleListening()
            return
        }
        
        // Cmd+.: Stop listening
        if isCmd && event.charactersIgnoringModifiers == "." {
            appDelegate?.stopListeningIfActive()
            return
        }
        
        // Cmd+Return: Send message (alternative to just pressing Return)
        if isCmd && event.keyCode == 36 { // 36 is Return key
            appDelegate?.sendCurrentInput()
            return
        }
        
        super.keyDown(with: event)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private let listenButton = NSButton(title: "Press Enter to Talk", target: nil, action: nil)
    private let statusLabel = NSTextField(labelWithString: "Starting Brain Chat…")
    private let transcriptView = NSTextView()
    private let scrollView = NSScrollView()
    
    // Settings dropdowns
    private let llmProviderDropdown = NSPopUpButton(frame: .zero, pullsDown: false)
    private let voiceEngineDropdown = NSPopUpButton(frame: .zero, pullsDown: false)
    private let voiceOptionDropdown = NSPopUpButton(frame: .zero, pullsDown: false)
    private let securityRoleDropdown = NSPopUpButton(frame: .zero, pullsDown: false)
    private let dictationEngineDropdown = NSPopUpButton(frame: .zero, pullsDown: false)
    private let chatModeDropdown = NSPopUpButton(frame: .zero, pullsDown: false)
    private let llmModeDropdown = NSPopUpButton(frame: .zero, pullsDown: false)

    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en_AU"))
    private let audioEngine = AVAudioEngine()
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var didProcessFinalResult = false
    private var isListening = false
    private var lastHeardText = ""
    private var speechPermissionGranted = false
    private var microphonePermissionGranted = false

    private let speaker = SpeechVoice()
    private let fallbackResponder = LocalFallbackResponder()
    private let bridge = RedpandaBridge()
    private var currentMode: ChatMode = ModePreferences.load()
    private let modeBadgeLabel = NSTextField(labelWithString: "Chat Mode")
    private var bridgeAvailability: RedpandaBridge.Availability = .unavailable("Connecting…")
    private var pendingFallbacks: [String: DispatchWorkItem] = [:]
    private var pendingRequestOrder: [String] = []

    // LLM streaming state
    private var streamingClient: LLMStreamingClient?
    private var currentStreamID: String?           // ID of the in-flight stream request
    private var streamHeaderShown = false          // true once "Brain: " has been appended
    private var pendingTokens = ""                 // tokens buffered for the next 30-fps flush
    private var tokenFlushTimer: Timer?            // coalescing display timer (~30 fps)

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Register for AppleScript support
        ScriptingState.shared.appDelegate = self
        
        // Register AppleEvent handlers for scripting
        registerAppleEventHandlers()
        
        setupWindow()
        configureBridge()
        requestPermissions()
        bridge.start()

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
            self.speakAndLog("Brain Chat is ready. Press Enter to talk.", speaker: "Brain")
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        streamingClient?.cancel()
        streamingClient = nil
        tokenFlushTimer?.invalidate()
        bridge.stop()
        stopListeningSession(cancelRecognition: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    private func setupWindow() {
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 900, height: 700),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Brain Chat"
        window.minSize = NSSize(width: 800, height: 600)
        window.center()

        let contentView = KeyboardAwareContentView(frame: window.contentView?.bounds ?? .zero)
        contentView.autoresizingMask = [.width, .height]
        contentView.appDelegate = self
        window.contentView = contentView

        let titleLabel = NSTextField(labelWithString: "Brain Chat")
        titleLabel.font = NSFont.systemFont(ofSize: 32, weight: .bold)
        titleLabel.frame = NSRect(x: 40, y: 640, width: 300, height: 40)
        titleLabel.setAccessibilityLabel("Brain Chat")
        contentView.addSubview(titleLabel)

        modeBadgeLabel.font = NSFont.systemFont(ofSize: 13, weight: .medium)
        modeBadgeLabel.frame = NSRect(x: 650, y: 646, width: 200, height: 20)
        modeBadgeLabel.alignment = .right
        modeBadgeLabel.stringValue = "\(currentMode.displayName) Mode"
        modeBadgeLabel.setAccessibilityLabel("Current mode: \(currentMode.displayName)")
        contentView.addSubview(modeBadgeLabel)

        // MARK: - Settings Row 1: LLM Provider, LLM Mode, Chat Mode
        let settingsY1: CGFloat = 590
        let dropdownWidth: CGFloat = 140
        let labelHeight: CGFloat = 18
        let dropdownHeight: CGFloat = 26
        
        // LLM Provider dropdown
        let llmProviderLabel = NSTextField(labelWithString: "LLM Provider:")
        llmProviderLabel.font = NSFont.systemFont(ofSize: 12, weight: .medium)
        llmProviderLabel.frame = NSRect(x: 40, y: settingsY1 + dropdownHeight + 2, width: dropdownWidth, height: labelHeight)
        contentView.addSubview(llmProviderLabel)
        
        llmProviderDropdown.frame = NSRect(x: 40, y: settingsY1, width: dropdownWidth, height: dropdownHeight)
        llmProviderDropdown.removeAllItems()
        for provider in LLMProvider.allCases {
            llmProviderDropdown.addItem(withTitle: provider.displayName)
        }
        llmProviderDropdown.selectItem(withTitle: LLMProvider.ollama.displayName) // Default to Ollama (local)
        llmProviderDropdown.target = self
        llmProviderDropdown.action = #selector(llmProviderChanged)
        llmProviderDropdown.setAccessibilityLabel("LLM Provider")
        llmProviderDropdown.setAccessibilityHelp("Select which AI model to use: Ollama, OpenRouter, or Claude Desktop")
        llmProviderDropdown.setAccessibilityRole(NSAccessibility.Role.popUpButton)
        llmProviderDropdown.setAccessibilityTraits(.button)
        contentView.addSubview(llmProviderDropdown)
        
        // LLM Mode dropdown (Single, Multi-Bot, Consensus)
        let llmModeLabel = NSTextField(labelWithString: "LLM Mode:")
        llmModeLabel.font = NSFont.systemFont(ofSize: 12, weight: .medium)
        llmModeLabel.frame = NSRect(x: 200, y: settingsY1 + dropdownHeight + 2, width: dropdownWidth, height: labelHeight)
        contentView.addSubview(llmModeLabel)
        
        llmModeDropdown.frame = NSRect(x: 200, y: settingsY1, width: dropdownWidth, height: dropdownHeight)
        llmModeDropdown.removeAllItems()
        for mode in LLMMode.allCases {
            llmModeDropdown.addItem(withTitle: mode.displayName)
        }
        llmModeDropdown.selectItem(at: 0) // Single LLM
        llmModeDropdown.target = self
        llmModeDropdown.action = #selector(llmModeChanged)
        llmModeDropdown.setAccessibilityLabel("LLM Mode")
        llmModeDropdown.setAccessibilityHelp("Choose how AI responds: Single LLM, Multi-Bot, or Consensus mode")
        llmModeDropdown.setAccessibilityRole(NSAccessibility.Role.popUpButton)
        llmModeDropdown.setAccessibilityTraits(.button)
        contentView.addSubview(llmModeDropdown)
        
        // Chat Mode dropdown
        let chatModeLabel = NSTextField(labelWithString: "Chat Mode:")
        chatModeLabel.font = NSFont.systemFont(ofSize: 12, weight: .medium)
        chatModeLabel.frame = NSRect(x: 360, y: settingsY1 + dropdownHeight + 2, width: dropdownWidth, height: labelHeight)
        contentView.addSubview(chatModeLabel)
        
        chatModeDropdown.frame = NSRect(x: 360, y: settingsY1, width: dropdownWidth, height: dropdownHeight)
        chatModeDropdown.removeAllItems()
        for mode in ChatMode.allCases {
            chatModeDropdown.addItem(withTitle: mode.displayName)
        }
        chatModeDropdown.selectItem(withTitle: currentMode.displayName)
        chatModeDropdown.target = self
        chatModeDropdown.action = #selector(chatModeChanged)
        chatModeDropdown.setAccessibilityLabel("Chat Mode")
        chatModeDropdown.setAccessibilityHelp("Changes how Brain Chat responds: Chat, Iris Lumina, or YOLO mode")
        chatModeDropdown.setAccessibilityRole(NSAccessibility.Role.popUpButton)
        chatModeDropdown.setAccessibilityTraits(.button)
        contentView.addSubview(chatModeDropdown)
        
        // Security Role dropdown
        let securityLabel = NSTextField(labelWithString: "Security Role:")
        securityLabel.font = NSFont.systemFont(ofSize: 12, weight: .medium)
        securityLabel.frame = NSRect(x: 520, y: settingsY1 + dropdownHeight + 2, width: dropdownWidth, height: labelHeight)
        contentView.addSubview(securityLabel)
        
        securityRoleDropdown.frame = NSRect(x: 520, y: settingsY1, width: dropdownWidth, height: dropdownHeight)
        securityRoleDropdown.removeAllItems()
        for role in SecurityRole.allCases {
            securityRoleDropdown.addItem(withTitle: role.displayName)
        }
        securityRoleDropdown.selectItem(withTitle: SecuritySettings.currentRole.displayName)
        securityRoleDropdown.target = self
        securityRoleDropdown.action = #selector(securityRoleChanged)
        securityRoleDropdown.setAccessibilityLabel("Security Role")
        securityRoleDropdown.setAccessibilityHelp("Controls what actions are allowed: Guest, User, or Admin")
        securityRoleDropdown.setAccessibilityRole(NSAccessibility.Role.popUpButton)
        securityRoleDropdown.setAccessibilityTraits(.button)
        contentView.addSubview(securityRoleDropdown)

        // MARK: - Settings Row 2: Voice Engine, Voice, Dictation Engine
        let settingsY2: CGFloat = 530
        
        // Voice Engine dropdown
        let voiceEngineLabel = NSTextField(labelWithString: "Voice Engine:")
        voiceEngineLabel.font = NSFont.systemFont(ofSize: 12, weight: .medium)
        voiceEngineLabel.frame = NSRect(x: 40, y: settingsY2 + dropdownHeight + 2, width: dropdownWidth, height: labelHeight)
        contentView.addSubview(voiceEngineLabel)
        
        voiceEngineDropdown.frame = NSRect(x: 40, y: settingsY2, width: dropdownWidth, height: dropdownHeight)
        voiceEngineDropdown.removeAllItems()
        for engine in VoiceEngine.allCases {
            voiceEngineDropdown.addItem(withTitle: engine.displayName)
        }
        voiceEngineDropdown.selectItem(withTitle: VoiceSettings.currentEngine.displayName)
        voiceEngineDropdown.target = self
        voiceEngineDropdown.action = #selector(voiceEngineChanged)
        voiceEngineDropdown.setAccessibilityLabel("Voice Engine")
        voiceEngineDropdown.setAccessibilityHelp("Select how responses are spoken: System speech, ElevenLabs, or other engines")
        voiceEngineDropdown.setAccessibilityRole(NSAccessibility.Role.popUpButton)
        voiceEngineDropdown.setAccessibilityTraits(.button)
        contentView.addSubview(voiceEngineDropdown)
        
        // Voice Option dropdown
        let voiceOptionLabel = NSTextField(labelWithString: "Voice:")
        voiceOptionLabel.font = NSFont.systemFont(ofSize: 12, weight: .medium)
        voiceOptionLabel.frame = NSRect(x: 200, y: settingsY2 + dropdownHeight + 2, width: dropdownWidth, height: labelHeight)
        contentView.addSubview(voiceOptionLabel)
        
        voiceOptionDropdown.frame = NSRect(x: 200, y: settingsY2, width: dropdownWidth, height: dropdownHeight)
        voiceOptionDropdown.removeAllItems()
        for voice in VoiceOption.allCases {
            voiceOptionDropdown.addItem(withTitle: voice.displayName)
        }
        voiceOptionDropdown.selectItem(withTitle: VoiceSettings.currentVoice.displayName)
        voiceOptionDropdown.target = self
        voiceOptionDropdown.action = #selector(voiceOptionChanged)
        voiceOptionDropdown.setAccessibilityLabel("Voice")
        voiceOptionDropdown.setAccessibilityHelp("Select which voice speaks responses. Karen is the default for Joseph. Options include Moira, Samantha, and others.")
        voiceOptionDropdown.setAccessibilityRole(NSAccessibility.Role.popUpButton)
        voiceOptionDropdown.setAccessibilityTraits(.button)
        contentView.addSubview(voiceOptionDropdown)
        
        // Dictation Engine dropdown
        let dictationLabel = NSTextField(labelWithString: "Dictation:")
        dictationLabel.font = NSFont.systemFont(ofSize: 12, weight: .medium)
        dictationLabel.frame = NSRect(x: 360, y: settingsY2 + dropdownHeight + 2, width: dropdownWidth, height: labelHeight)
        contentView.addSubview(dictationLabel)
        
        dictationEngineDropdown.frame = NSRect(x: 360, y: settingsY2, width: dropdownWidth, height: dropdownHeight)
        dictationEngineDropdown.removeAllItems()
        for engine in DictationEngine.allCases {
            dictationEngineDropdown.addItem(withTitle: engine.displayName)
        }
        dictationEngineDropdown.selectItem(withTitle: DictationSettings.currentEngine.displayName)
        dictationEngineDropdown.target = self
        dictationEngineDropdown.action = #selector(dictationEngineChanged)
        dictationEngineDropdown.setAccessibilityLabel("Dictation Engine")
        dictationEngineDropdown.setAccessibilityHelp("Choose how your voice is transcribed: System Speech Recognition or third-party engines")
        dictationEngineDropdown.setAccessibilityRole(NSAccessibility.Role.popUpButton)
        dictationEngineDropdown.setAccessibilityTraits(.button)
        contentView.addSubview(dictationEngineDropdown)

        // MARK: - Main UI Elements (shifted down)
        let instructionsLabel = NSTextField(wrappingLabelWithString: "Accessible voice chat for Joseph. Press Enter on the big button, speak your command, and Brain Chat will respond with voice.")
        instructionsLabel.font = NSFont.systemFont(ofSize: 16)
        instructionsLabel.frame = NSRect(x: 40, y: 480, width: 820, height: 40)
        instructionsLabel.setAccessibilityLabel("Instructions")
        contentView.addSubview(instructionsLabel)

        listenButton.frame = NSRect(x: 40, y: 400, width: 820, height: 64)
        listenButton.bezelStyle = .regularSquare
        listenButton.font = NSFont.systemFont(ofSize: 28, weight: .bold)
        listenButton.target = self
        listenButton.action = #selector(toggleListening)
        listenButton.keyEquivalent = "\r"
        listenButton.keyEquivalentModifierMask = []
        listenButton.setAccessibilityLabel("Start listening")
        listenButton.setAccessibilityHelp("Double tap to toggle voice input. Press Enter or Cmd+M to start listening.")
        listenButton.setAccessibilityRole(NSAccessibility.Role.button)
        listenButton.setAccessibilityTraits(.button)
        contentView.addSubview(listenButton)

        statusLabel.frame = NSRect(x: 40, y: 362, width: 820, height: 24)
        statusLabel.font = NSFont.systemFont(ofSize: 16, weight: .medium)
        statusLabel.setAccessibilityLabel("Status")
        contentView.addSubview(statusLabel)

        let transcriptLabel = NSTextField(labelWithString: "Conversation Transcript")
        transcriptLabel.font = NSFont.systemFont(ofSize: 18, weight: .semibold)
        transcriptLabel.frame = NSRect(x: 40, y: 330, width: 300, height: 24)
        contentView.addSubview(transcriptLabel)

        scrollView.frame = NSRect(x: 40, y: 40, width: 820, height: 280)
        scrollView.hasVerticalScroller = true
        scrollView.borderType = .bezelBorder
        scrollView.autoresizingMask = [.width, .height]

        transcriptView.frame = scrollView.bounds
        transcriptView.isEditable = false
        transcriptView.isSelectable = true
        transcriptView.font = NSFont.monospacedSystemFont(ofSize: 14, weight: .regular)
        transcriptView.textContainerInset = NSSize(width: 12, height: 12)
        transcriptView.backgroundColor = NSColor.textBackgroundColor
        transcriptView.string = "Brain: Launching Brain Chat…\n"
        transcriptView.setAccessibilityLabel("Conversation transcript. All messages are recorded here for copying and review.")
        scrollView.documentView = transcriptView
        contentView.addSubview(scrollView)

        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(listenButton)
        NSApp.activate(ignoringOtherApps: true)
    }
    
    // MARK: - Dropdown Action Handlers
    
    @objc private func llmProviderChanged() {
        guard let selected = llmProviderDropdown.titleOfSelectedItem,
              let provider = LLMProvider.allCases.first(where: { $0.displayName == selected }) else { return }
        updateStatus("LLM Provider changed to \(provider.displayName)")
        speakAndLog("Switched to \(provider.shortName)", speaker: "Brain")
    }
    
    @objc private func llmModeChanged() {
        guard let selected = llmModeDropdown.titleOfSelectedItem,
              let mode = LLMMode.allCases.first(where: { $0.displayName == selected }) else { return }
        updateStatus("LLM Mode changed to \(mode.displayName)")
        speakAndLog("Now using \(mode.displayName) mode", speaker: "Brain")
    }
    
    @objc private func chatModeChanged() {
        guard let selected = chatModeDropdown.titleOfSelectedItem,
              let mode = ChatMode.allCases.first(where: { $0.displayName == selected }) else { return }
        currentMode = mode
        ModePreferences.save(mode)
        modeBadgeLabel.stringValue = "\(mode.displayName) Mode"
        updateStatus("Chat mode changed to \(mode.displayName)")
        speakAndLog("Switched to \(mode.displayName) mode. \(mode.modeDescription)", speaker: "Brain")
    }
    
    @objc private func securityRoleChanged() {
        guard let selected = securityRoleDropdown.titleOfSelectedItem,
              let role = SecurityRole.allCases.first(where: { $0.displayName == selected }) else { return }
        SecuritySettings.currentRole = role
        updateStatus("Security role changed to \(role.displayName)")
        speakAndLog("Security role is now \(role.displayName). \(role.accessibilityDescription)", speaker: "Brain")
    }
    
    @objc private func voiceEngineChanged() {
        guard let selected = voiceEngineDropdown.titleOfSelectedItem,
              let engine = VoiceEngine.allCases.first(where: { $0.displayName == selected }) else { return }
        VoiceSettings.currentEngine = engine
        updateStatus("Voice engine changed to \(engine.displayName)")
        speakAndLog("Voice engine changed to \(engine.displayName)", speaker: "Brain")
    }
    
    @objc private func voiceOptionChanged() {
        guard let selected = voiceOptionDropdown.titleOfSelectedItem,
              let voice = VoiceOption.allCases.first(where: { $0.displayName == selected }) else { return }
        VoiceSettings.currentVoice = voice
        updateStatus("Voice changed to \(voice.displayName)")
        // Speak with the new voice to demonstrate
        speakAndLog("Hello, I'm \(voice.displayName)", speaker: "Brain")
    }
    
    @objc private func dictationEngineChanged() {
        guard let selected = dictationEngineDropdown.titleOfSelectedItem,
              let engine = DictationEngine.allCases.first(where: { $0.displayName == selected }) else { return }
        DictationSettings.currentEngine = engine
        updateStatus("Dictation engine changed to \(engine.displayName)")
        speakAndLog("Dictation engine changed to \(engine.displayName)", speaker: "Brain")
    }

    private func configureBridge() {
        bridge.onAvailabilityChanged = { [weak self] availability in
            guard let self else { return }
            self.bridgeAvailability = availability
            switch availability {
            case .connected:
                self.updateStatus("Connected to Redpanda at localhost:9092")
            case .unavailable(let reason):
                self.updateStatus("Fallback mode: \(reason)")
            }
        }

        bridge.onResponse = { [weak self] response in
            guard let self else { return }
            self.handleRemoteResponse(response)
        }
    }

    private func requestPermissions() {
        listenButton.isEnabled = false
        updateStatus("Requesting microphone and speech recognition permissions…")

        AVCaptureDevice.requestAccess(for: .audio) { [weak self] granted in
            DispatchQueue.main.async {
                self?.microphonePermissionGranted = granted
                self?.refreshPermissionState()
            }
        }

        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            DispatchQueue.main.async {
                self?.speechPermissionGranted = (status == .authorized)
                self?.refreshPermissionState()
            }
        }
    }

    private func refreshPermissionState() {
        let ready = microphonePermissionGranted && speechPermissionGranted && (speechRecognizer?.isAvailable ?? false)
        listenButton.isEnabled = ready

        if ready {
            updateStatus("Ready. Press Enter to talk.")
        } else if !microphonePermissionGranted {
            updateStatus("Microphone access is required. Enable it in System Settings.")
        } else if !speechPermissionGranted {
            updateStatus("Speech recognition access is required. Enable it in System Settings.")
        }
    }

    @objc func toggleListening() {
        if isListening {
            let text = lastHeardText.trimmingCharacters(in: .whitespacesAndNewlines)
            if !text.isEmpty && !didProcessFinalResult {
                didProcessFinalResult = true
                finishListening(with: text)
            } else {
                stopListeningSession(cancelRecognition: true)
                if text.isEmpty {
                    speakAndLog("I didn't hear anything. Please try again.", speaker: "Brain")
                }
            }
        } else {
            startListening()
        }
    }

    private func startListening() {
        guard listenButton.isEnabled else {
            speakAndLog("Microphone or speech recognition permissions are not ready yet.", speaker: "Brain")
            return
        }

        guard let speechRecognizer, speechRecognizer.isAvailable else {
            speakAndLog("Speech recognition is not available right now.", speaker: "Brain")
            return
        }

        stopListeningSession(cancelRecognition: true, updateButton: false)
        didProcessFinalResult = false
        lastHeardText = ""
        isListening = true
        listenButton.title = "Listening… Press Enter to Stop"
        listenButton.setAccessibilityLabel("Stop listening")
        updateStatus("Listening…")

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        request.taskHint = .dictation
        recognitionRequest = request

        let inputNode = audioEngine.inputNode
        inputNode.removeTap(onBus: 0)

        recognitionTask = speechRecognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self else { return }

            if let result {
                let text = result.bestTranscription.formattedString.trimmingCharacters(in: .whitespacesAndNewlines)
                self.updateStatus(text.isEmpty ? "Listening…" : "Heard: \(text)")

                if !text.isEmpty {
                    self.lastHeardText = text
                }

                if result.isFinal, !text.isEmpty, !self.didProcessFinalResult {
                    self.didProcessFinalResult = true
                    self.finishListening(with: text)
                    return
                }
            }

            if let error, !self.didProcessFinalResult {
                self.stopListeningSession(cancelRecognition: true)
                self.speakAndLog("I could not understand that. Please try again.", speaker: "Brain")
                self.updateStatus("Speech recognition error: \(error.localizedDescription)")
            }
        }

        let recordingFormat = inputNode.outputFormat(forBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { [weak self] buffer, _ in
            self?.recognitionRequest?.append(buffer)
        }

        audioEngine.prepare()
        do {
            try audioEngine.start()
            speaker.speak("Listening")
        } catch {
            stopListeningSession(cancelRecognition: true)
            speakAndLog("Audio capture could not start.", speaker: "Brain")
            updateStatus("Audio error: \(error.localizedDescription)")
        }
    }

    private func finishListening(with text: String) {
        stopListeningSession(cancelRecognition: false)
        processInput(text)
    }

    private func stopListeningSession(cancelRecognition: Bool, updateButton: Bool = true) {
        if audioEngine.isRunning {
            audioEngine.stop()
        }

        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        if cancelRecognition {
            recognitionTask?.cancel()
        }
        recognitionRequest = nil
        recognitionTask = nil
        isListening = false

        if updateButton {
            listenButton.title = "Press Enter to Talk"
            listenButton.setAccessibilityLabel("Start listening")
        }
    }
    
    /// Stops listening if currently active (called via Cmd+.)
    @objc func stopListeningIfActive() {
        guard isListening else {
            speakAndLog("Not currently listening.", speaker: "Brain")
            return
        }
        stopListeningSession(cancelRecognition: true)
        speakAndLog("Stopped listening.", speaker: "Brain")
    }
    
    /// Sends the current input if any text was heard (called via Cmd+Return)
    @objc func sendCurrentInput() {
        guard isListening else {
            speakAndLog("Not currently listening. Press Enter to start.", speaker: "Brain")
            return
        }
        let text = lastHeardText.trimmingCharacters(in: .whitespacesAndNewlines)
        if !text.isEmpty && !didProcessFinalResult {
            didProcessFinalResult = true
            finishListening(with: text)
        } else if text.isEmpty {
            speakAndLog("I didn't hear anything. Please try again.", speaker: "Brain")
        }
    }

    private func processInput(_ text: String) {
        if text.hasPrefix("/") { handleAppModeCommand(text); return }
        if currentMode == .yolo { handleAppYOLOCommand(text); return }
        // Cancel any previous stream before starting a fresh one.
        streamingClient?.cancel()
        streamingClient = nil
        tokenFlushTimer?.invalidate()
        tokenFlushTimer = nil
        pendingTokens = ""

        appendTranscript(speaker: "You", text: text)
        let requestID = UUID().uuidString
        currentStreamID = requestID
        streamHeaderShown = false
        
        // Store the original text for RAG storage later
        let originalUserText = text

        // RAG enrichment: enhance prompt with knowledge graph context
        let rag = RAGService.shared
        rag.onStatusUpdate = { [weak self] status in
            DispatchQueue.main.async { self?.updateStatus(status) }
        }
        
        rag.enrichPromptWithRAG(text) { [weak self] enrichedText in
            guard let self, self.currentStreamID == requestID else { return }
            self.processWithLLM(enrichedText, originalText: originalUserText, requestID: requestID)
        }
    }
    
    /// Processes text with LLM after RAG enrichment
    private func processWithLLM(_ text: String, originalText: String, requestID: String) {
        let orchestrator = LLMOrchestrator.shared
        let llmMode = orchestrator.mode

        // Use orchestrator for multi-bot and consensus modes
        if llmMode == .multiBot || llmMode == .consensus {
            updateStatus("Using \(llmMode.displayName) mode…")
            orchestrator.onStatusUpdate = { [weak self] status in
                DispatchQueue.main.async { self?.updateStatus(status) }
            }
            orchestrator.query(text, systemPrompt: currentMode.systemPrompt) { [weak self] response, error in
                DispatchQueue.main.async {
                    guard let self, self.currentStreamID == requestID else { return }
                    if response.isEmpty {
                        self.updateStatus("LLM orchestrator failed. Trying fallback…")
                        self.useRedpandaPath(text: originalText, requestID: requestID)
                    } else {
                        self.appendTranscript(speaker: "Brain", text: response)
                        // Store conversation in RAG
                        RAGService.shared.storeConversation(
                            userMessage: originalText,
                            aiResponse: response,
                            mode: self.currentMode.rawValue
                        )
                        if self.currentMode.speaksResponses { self.speaker.speak(response) }
                        self.updateStatus("Ready. \(self.currentMode.displayName) mode (\(llmMode.displayName)). Press Enter to talk.")
                    }
                }
            }
            return
        }

        // Single LLM mode (default) - use direct streaming
        updateStatus("Connecting to \(orchestrator.primaryLLM.shortName)…")

        let client = LLMStreamingClient()
        streamingClient = client

        // Build config based on orchestrator's primary LLM
        let primaryProvider = orchestrator.primaryLLM
        let config = LLMConfig(
            url: primaryProvider.baseURL,
            model: primaryProvider.defaultModel,
            systemPrompt: currentMode.systemPrompt,
            apiKey: orchestrator.apiKey(for: primaryProvider)
        )

        client.stream(
            config: config,
            userText: text,
            onToken: { [weak self] token in
                guard let self, self.currentStreamID == requestID else { return }
                self.handleIncomingToken(token)
            },
            onComplete: { [weak self] fullText, error in
                guard let self, self.currentStreamID == requestID else { return }
                // Store conversation in RAG after streaming completes
                if !fullText.isEmpty {
                    RAGService.shared.storeConversation(
                        userMessage: originalText,
                        aiResponse: fullText,
                        mode: self.currentMode.rawValue
                    )
                }
                self.handleStreamCompletion(fullText: fullText, error: error,
                                            originalText: originalText, requestID: requestID)
            }
        )
    }

    private func scheduleFallback(for requestID: String, originalText: String) {
        let workItem = DispatchWorkItem { [weak self] in
            self?.respondLocally(to: originalText, requestID: requestID, reason: self?.availabilityReason ?? "no response received")
        }
        pendingFallbacks[requestID] = workItem
        DispatchQueue.main.asyncAfter(deadline: .now() + 7, execute: workItem)
    }

    private func handleRemoteResponse(_ response: BridgeResponse) {
        if let requestID = response.requestID {
            resolvePendingRequest(id: requestID)
        } else if let next = pendingRequestOrder.first {
            resolvePendingRequest(id: next)
        }

        updateStatus(response.isPartial && !response.isFinal ? "Streaming AI response…" : "Received AI response from brain.voice.response")
        appendTranscript(speaker: "Brain", text: ANSIText.strip(response.text))
        if response.isFinal {
            speaker.speak(response.text)
        }
    }

    private func respondLocally(to text: String, requestID: String, reason: String) {
        resolvePendingRequest(id: requestID)
        let response = fallbackResponder.response(for: text, reason: reason)
        updateStatus("Responding locally")
        appendTranscript(speaker: "Brain", text: response)
        speaker.speak(response)
    }

    // MARK: - Streaming Display

    private func handleIncomingToken(_ token: String) {
        // Defer adding the "Brain: " label until the first real token arrives —
        // so nothing appears in the transcript if the stream fails immediately.
        if !streamHeaderShown {
            streamHeaderShown = true
            appendRaw("Brain: ")
        }
        pendingTokens += token
        updateStatus("Receiving response…")
        scheduleTokenFlush()
    }

    /// Coalesces rapid token arrivals into ~30-fps display batches, reducing
    /// NSTextView layout passes and keeping the output smooth without flickering.
    private func scheduleTokenFlush() {
        guard tokenFlushTimer == nil else { return }
        tokenFlushTimer = Timer.scheduledTimer(withTimeInterval: 1.0 / 30.0, repeats: false) { [weak self] _ in
            self?.tokenFlushTimer = nil
            self?.flushPendingTokens()
        }
    }

    private func flushPendingTokens() {
        guard !pendingTokens.isEmpty else { return }
        let chunk = pendingTokens
        pendingTokens = ""
        appendRaw(chunk)
        transcriptView.scrollToEndOfDocument(nil)
    }

    private func handleStreamCompletion(fullText: String, error: Error?,
                                         originalText: String, requestID: String) {
        // Flush any tokens still held in the coalescing buffer.
        tokenFlushTimer?.invalidate()
        tokenFlushTimer = nil
        flushPendingTokens()
        streamingClient = nil

        if fullText.isEmpty {
            // Stream produced no content — fall through to Redpanda then local fallback.
            updateStatus("Local AI unavailable. Trying Redpanda…")
            useRedpandaPath(text: originalText, requestID: requestID)
        } else {
            // Finalize the streamed entry with a blank separator line and speak it.
            appendRaw("\n\n")
            transcriptView.scrollToEndOfDocument(nil)
            if currentMode.speaksResponses { speaker.speak(fullText) }
            updateStatus("Ready. \(currentMode.displayName) mode. Press Enter to talk.")
        }
    }

    /// Falls back to the Redpanda bridge when direct LLM streaming is unavailable.
    private func useRedpandaPath(text: String, requestID: String) {
        pendingRequestOrder.append(requestID)
        updateStatus("Sending your voice command to Redpanda…")
        bridge.publish(text: text, requestID: requestID) { [weak self] success, reason in
            guard let self else { return }
            if success {
                self.updateStatus("Waiting for AI response on brain.voice.response…")
                self.scheduleFallback(for: requestID, originalText: text)
            } else {
                self.updateStatus("Redpanda publish failed. Using local fallback.")
                self.respondLocally(to: text, requestID: requestID, reason: reason ?? "publish failed")
            }
        }
    }

    /// Appends text directly to the transcript storage using the view's current font.
    /// Must be called on the main thread.
    private func appendRaw(_ text: String) {
        guard let storage = transcriptView.textStorage else { return }
        let font = transcriptView.font ?? NSFont.monospacedSystemFont(ofSize: 15, weight: .regular)
        storage.beginEditing()
        storage.append(NSAttributedString(string: ANSIText.strip(text), attributes: [.font: font]))
        storage.endEditing()
    }

    private func resolvePendingRequest(id: String) {
        pendingFallbacks[id]?.cancel()
        pendingFallbacks[id] = nil
        pendingRequestOrder.removeAll { $0 == id }
    }

    private var availabilityReason: String {
        switch bridgeAvailability {
        case .connected:
            return "broker is connected but no response arrived"
        case .unavailable(let reason):
            return reason
        }
    }

    private func updateStatus(_ text: String) {
        statusLabel.stringValue = text
        ScriptingState.shared.currentStatus = text
    }

    private func appendTranscript(speaker: String, text: String) {
        let entry = "\(speaker): \(ANSIText.strip(text))\n\n"
        let attributed = NSAttributedString(string: entry)
        transcriptView.textStorage?.append(attributed)
        transcriptView.scrollToEndOfDocument(nil)
    }


    // MARK: - Mode Management

    private let appLLMSelector = LLMSelectorUI()
    private let appRAGSelector = RAGSelectorUI()

    private func handleAppModeCommand(_ input: String) {
        let cmd = input.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)

        // Handle /llm commands
        if cmd.hasPrefix("/llm") {
            let handled = appLLMSelector.handleCommand(input)
            if handled {
                // Announce the change for accessibility
                let orchestrator = LLMOrchestrator.shared
                speakAndLog("LLM configuration updated. Mode: \(orchestrator.mode.displayName), Primary: \(orchestrator.primaryLLM.shortName)", speaker: "Brain")
            }
            return
        }
        
        // Handle /rag commands
        if cmd.hasPrefix("/rag") {
            let handled = appRAGSelector.handleCommand(input)
            if handled {
                let status = RAGSettings.isEnabled ? "enabled" : "disabled"
                speakAndLog("RAG \(status). Neo4j \(RAGService.shared.isAvailable ? "connected" : "unavailable").", speaker: "Brain")
            }
            return
        }

        if cmd == "/modes" || cmd == "/help" {
            var lines = ["Available modes:"]
            for mode in ChatMode.allCases {
                lines.append((mode == currentMode ? "> " : "  ")
                             + mode.switchCommand + ": " + mode.modeDescription)
            }
            lines.append("")
            lines.append("LLM Commands:")
            lines.append("  /llm status - Show LLM configuration")
            lines.append("  /llm help - Show all LLM commands")
            lines.append("")
            lines.append("RAG Commands:")
            lines.append("  /rag - Show RAG status")
            lines.append("  /rag help - Show RAG commands")
            speakAndLog(lines.joined(separator: "\n"), speaker: "Brain")
            return
        }
        if let mode = ChatMode.allCases.first(where: { cmd == $0.switchCommand }) {
            currentMode = mode
            ModePreferences.save(mode)
            modeBadgeLabel.stringValue = "\(mode.displayName) Mode"
            modeBadgeLabel.setAccessibilityLabel("Current mode: \(mode.displayName)")
            speakAndLog("Switched to \(mode.displayName) mode. \(mode.modeDescription)", speaker: "Brain")
            updateStatus("Mode: \(mode.displayName)")
        } else {
            speakAndLog("Unknown command: \(input). Say slash modes for help.", speaker: "Brain")
        }
    }

    private func handleAppYOLOCommand(_ command: String) {
        appendTranscript(speaker: "You", text: "yolo: \(command)")
        updateStatus("Publishing YOLO command to brain.yolo.commands…")
        let reqID = UUID().uuidString
        bridge.publish(text: "yolo: \(command)", requestID: reqID) { [weak self] success, reason in
            guard let self else { return }
            if success {
                self.speakAndLog("YOLO command published: \(command)", speaker: "Brain")
                self.updateStatus("Ready. Press Enter to talk.")
            } else {
                self.speakAndLog("YOLO publish failed: \(reason ?? "unknown error")", speaker: "Brain")
                self.updateStatus("YOLO publish failed.")
            }
        }
    }

    private func speakAndLog(_ text: String, speaker: String) {
        appendTranscript(speaker: speaker, text: text)
        self.speaker.speak(text)
    }
    
    // MARK: - AppleScript Handler Methods
    
    /// Expose current mode for AppleScript
    var currentModeForScript: ChatMode { currentMode }
    
    /// Expose listening state for AppleScript
    var isListeningForScript: Bool { isListening }
    
    /// Expose bridge availability for AppleScript
    var bridgeAvailabilityForScript: RedpandaBridge.Availability { bridgeAvailability }
    
    /// Register AppleEvent handlers for direct scripting support
    private func registerAppleEventHandlers() {
        let em = NSAppleEventManager.shared()
        
        // Register for custom Apple Events
        // BrCh = Brain Chat suite code
        let brChCode = FourCharCode("BrCh")
        
        // set mode command (BrChSMod)
        em.setEventHandler(self, andSelector: #selector(handleSetModeEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("SMod"))
        
        // get mode command (BrChGMod)
        em.setEventHandler(self, andSelector: #selector(handleGetModeEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("GMod"))
        
        // list modes command (BrChLMod)
        em.setEventHandler(self, andSelector: #selector(handleListModesEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("LMod"))
        
        // send message command (BrChSend)
        em.setEventHandler(self, andSelector: #selector(handleSendMessageEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("Send"))
        
        // get response command (BrChResp)
        em.setEventHandler(self, andSelector: #selector(handleGetResponseEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("Resp"))
        
        // speak command (BrChSpek)
        em.setEventHandler(self, andSelector: #selector(handleSpeakEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("Spek"))
        
        // start listening command (BrChStLs)
        em.setEventHandler(self, andSelector: #selector(handleStartListeningEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("StLs"))
        
        // stop listening command (BrChSpLs)
        em.setEventHandler(self, andSelector: #selector(handleStopListeningEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("SpLs"))
        
        // get status command (BrChGSta)
        em.setEventHandler(self, andSelector: #selector(handleGetStatusEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("GSta"))
        
        // health check command (BrChHlth)
        em.setEventHandler(self, andSelector: #selector(handleHealthCheckEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("Hlth"))
        
        // bridge status command (BrChBrSt)
        em.setEventHandler(self, andSelector: #selector(handleBridgeStatusEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("BrSt"))
        
        // get transcript command (BrChTrns)
        em.setEventHandler(self, andSelector: #selector(handleGetTranscriptEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("Trns"))
        
        // clear transcript command (BrChClTr)
        em.setEventHandler(self, andSelector: #selector(handleClearTranscriptEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("ClTr"))
        
        // execute yolo command (BrChYolo)
        em.setEventHandler(self, andSelector: #selector(handleYoloEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("Yolo"))
        
        // set llm command (BrChSLLM)
        em.setEventHandler(self, andSelector: #selector(handleSetLLMEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("SLLM"))
        
        // get llm command (BrChGLLM)
        em.setEventHandler(self, andSelector: #selector(handleGetLLMEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("GLLM"))
        
        // show window command (BrChShWn)
        em.setEventHandler(self, andSelector: #selector(handleShowWindowEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("ShWn"))
        
        // hide window command (BrChHdWn)
        em.setEventHandler(self, andSelector: #selector(handleHideWindowEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("HdWn"))
        
        // announce command (BrChAnno)
        em.setEventHandler(self, andSelector: #selector(handleAnnounceEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("Anno"))
        
        // describe ui command (BrChDsUI)
        em.setEventHandler(self, andSelector: #selector(handleDescribeUIEvent(_:withReply:)),
                          forEventClass: brChCode, andEventID: FourCharCode("DsUI"))
    }
    
    // MARK: - AppleEvent Handlers
    
    @objc func handleSetModeEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        if let param = event.paramDescriptor(forKeyword: keyDirectObject)?.stringValue,
           let mode = ChatMode(rawValue: param.lowercased()) {
            DispatchQueue.main.async { self.setModeFromScript(mode) }
            reply.setDescriptor(NSAppleEventDescriptor(string: "Switched to \(mode.displayName) mode"), forKeyword: keyDirectObject)
        }
    }
    
    @objc func handleGetModeEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        reply.setDescriptor(NSAppleEventDescriptor(string: currentMode.rawValue), forKeyword: keyDirectObject)
    }
    
    @objc func handleListModesEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        let modes = ChatMode.allCases.map { "\($0.rawValue): \($0.modeDescription)" }.joined(separator: "\n")
        reply.setDescriptor(NSAppleEventDescriptor(string: modes), forKeyword: keyDirectObject)
    }
    
    @objc func handleSendMessageEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        guard let message = event.paramDescriptor(forKeyword: keyDirectObject)?.stringValue else { return }
        
        // For synchronous operation, we need to use a semaphore
        let sem = DispatchSemaphore(value: 0)
        var responseText = ""
        
        DispatchQueue.main.async {
            self.sendMessageFromScript(message) { result in
                responseText = result
                sem.signal()
            }
        }
        
        // Wait up to 60 seconds
        _ = sem.wait(timeout: .now() + 60)
        reply.setDescriptor(NSAppleEventDescriptor(string: responseText), forKeyword: keyDirectObject)
    }
    
    @objc func handleGetResponseEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        reply.setDescriptor(NSAppleEventDescriptor(string: ScriptingState.shared.lastResponse), forKeyword: keyDirectObject)
    }
    
    @objc func handleSpeakEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        if let text = event.paramDescriptor(forKeyword: keyDirectObject)?.stringValue {
            DispatchQueue.main.async { self.speakFromScript(text) }
        }
    }
    
    @objc func handleStartListeningEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        DispatchQueue.main.async { self.startListeningFromScript() }
        reply.setDescriptor(NSAppleEventDescriptor(boolean: true), forKeyword: keyDirectObject)
    }
    
    @objc func handleStopListeningEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        var heardText = ""
        let sem = DispatchSemaphore(value: 0)
        DispatchQueue.main.async {
            heardText = self.stopListeningFromScript()
            sem.signal()
        }
        _ = sem.wait(timeout: .now() + 5)
        reply.setDescriptor(NSAppleEventDescriptor(string: heardText), forKeyword: keyDirectObject)
    }
    
    @objc func handleGetStatusEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        reply.setDescriptor(NSAppleEventDescriptor(string: ScriptingState.shared.currentStatus), forKeyword: keyDirectObject)
    }
    
    @objc func handleHealthCheckEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        var result = ""
        let sem = DispatchSemaphore(value: 0)
        DispatchQueue.main.async {
            result = self.healthCheckFromScript()
            sem.signal()
        }
        _ = sem.wait(timeout: .now() + 5)
        reply.setDescriptor(NSAppleEventDescriptor(string: result), forKeyword: keyDirectObject)
    }
    
    @objc func handleBridgeStatusEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        var result = ""
        let sem = DispatchSemaphore(value: 0)
        DispatchQueue.main.async {
            result = self.bridgeStatusFromScript()
            sem.signal()
        }
        _ = sem.wait(timeout: .now() + 2)
        reply.setDescriptor(NSAppleEventDescriptor(string: result), forKeyword: keyDirectObject)
    }
    
    @objc func handleGetTranscriptEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        let lines = event.paramDescriptor(forKeyword: FourCharCode("lins"))?.int32Value
        var result = ""
        let sem = DispatchSemaphore(value: 0)
        DispatchQueue.main.async {
            result = self.getTranscriptFromScript(lines: lines.map { Int($0) })
            sem.signal()
        }
        _ = sem.wait(timeout: .now() + 2)
        reply.setDescriptor(NSAppleEventDescriptor(string: result), forKeyword: keyDirectObject)
    }
    
    @objc func handleClearTranscriptEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        DispatchQueue.main.async { self.clearTranscriptFromScript() }
    }
    
    @objc func handleYoloEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        guard let command = event.paramDescriptor(forKeyword: keyDirectObject)?.stringValue else { return }
        
        let sem = DispatchSemaphore(value: 0)
        var result = ""
        
        DispatchQueue.main.async {
            self.executeYoloFromScript(command) { response in
                result = response
                sem.signal()
            }
        }
        
        _ = sem.wait(timeout: .now() + 30)
        reply.setDescriptor(NSAppleEventDescriptor(string: result), forKeyword: keyDirectObject)
    }
    
    @objc func handleSetLLMEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        if let model = event.paramDescriptor(forKeyword: keyDirectObject)?.stringValue {
            ScriptingState.shared.customLLMModel = model
            reply.setDescriptor(NSAppleEventDescriptor(string: "LLM set to \(model)"), forKeyword: keyDirectObject)
        }
    }
    
    @objc func handleGetLLMEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        let model = ScriptingState.shared.customLLMModel ?? currentMode.llmModel
        reply.setDescriptor(NSAppleEventDescriptor(string: model), forKeyword: keyDirectObject)
    }
    
    @objc func handleShowWindowEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        DispatchQueue.main.async { self.showWindowFromScript() }
    }
    
    @objc func handleHideWindowEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        DispatchQueue.main.async { self.hideWindowFromScript() }
    }
    
    @objc func handleAnnounceEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        if let text = event.paramDescriptor(forKeyword: keyDirectObject)?.stringValue {
            let priority = event.paramDescriptor(forKeyword: FourCharCode("prio"))?.stringValue ?? "normal"
            DispatchQueue.main.async { self.announceFromScript(text, priority: priority) }
        }
    }
    
    @objc func handleDescribeUIEvent(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        var result = ""
        let sem = DispatchSemaphore(value: 0)
        DispatchQueue.main.async {
            result = self.describeUIFromScript()
            sem.signal()
        }
        _ = sem.wait(timeout: .now() + 2)
        reply.setDescriptor(NSAppleEventDescriptor(string: result), forKeyword: keyDirectObject)
    }
    
    func setModeFromScript(_ mode: ChatMode) {
        currentMode = mode
        ModePreferences.save(mode)
        modeBadgeLabel.stringValue = "\(mode.displayName) Mode"
        modeBadgeLabel.setAccessibilityLabel("Current mode: \(mode.displayName)")
        speakAndLog("Switched to \(mode.displayName) mode via AppleScript.", speaker: "Brain")
        updateStatus("Mode: \(mode.displayName)")
    }
    
    func startListeningFromScript() {
        if !isListening {
            toggleListening()
        }
    }
    
    func stopListeningFromScript() -> String {
        let heardText = lastHeardText
        if isListening {
            toggleListening()
        }
        return heardText
    }
    
    func speakFromScript(_ text: String) {
        speaker.speak(text)
    }
    
    func stopSpeakingFromScript() {
        // SpeechVoice stops any current speech when speak() is called with empty
        // For explicit stop, we'd need to expose the synthesizer
        speaker.speak("")
    }
    
    func sendMessageFromScript(_ message: String, completion: @escaping (String) -> Void) {
        appendTranscript(speaker: "You (AppleScript)", text: message)
        updateStatus("Processing AppleScript message…")
        
        let config = ScriptingState.shared.customLLMModel.map { model in
            LLMConfig(
                url: URL(string: "http://localhost:11434/v1/chat/completions")!,
                model: model,
                systemPrompt: currentMode.systemPrompt
            )
        } ?? .mode(currentMode)
        
        let client = LLMStreamingClient()
        var fullResponse = ""
        
        client.stream(
            config: config,
            userText: message,
            onToken: { token in
                fullResponse += token
            },
            onComplete: { [weak self] text, error in
                DispatchQueue.main.async {
                    if let error = error {
                        let errMsg = "Error: \(error.localizedDescription)"
                        ScriptingState.shared.lastResponse = errMsg
                        self?.appendTranscript(speaker: "Brain", text: errMsg)
                        self?.updateStatus("Error occurred")
                        completion(errMsg)
                    } else {
                        let response = text.isEmpty ? fullResponse : text
                        ScriptingState.shared.lastResponse = response
                        self?.appendTranscript(speaker: "Brain", text: response)
                        self?.updateStatus("Ready. \(self?.currentMode.displayName ?? "Chat") mode.")
                        if self?.currentMode.speaksResponses == true {
                            self?.speaker.speak(response)
                        }
                        completion(response)
                    }
                }
            }
        )
        
        streamingClient = client
    }
    
    func sendMessageAsyncFromScript(_ message: String, requestID: String) {
        ScriptingState.shared.lastRequestID = requestID
        sendMessageFromScript(message) { _ in }
    }
    
    func getTranscriptFromScript(lines: Int?) -> String {
        let fullText = transcriptView.string
        guard let lines = lines, lines > 0 else { return fullText }
        
        let allLines = fullText.components(separatedBy: "\n")
        let recentLines = allLines.suffix(lines)
        return recentLines.joined(separator: "\n")
    }
    
    func clearTranscriptFromScript() {
        transcriptView.string = ""
        speakAndLog("Transcript cleared via AppleScript.", speaker: "Brain")
    }
    
    func executeYoloFromScript(_ command: String, completion: @escaping (String) -> Void) {
        appendTranscript(speaker: "YOLO (AppleScript)", text: command)
        updateStatus("Publishing YOLO command…")
        
        let reqID = UUID().uuidString
        bridge.publish(text: "yolo: \(command)", requestID: reqID) { [weak self] success, reason in
            DispatchQueue.main.async {
                if success {
                    let msg = "YOLO command published: \(command)"
                    self?.appendTranscript(speaker: "Brain", text: msg)
                    self?.updateStatus("Ready. Press Enter to talk.")
                    completion(msg)
                } else {
                    let msg = "YOLO publish failed: \(reason ?? "unknown error")"
                    self?.appendTranscript(speaker: "Brain", text: msg)
                    self?.updateStatus("YOLO publish failed.")
                    completion(msg)
                }
            }
        }
    }
    
    func connectBridgeFromScript() {
        bridge.start()
        speakAndLog("Bridge connection initiated via AppleScript.", speaker: "Brain")
    }
    
    func disconnectBridgeFromScript() {
        bridge.stop()
        speakAndLog("Bridge disconnected via AppleScript.", speaker: "Brain")
    }
    
    func bridgeStatusFromScript() -> String {
        switch bridgeAvailability {
        case .connected:
            return "Connected to Redpanda"
        case .unavailable(let reason):
            return "Unavailable: \(reason)"
        }
    }
    
    func healthCheckFromScript() -> String {
        var health: [String] = []
        health.append("Brain Chat Health Check")
        health.append("=======================")
        health.append("Mode: \(currentMode.displayName)")
        health.append("LLM: \(ScriptingState.shared.customLLMModel ?? currentMode.llmModel)")
        health.append("Bridge: \(bridgeStatusFromScript())")
        health.append("RAG: \(RAGSettings.isEnabled ? "Enabled" : "Disabled") - Neo4j: \(RAGService.shared.isAvailable ? "Connected" : "Unavailable")")
        health.append("Listening: \(isListening ? "Yes" : "No")")
        health.append("Speech Permission: \(speechPermissionGranted ? "Granted" : "Not Granted")")
        health.append("Microphone Permission: \(microphonePermissionGranted ? "Granted" : "Not Granted")")
        return health.joined(separator: "\n")
    }
    
    func showWindowFromScript() {
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
    
    func hideWindowFromScript() {
        window.orderOut(nil)
    }
    
    func announceFromScript(_ text: String, priority: String) {
        // Use NSAccessibilityPriorityKey directly
        let priorityNumber: Int
        switch priority.lowercased() {
        case "high":
            priorityNumber = 1  // NSAccessibilityPriorityHigh
        case "low":
            priorityNumber = 3  // NSAccessibilityPriorityLow
        default:
            priorityNumber = 2  // NSAccessibilityPriorityMedium
        }
        
        let userInfo: [NSAccessibility.NotificationUserInfoKey: Any] = [
            .announcement: text,
            .priority: NSNumber(value: priorityNumber)
        ]
        NSAccessibility.post(element: window as Any, notification: .announcementRequested, userInfo: userInfo)
        speaker.speak(text)
    }
    
    func describeUIFromScript() -> String {
        var description: [String] = []
        description.append("Brain Chat Window")
        description.append("Current mode: \(currentMode.displayName)")
        description.append("Status: \(statusLabel.stringValue)")
        description.append("Listen button: \(listenButton.title)")
        description.append("Listening: \(isListening ? "Active" : "Inactive")")
        
        let transcriptLines = transcriptView.string.components(separatedBy: "\n").count
        description.append("Transcript: \(transcriptLines) lines")
        
        return description.joined(separator: "\n")
    }
}

if TerminalChatController.shouldRunInTerminal {
    let terminalChat = TerminalChatController()
    terminalChat.run()
} else {
    let app = NSApplication.shared
    let delegate = AppDelegate()
    app.setActivationPolicy(.regular)
    app.delegate = delegate
    app.run()
}
