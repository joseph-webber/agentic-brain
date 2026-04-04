import Cocoa
import Speech
import AVFoundation
import Darwin

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
    private let synthesizer = AVSpeechSynthesizer()

    init() {}

    func speak(_ text: String) {
        let cleanText = ANSIText.strip(text)
        guard !cleanText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }

        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking(at: .immediate)
        }

        let utterance = AVSpeechUtterance(string: cleanText)
        utterance.rate = 0.48
        utterance.voice = Self.preferredVoice()
        synthesizer.speak(utterance)
    }

    private static func preferredVoice() -> AVSpeechSynthesisVoice? {
        let voices = AVSpeechSynthesisVoice.speechVoices()
        if let karen = voices.first(where: { $0.name.localizedCaseInsensitiveContains("Karen") && $0.language.hasPrefix("en-AU") }) {
            return karen
        }
        return voices.first(where: { $0.language.hasPrefix("en-AU") })
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
    static let green = escape + "32m"
    static let cyan = escape + "36m"
    static let yellow = escape + "33m"
    static let magenta = escape + "35m"
    static let clearLine = escape + "2K"
    static let saveCursor = escape + "s"
    static let restoreCursor = escape + "u"
    static let hideCursor = escape + "?25l"
    static let showCursor = escape + "?25h"
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

    /// Claude via Anthropic Messages API.
    static func claude(apiKey: String, model: String = "claude-sonnet-4-20250514") -> LLMConfig {
        LLMConfig(
            url: URL(string: "https://api.anthropic.com/v1/messages")!,
            model: model,
            systemPrompt: "You are Iris Lumina, an AI assistant for Joseph, who is blind and uses VoiceOver on macOS. Keep responses concise and clear. No filler phrases.",
            apiKey: apiKey, maxTokens: 1024
        )
    }

    /// OpenAI-compatible endpoint (GPT, Groq, etc).
    static func openAI(apiKey: String, url: String = "https://api.openai.com/v1/chat/completions",
                        model: String = "gpt-4o-mini") -> LLMConfig {
        LLMConfig(
            url: URL(string: url)!,
            model: model,
            systemPrompt: "You are Iris Lumina, an AI assistant for Joseph, who is blind and uses VoiceOver on macOS. Keep responses concise and clear. No filler phrases.",
            apiKey: apiKey, maxTokens: 1024
        )
    }
}

// MARK: - Speech Batcher

/// Batches incoming tokens into speakable chunks at natural sentence/clause boundaries.
final class SpeechBatcher {
    var onChunkReady: ((String) -> Void)?
    private var buffer = ""
    private var flushTimer: DispatchSourceTimer?
    private let flushInterval: TimeInterval
    private let minChunkLength: Int

    init(flushInterval: TimeInterval = 1.2, minChunkLength: Int = 40) {
        self.flushInterval  = flushInterval
        self.minChunkLength = minChunkLength
    }

    func feed(_ token: String) {
        buffer += token
        resetTimer()
        if buffer.last == "." || buffer.last == "!" || buffer.last == "?" {
            emitAll(); return
        }
        if buffer.count >= minChunkLength,
           (buffer.last == "," || buffer.last == ";" || buffer.last == ":") {
            emitAll(); return
        }
        if buffer.hasSuffix("\n") {
            let t = buffer.trimmingCharacters(in: .whitespacesAndNewlines)
            if !t.isEmpty { emitAll() }
        }
    }

    func flush() {
        cancelTimer()
        let t = buffer.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty else { buffer = ""; return }
        emitAll()
    }

    func cancel() { cancelTimer(); buffer = "" }

    private func emitAll() {
        let chunk = buffer.trimmingCharacters(in: .whitespacesAndNewlines)
        buffer = ""
        guard !chunk.isEmpty else { return }
        cancelTimer(); onChunkReady?(chunk)
    }

    private func resetTimer() {
        cancelTimer()
        let t = DispatchSource.makeTimerSource(queue: .main)
        t.schedule(deadline: .now() + flushInterval)
        t.setEventHandler { [weak self] in self?.flush() }
        t.resume()
        flushTimer = t
    }

    private func cancelTimer() { flushTimer?.cancel(); flushTimer = nil }
    deinit { cancelTimer() }
}

// MARK: - Typing Indicator

/// Animates "..." dots while waiting for the first LLM token.
final class TypingIndicator {
    var onFrame: ((String) -> Void)?
    private var timer: DispatchSourceTimer?
    private var dotCount = 0
    private(set) var isActive = false

    func start() {
        guard !isActive else { return }
        isActive = true; dotCount = 0
        let t = DispatchSource.makeTimerSource(queue: .main)
        t.schedule(deadline: .now(), repeating: .milliseconds(400))
        t.setEventHandler { [weak self] in
            guard let self, self.isActive else { return }
            self.dotCount = (self.dotCount % 3) + 1
            self.onFrame?(String(repeating: ".", count: self.dotCount))
        }
        t.resume(); timer = t
    }

    func stop() { isActive = false; timer?.cancel(); timer = nil }
    deinit { stop() }
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
        case httpError(Int, String?)
        case connectionFailed(Error)
        case cancelled
        var errorDescription: String? {
            switch self {
            case .httpError(let code, let body):
                return body.map { "HTTP \(code): \($0)" } ?? "HTTP \(code)"
            case .connectionFailed(let err): return err.localizedDescription
            case .cancelled: return "Generation cancelled"
            }
        }
    }

    /// `true` while a stream request is in-flight (including retry back-off waits).
    private(set) var isStreaming = false

    // Callbacks — always invoked on the main thread.
    var onToken: ((String) -> Void)?
    var onComplete: ((String, Error?) -> Void)?

    private var _session: URLSession?
    private var session: URLSession {
        if let s = _session { return s }
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest  = 10
        cfg.timeoutIntervalForResource = 180
        cfg.requestCachePolicy = .reloadIgnoringLocalCacheData
        let s = URLSession(configuration: cfg, delegate: self, delegateQueue: nil)
        _session = s; return s
    }

    private var currentTask: URLSessionDataTask?
    private var utf8Tail    = Data()
    private var lineBuf     = ""
    private var accumulated = ""
    private var errorBody   = Data()
    private var currentSSEEventType: String?

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
        errorBody = Data(); currentSSEEventType = nil
        sendRequest()
    }

    func cancel() {
        guard isStreaming else { return }
        isStreaming = false
        currentTask?.cancel(); currentTask = nil
        _session?.invalidateAndCancel(); _session = nil
        let text = accumulated
        DispatchQueue.main.async { [weak self] in
            self?.onComplete?(text, text.isEmpty ? StreamError.cancelled : nil)
        }
    }


    // MARK: Private: request

    private func sendRequest() {
        guard let config = pendingConfig else { return }

        var req = URLRequest(url: config.url)
        req.httpMethod = "POST"
        req.setValue("application/json",                     forHTTPHeaderField: "Content-Type")
        req.setValue("text/event-stream, application/json",  forHTTPHeaderField: "Accept")
        let isAnthropic = config.url.host?.contains("anthropic") == true
            || config.model.hasPrefix("claude")
        if isAnthropic {
            if let key = config.apiKey { req.setValue(key, forHTTPHeaderField: "x-api-key") }
            req.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
        } else if let key = config.apiKey {
            req.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
        }

        let body: [String: Any]
        if isAnthropic {
            let userMsgs = pendingMessages.filter { ($0["role"] as? String) != "system" }
            body = ["model": config.model, "system": config.systemPrompt,
                    "messages": userMsgs, "stream": true,
                    "temperature": config.temperature, "max_tokens": config.maxTokens]
        } else {
            body = ["model": config.model, "messages": pendingMessages, "stream": true,
                    "temperature": config.temperature, "max_tokens": config.maxTokens]
        }
        guard let bodyData = try? JSONSerialization.data(withJSONObject: body) else {
            finish(error: StreamError.connectionFailed(
                NSError(domain: "LLM", code: -1,
                        userInfo: [NSLocalizedDescriptionKey: "Request serialization failed"])))
            return
        }
        req.httpBody = bodyData

        utf8Tail = Data(); lineBuf = ""; errorBody = Data(); currentSSEEventType = nil

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
            finish(error: StreamError.httpError(-1, nil))
            return
        }
        if (200..<300).contains(http.statusCode) {
            completionHandler(.allow)
        } else {
            errorBody = Data()
            completionHandler(.allow)  // collect error body for reporting
        }
    }

    func urlSession(_ session: URLSession,
                    dataTask: URLSessionDataTask,
                    didReceive data: Data) {
        if let http = dataTask.response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            errorBody.append(data); return
        }
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
        if let http = task.response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            let bodyStr = String(data: errorBody, encoding: .utf8).map { String($0.prefix(500)) }
            finish(error: StreamError.httpError(http.statusCode, bodyStr)); return
        }
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

        // Track SSE event type (used by Anthropic).
        if line.hasPrefix("event:") {
            currentSSEEventType = String(line.dropFirst("event:".count)).trimmingCharacters(in: .whitespaces)
            return
        }
        if line.hasPrefix(":") { return }  // SSE comment

        let jsonStr: String
        if line.hasPrefix("data: ") {
            let p = String(line.dropFirst("data: ".count))
            if p == "[DONE]" { currentSSEEventType = nil; return }
            jsonStr = p
        } else if line.hasPrefix("data:") {
            let p = String(line.dropFirst("data:".count)).trimmingCharacters(in: .whitespaces)
            if p == "[DONE]" { currentSSEEventType = nil; return }
            jsonStr = p
        } else { jsonStr = line }

        guard let jd = jsonStr.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: jd) as? [String: Any] else {
            currentSSEEventType = nil; return
        }

        // OpenAI format
        if let choices = json["choices"] as? [[String: Any]],
           let delta = choices.first?["delta"] as? [String: Any],
           let content = delta["content"] as? String, !content.isEmpty {
            emit(content); currentSSEEventType = nil; return
        }
        // Anthropic content_block_delta
        if let t = json["type"] as? String, t == "content_block_delta",
           let delta = json["delta"] as? [String: Any],
           let text = delta["text"] as? String, !text.isEmpty {
            emit(text); currentSSEEventType = nil; return
        }
        if currentSSEEventType == "content_block_delta",
           let delta = json["delta"] as? [String: Any],
           let text = delta["text"] as? String, !text.isEmpty {
            emit(text); currentSSEEventType = nil; return
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
        guard isStreaming else { return }
        isStreaming = false
        _session?.finishTasksAndInvalidate(); _session = nil
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
    private let agentResultsSubscriber = AgentResultsSubscriber()
    private let fallbackResponder = LocalFallbackResponder()
    private let speaker = SpeechVoice()
    private let terminalMode = TerminalMode()
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

    // LLM streaming state
    private var streamingClient: LLMStreamingClient?
    private var currentStreamID: String?
    private var streamPrefixShown = false   // true once "Brain> " has been written
    private let copilotBridge = GHCopilotBridge()
    private let speechBatcher = SpeechBatcher()
    private let typingIndicator = TypingIndicator()

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
        configureAgentSubscriber()
        setupInputSource()
        renderWelcome()
        bridge.start()
        agentResultsSubscriber.start()
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

    private func configureAgentSubscriber() {
        agentResultsSubscriber.onStatusChanged = { [weak self] (message: String) in
            self?.uiQueue.async { self?.writeStatus(message) }
        }

        agentResultsSubscriber.onResult = { [weak self] (result: AgentResultsSubscriber.AgentResult) in
            self?.uiQueue.async {
                guard let self else { return }
                let label = result.agentName.map { "\($0) (Agent)" } ?? "Agent"
                let taskSuffix = result.taskID.map { " [\($0)]" } ?? ""
                let cleanText = ANSIText.strip(result.text)
                self.writeTranscriptLine(
                    prefix: label + taskSuffix,
                    text: cleanText,
                    color: TerminalANSI.magenta
                )
                DispatchQueue.main.async { self.speaker.speak(cleanText) }
                self.renderPrompt()
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
            // Ctrl+C/D: cancel stream if active, otherwise exit.
            if streamingClient?.isStreaming == true {
                cancelCurrentStream(reason: "Stopped by user")
            } else {
                shutdown(exitCode: 0)
            }
        case 27:
            if streamingClient?.isStreaming == true {
                cancelCurrentStream(reason: "Stopped by user")
            } else {
                escapeSequencePending = true
            }
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

    private func cancelCurrentStream(reason: String?) {
        typingIndicator.stop()
        speechBatcher.cancel()
        streamingClient?.cancel()
        streamingClient = nil
        currentStreamID = nil
        writeRaw("\r\n")
        if let reason { writeStatus(reason) }
        renderPrompt()
    }

    private func renderWelcome() {
        let intro = ANSIText.strip("Brain Chat terminal mode is ready. Type a message and press Return. Press Control C to exit.")
        writeLine(colorize(intro, color: TerminalANSI.bold + TerminalANSI.magenta))
        writeLine("VoiceOver-friendly mode: set BRAINCHAT_ACCESSIBLE_TERMINAL=1 to disable cursor tricks and ANSI colors.")
        DispatchQueue.main.async {
            self.speaker.speak("Brain Chat is ready. Type a message and press Return.")
        }
    }

    private func processInput(_ text: String) {
        cancelCurrentStream(reason: nil)

        writeTranscriptLine(prefix: "You", text: text, color: TerminalANSI.cyan)
        let requestID = UUID().uuidString
        currentStreamID = requestID
        streamPrefixShown = false

        typingIndicator.onFrame = { [weak self] dots in
            guard let self, self.richTTYEnabled else { return }
            self.writeRaw("\r" + TerminalANSI.clearLine)
            self.writeRaw(self.colorize("Brain> ", color: TerminalANSI.dim + TerminalANSI.green) + dots)
        }
        typingIndicator.start()

        speechBatcher.cancel()
        speechBatcher.onChunkReady = { [weak self] chunk in
            DispatchQueue.main.async { self?.speaker.speak(chunk) }
        }

        writeStatus("Connecting to local AI\u{2026} (Esc to cancel)")

        let client = LLMStreamingClient()
        streamingClient = client

        client.stream(
            config: .default,
            userText: text,
            onToken: { [weak self] token in
                self?.uiQueue.async {
                    guard let self, self.currentStreamID == requestID else { return }
                    if !self.streamPrefixShown {
                        self.typingIndicator.stop()
                        self.streamPrefixShown = true
                        if self.richTTYEnabled {
                            self.writeRaw("\r" + TerminalANSI.clearLine)
                        }
                        self.promptVisible = false
                        self.writeRaw(self.colorize("Brain> ", color: TerminalANSI.green + TerminalANSI.bold))
                    }
                    self.writeRaw(ANSIText.strip(token))
                    self.speechBatcher.feed(token)
                }
            },
            onComplete: { [weak self] fullText, error in
                self?.uiQueue.async {
                    guard let self, self.currentStreamID == requestID else { return }
                    self.typingIndicator.stop()
                    self.speechBatcher.flush()
                    self.streamingClient = nil
                    if fullText.isEmpty {
                        self.writeStatus("Local AI unavailable. Trying Redpanda\u{2026}")
                        self.useRedpandaPath(text: text, requestID: requestID)
                    } else {
                        self.writeRaw("\r\n")
                        if let error {
                            self.writeStatus("Stream ended: \(error.localizedDescription)")
                        } else {
                            self.writeStatus("Ready. (Esc to stop, Ctrl+C to exit)")
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

        let prompt = colorize("You> ", color: TerminalANSI.cyan + TerminalANSI.bold) + inputBuffer
        if richTTYEnabled {
            writeRaw("\r" + TerminalANSI.clearLine + prompt)
        } else {
            writeRaw(promptVisible ? "\r> \(inputBuffer)" : prompt)
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

    // MARK: - Copilot Integration

    private func handleCopilotCommand(_ command: GHCopilotBridge.CopilotCommand) {
        switch command {
        case .startSession:
            writeStatus("Starting Copilot chat session…")
            do {
                try copilotBridge.startSession(mode: .chat)
                let msg = "Copilot chat session started. Use /copilot followed by your message."
                writeTranscriptLine(prefix: "Copilot", text: msg, color: TerminalANSI.magenta)
                DispatchQueue.main.async { self.speaker.speak(msg) }
            } catch {
                writeTranscriptLine(prefix: "Copilot", text: error.localizedDescription, color: TerminalANSI.yellow)
            }
            renderPrompt()
        case .stopSession:
            copilotBridge.endSession()
            writeTranscriptLine(prefix: "Copilot", text: "Copilot session ended.", color: TerminalANSI.magenta)
            DispatchQueue.main.async { self.speaker.speak("Copilot session ended.") }
            renderPrompt()
        case .restartSession:
            do { try copilotBridge.restartSession()
                writeTranscriptLine(prefix: "Copilot", text: "Copilot session restarted.", color: TerminalANSI.magenta)
            } catch {
                writeTranscriptLine(prefix: "Copilot", text: error.localizedDescription, color: TerminalANSI.yellow)
            }
            renderPrompt()
        case .chat(let prompt):
            writeTranscriptLine(prefix: "You (Copilot)", text: prompt, color: TerminalANSI.cyan)
            if copilotBridge.isSessionActive {
                writeStatus("Sending to Copilot…")
                streamPrefixShown = false
                copilotBridge.onToken = { [weak self] token in
                    self?.uiQueue.async { guard let self else { return }
                        if !self.streamPrefixShown {
                            self.streamPrefixShown = true
                            if self.promptVisible { self.writeRaw("\r" + (self.richTTYEnabled ? TerminalANSI.clearLine : "")); self.promptVisible = false }
                            self.writeRaw(self.colorize("Copilot> ", color: TerminalANSI.magenta + TerminalANSI.bold))
                        }
                        self.writeRaw(ANSIText.strip(token))
                    }
                }
                copilotBridge.onComplete = { [weak self] fullText, _ in
                    self?.uiQueue.async { guard let self else { return }
                        self.writeRaw("\r\n"); self.writeStatus("Ready."); self.streamPrefixShown = false
                        if !fullText.isEmpty { DispatchQueue.main.async { self.speaker.speak(fullText) } }
                        self.renderPrompt()
                    }
                }
                do { try copilotBridge.sendChat(prompt) } catch {
                    writeTranscriptLine(prefix: "Copilot", text: error.localizedDescription, color: TerminalANSI.yellow); renderPrompt()
                }
            } else {
                writeStatus("Running Copilot one-shot…")
                copilotBridge.executeOneShot(mode: .chat, prompt: prompt) { [weak self] result in
                    self?.uiQueue.async { guard let self else { return }
                        switch result {
                        case .success(let t): self.writeTranscriptLine(prefix: "Copilot", text: t, color: TerminalANSI.magenta)
                            DispatchQueue.main.async { self.speaker.speak(t) }
                        case .failure(let e): self.writeTranscriptLine(prefix: "Copilot", text: e.localizedDescription, color: TerminalANSI.yellow)
                        }
                        self.writeStatus("Ready."); self.renderPrompt()
                    }
                }
            }
        case .suggest(let prompt):
            writeTranscriptLine(prefix: "You (Suggest)", text: prompt, color: TerminalANSI.cyan)
            copilotBridge.executeOneShot(mode: .suggest, prompt: prompt) { [weak self] result in
                self?.uiQueue.async { guard let self else { return }
                    switch result {
                    case .success(let t): self.writeTranscriptLine(prefix: "Copilot", text: t, color: TerminalANSI.magenta)
                        DispatchQueue.main.async { self.speaker.speak(t) }
                    case .failure(let e): self.writeTranscriptLine(prefix: "Copilot", text: e.localizedDescription, color: TerminalANSI.yellow)
                    }
                    self.writeStatus("Ready."); self.renderPrompt()
                }
            }
        case .explain(let prompt):
            writeTranscriptLine(prefix: "You (Explain)", text: prompt, color: TerminalANSI.cyan)
            copilotBridge.executeOneShot(mode: .explain, prompt: prompt) { [weak self] result in
                self?.uiQueue.async { guard let self else { return }
                    switch result {
                    case .success(let t): self.writeTranscriptLine(prefix: "Copilot", text: t, color: TerminalANSI.magenta)
                        DispatchQueue.main.async { self.speaker.speak(t) }
                    case .failure(let e): self.writeTranscriptLine(prefix: "Copilot", text: e.localizedDescription, color: TerminalANSI.yellow)
                    }
                    self.writeStatus("Ready."); self.renderPrompt()
                }
            }
        }
    }

        private func shutdown(exitCode: Int32) {
        guard !shuttingDown else { return }
        shuttingDown = true
        typingIndicator.stop()
        speechBatcher.cancel()
        streamingClient?.cancel()
        streamingClient = nil
        pendingFallbacks.values.forEach { $0.cancel() }
        pendingFallbacks.removeAll()
        agentResultsSubscriber.stop()
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

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private let listenButton = NSButton(title: "Press Enter to Talk", target: nil, action: nil)
    private let statusLabel = NSTextField(labelWithString: "Starting Brain Chat…")
    private let transcriptView = NSTextView()
    private let scrollView = NSScrollView()

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
    private let agentResultsSubscriber = AgentResultsSubscriber()
    private var bridgeAvailability: RedpandaBridge.Availability = .unavailable("Connecting…")
    private var pendingFallbacks: [String: DispatchWorkItem] = [:]
    private var pendingRequestOrder: [String] = []

    // LLM streaming state
    private var streamingClient: LLMStreamingClient?
    private var currentStreamID: String?           // ID of the in-flight stream request
    private var streamHeaderShown = false          // true once "Brain: " has been appended
    private var pendingTokens = ""                 // tokens buffered for the next 30-fps flush
    private var tokenFlushTimer: Timer?            // coalescing display timer (~30 fps)
    private let copilotBridge = GHCopilotBridge()
    private let speechBatcher = SpeechBatcher()
    private let typingIndicator = TypingIndicator()

    func applicationDidFinishLaunching(_ notification: Notification) {
        setupWindow()
        configureBridge()
        configureAgentSubscriber()
        requestPermissions()
        bridge.start()
        agentResultsSubscriber.start()

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
            self.speakAndLog("Brain Chat is ready. Press Enter to talk.", speaker: "Brain")
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        streamingClient?.cancel()
        streamingClient = nil
        tokenFlushTimer?.invalidate()
        agentResultsSubscriber.stop()
        bridge.stop()
        stopListeningSession(cancelRecognition: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    private func setupWindow() {
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 820, height: 560),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Brain Chat"
        window.minSize = NSSize(width: 720, height: 480)
        window.center()

        let contentView = NSView(frame: window.contentView?.bounds ?? .zero)
        contentView.autoresizingMask = [.width, .height]
        window.contentView = contentView

        let titleLabel = NSTextField(labelWithString: "Brain Chat")
        titleLabel.font = NSFont.systemFont(ofSize: 32, weight: .bold)
        titleLabel.frame = NSRect(x: 40, y: 490, width: 300, height: 40)
        titleLabel.setAccessibilityLabel("Brain Chat")
        contentView.addSubview(titleLabel)

        let instructionsLabel = NSTextField(wrappingLabelWithString: "Accessible voice chat for Joseph. Press Enter on the big button, speak your command, and Brain Chat will send it to Redpanda or answer locally if the broker is unavailable.")
        instructionsLabel.font = NSFont.systemFont(ofSize: 17)
        instructionsLabel.frame = NSRect(x: 40, y: 430, width: 740, height: 50)
        instructionsLabel.setAccessibilityLabel("Instructions")
        contentView.addSubview(instructionsLabel)

        listenButton.frame = NSRect(x: 40, y: 350, width: 740, height: 64)
        listenButton.bezelStyle = .regularSquare
        listenButton.font = NSFont.systemFont(ofSize: 28, weight: .bold)
        listenButton.target = self
        listenButton.action = #selector(toggleListening)
        listenButton.keyEquivalent = "\r"
        listenButton.keyEquivalentModifierMask = []
        listenButton.setAccessibilityLabel("Press Enter to talk")
        listenButton.setAccessibilityHelp("Starts and stops voice capture")
        contentView.addSubview(listenButton)

        statusLabel.frame = NSRect(x: 40, y: 312, width: 740, height: 24)
        statusLabel.font = NSFont.systemFont(ofSize: 16, weight: .medium)
        statusLabel.setAccessibilityLabel("Status")
        contentView.addSubview(statusLabel)

        let transcriptLabel = NSTextField(labelWithString: "Conversation")
        transcriptLabel.font = NSFont.systemFont(ofSize: 18, weight: .semibold)
        transcriptLabel.frame = NSRect(x: 40, y: 280, width: 200, height: 24)
        contentView.addSubview(transcriptLabel)

        scrollView.frame = NSRect(x: 40, y: 40, width: 740, height: 230)
        scrollView.hasVerticalScroller = true
        scrollView.borderType = .bezelBorder
        scrollView.autoresizingMask = [.width, .height]

        transcriptView.frame = scrollView.bounds
        transcriptView.isEditable = false
        transcriptView.isSelectable = true
        transcriptView.font = NSFont.monospacedSystemFont(ofSize: 15, weight: .regular)
        transcriptView.textContainerInset = NSSize(width: 12, height: 12)
        transcriptView.backgroundColor = NSColor.textBackgroundColor
        transcriptView.string = "Brain: Launching Brain Chat…\n"
        transcriptView.setAccessibilityLabel("Conversation transcript")
        scrollView.documentView = transcriptView
        contentView.addSubview(scrollView)

        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(listenButton)
        NSApp.activate(ignoringOtherApps: true)
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

    private func configureAgentSubscriber() {
        agentResultsSubscriber.onStatusChanged = { [weak self] (message: String) in
            guard let self else { return }
            self.updateStatus(message)
        }

        agentResultsSubscriber.onResult = { [weak self] (result: AgentResultsSubscriber.AgentResult) in
            guard let self else { return }
            let label = result.agentName.map { "\($0) (Agent)" } ?? "Agent"
            let taskSuffix = result.taskID.map { " [\($0)]" } ?? ""
            let cleanText = ANSIText.strip(result.text)
            self.appendTranscript(speaker: label + taskSuffix, text: cleanText)
            self.updateStatus("Agent result received from \(result.topic)")
            self.speaker.speak(cleanText)
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

    @objc private func toggleListening() {
        // If streaming, pressing the button cancels generation.
        if streamingClient?.isStreaming == true {
            speechBatcher.cancel()
            typingIndicator.stop()
            streamingClient?.cancel()
            streamingClient = nil
            currentStreamID = nil
            tokenFlushTimer?.invalidate()
            tokenFlushTimer = nil
            flushPendingTokens()
            appendRaw(" [stopped]\n\n")
            listenButton.title = "Press Enter to Talk"
            updateStatus("Generation stopped. Press Enter to talk.")
            return
        }

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
        }
    }

    private func processInput(_ text: String) {
        streamingClient?.cancel()
        streamingClient = nil
        tokenFlushTimer?.invalidate()
        tokenFlushTimer = nil
        pendingTokens = ""
        speechBatcher.cancel()
        typingIndicator.stop()

        appendTranscript(speaker: "You", text: text)
        let requestID = UUID().uuidString
        currentStreamID = requestID
        streamHeaderShown = false

        speechBatcher.onChunkReady = { [weak self] chunk in
            self?.speaker.speak(chunk)
        }
        typingIndicator.onFrame = { [weak self] dots in
            self?.updateStatus("Thinking\(dots)")
        }
        typingIndicator.start()
        listenButton.title = "Stop Generation (Enter)"

        let client = LLMStreamingClient()
        streamingClient = client

        client.stream(
            config: .default,
            userText: text,
            onToken: { [weak self] token in
                guard let self, self.currentStreamID == requestID else { return }
                self.handleIncomingToken(token)
            },
            onComplete: { [weak self] fullText, error in
                guard let self, self.currentStreamID == requestID else { return }
                self.handleStreamCompletion(fullText: fullText, error: error,
                                            originalText: text, requestID: requestID)
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

    // MARK: - Copilot Integration (GUI)

    private func handleCopilotCommand(_ command: GHCopilotBridge.CopilotCommand) {
        switch command {
        case .startSession:
            do { try copilotBridge.startSession(mode: .chat)
                speakAndLog("Copilot chat session started. Use /copilot followed by your message.", speaker: "Copilot")
            } catch { speakAndLog("Could not start Copilot: \(error.localizedDescription)", speaker: "Copilot") }
        case .stopSession:
            copilotBridge.endSession()
            speakAndLog("Copilot session ended.", speaker: "Copilot")
        case .restartSession:
            do { try copilotBridge.restartSession(); speakAndLog("Copilot session restarted.", speaker: "Copilot") }
            catch { speakAndLog("Could not restart Copilot: \(error.localizedDescription)", speaker: "Copilot") }
        case .chat(let prompt):
            appendTranscript(speaker: "You (Copilot)", text: prompt)
            if copilotBridge.isSessionActive {
                updateStatus("Sending to Copilot…")
                copilotBridge.onComplete = { [weak self] fullText, error in
                    guard let self else { return }
                    if let error { self.speakAndLog("Copilot error: \(error.localizedDescription)", speaker: "Copilot") }
                    else if !fullText.isEmpty { self.appendTranscript(speaker: "Copilot", text: fullText); self.speaker.speak(fullText) }
                    self.updateStatus("Ready. Press Enter to talk.")
                }
                do { try copilotBridge.sendChat(prompt) } catch { speakAndLog("Copilot error: \(error.localizedDescription)", speaker: "Copilot") }
            } else {
                updateStatus("Running Copilot one-shot…")
                copilotBridge.executeOneShot(mode: .chat, prompt: prompt) { [weak self] result in
                    guard let self else { return }
                    switch result {
                    case .success(let t): self.appendTranscript(speaker: "Copilot", text: t); self.speaker.speak(t)
                    case .failure(let e): self.speakAndLog("Copilot failed: \(e.localizedDescription)", speaker: "Copilot")
                    }; self.updateStatus("Ready. Press Enter to talk.")
                }
            }
        case .suggest(let prompt):
            appendTranscript(speaker: "You (Suggest)", text: prompt)
            copilotBridge.executeOneShot(mode: .suggest, prompt: prompt) { [weak self] result in
                guard let self else { return }
                switch result {
                case .success(let t): self.appendTranscript(speaker: "Copilot", text: t); self.speaker.speak(t)
                case .failure(let e): self.speakAndLog("Suggest failed: \(e.localizedDescription)", speaker: "Copilot")
                }; self.updateStatus("Ready. Press Enter to talk.")
            }
        case .explain(let prompt):
            appendTranscript(speaker: "You (Explain)", text: prompt)
            copilotBridge.executeOneShot(mode: .explain, prompt: prompt) { [weak self] result in
                guard let self else { return }
                switch result {
                case .success(let t): self.appendTranscript(speaker: "Copilot", text: t); self.speaker.speak(t)
                case .failure(let e): self.speakAndLog("Explain failed: \(e.localizedDescription)", speaker: "Copilot")
                }; self.updateStatus("Ready. Press Enter to talk.")
            }
        }
    }

        // MARK: - Streaming Display

    private func handleIncomingToken(_ token: String) {
        // Stop typing indicator on first real token. Defer "Brain: " label until now —
        // so nothing appears in the transcript if the stream fails immediately.
        if !streamHeaderShown {
            typingIndicator.stop()
            streamHeaderShown = true
            appendRaw("Brain: ")
        }
        pendingTokens += token
        speechBatcher.feed(token)
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
        typingIndicator.stop()
        speechBatcher.flush()
        streamingClient = nil
        listenButton.title = "Press Enter to Talk"

        if fullText.isEmpty {
            // Stream produced no content — fall through to Redpanda then local fallback.
            updateStatus("Local AI unavailable. Trying Redpanda…")
            useRedpandaPath(text: originalText, requestID: requestID)
        } else {
            // Finalize the streamed entry with a blank separator line and speak it.
            appendRaw("\n\n")
            transcriptView.scrollToEndOfDocument(nil)
            if let error {
                updateStatus("Stream ended: \(error.localizedDescription)")
            } else {
                updateStatus("Ready. Press Enter to talk.")
            }
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
    }

    private func appendTranscript(speaker: String, text: String) {
        let entry = "\(speaker): \(ANSIText.strip(text))\n\n"
        let attributed = NSAttributedString(string: entry)
        transcriptView.textStorage?.append(attributed)
        transcriptView.scrollToEndOfDocument(nil)
    }

    private func speakAndLog(_ text: String, speaker: String) {
        appendTranscript(speaker: speaker, text: text)
        self.speaker.speak(text)
    }
}

// MARK: - Agent Results Subscriber (Pandaproxy REST consumer)

final class AgentResultsSubscriber {
    struct AgentResult {
        let text: String
        let agentName: String?
        let taskID: String?
        let topic: String
    }

    var onResult: ((AgentResult) -> Void)?
    var onStatusChanged: ((String) -> Void)?

    private let pandaproxyBaseURL = "http://localhost:8082"
    private let groupID = "brainchat-group"
    private let instanceName = "brainchat"
    private let resultsTopic = "brain.agent.results"
    private let pollInterval: Double = 2.0

    private var pollTimer: DispatchSourceTimer?
    private var isConsumerCreated = false
    private var isSubscribed = false
    private let queue = DispatchQueue(label: "brainchat.agentresults")

    func start() {
        queue.async { self.createConsumer() }
    }

    func stop() {
        pollTimer?.cancel()
        pollTimer = nil
        deleteConsumer()
    }

    // MARK: - Consumer lifecycle

    private func createConsumer() {
        guard !isConsumerCreated else {
            subscribeToTopic()
            return
        }

        var request = URLRequest(url: URL(string: "\(pandaproxyBaseURL)/consumers/\(groupID)")!)
        request.httpMethod = "POST"
        request.setValue("application/vnd.kafka.v2+json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/vnd.kafka.v2+json", forHTTPHeaderField: "Accept")
        request.httpBody = try? JSONSerialization.data(withJSONObject: ["name": instanceName, "format": "json"])

        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            guard let self else { return }
            if let error = error {
                self.onStatusChanged?("Agent results: create failed (\(error.localizedDescription))")
                self.queue.asyncAfter(deadline: .now() + 5) { self.createConsumer() }
                return
            }
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            if status == 200 || status == 409 {
                self.isConsumerCreated = true
                self.subscribeToTopic()
            } else {
                let body = data.flatMap { String(data: $0, encoding: .utf8) } ?? ""
                self.onStatusChanged?("Agent results: create status \(status): \(body)")
                self.queue.asyncAfter(deadline: .now() + 5) { self.createConsumer() }
            }
        }.resume()
    }

    private func subscribeToTopic() {
        let urlStr = "\(pandaproxyBaseURL)/consumers/\(groupID)/instances/\(instanceName)/subscription"
        var request = URLRequest(url: URL(string: urlStr)!)
        request.httpMethod = "POST"
        request.setValue("application/vnd.kafka.v2+json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/vnd.kafka.v2+json", forHTTPHeaderField: "Accept")
        request.httpBody = try? JSONSerialization.data(withJSONObject: ["topics": [resultsTopic]])

        URLSession.shared.dataTask(with: request) { [weak self] _, response, error in
            guard let self else { return }
            if let error = error {
                self.onStatusChanged?("Agent results: subscribe failed (\(error.localizedDescription))")
                self.queue.asyncAfter(deadline: .now() + 5) { self.subscribeToTopic() }
                return
            }
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            if status == 200 || status == 204 {
                self.isSubscribed = true
                self.onStatusChanged?("Subscribed to \(self.resultsTopic)")
                self.startPolling()
            } else {
                self.queue.asyncAfter(deadline: .now() + 5) { self.subscribeToTopic() }
            }
        }.resume()
    }

    private func startPolling() {
        let timer = DispatchSource.makeTimerSource(queue: queue)
        timer.schedule(deadline: .now() + pollInterval, repeating: pollInterval)
        timer.setEventHandler { [weak self] in self?.poll() }
        timer.resume()
        pollTimer = timer
    }

    private func poll() {
        guard isSubscribed else { return }
        let urlStr = "\(pandaproxyBaseURL)/consumers/\(groupID)/instances/\(instanceName)/records?max_bytes=1048576"
        var request = URLRequest(url: URL(string: urlStr)!)
        request.setValue("application/vnd.kafka.json.v2+json", forHTTPHeaderField: "Accept")

        URLSession.shared.dataTask(with: request) { [weak self] data, _, error in
            guard let self else { return }
            if let error = error {
                let nsError = error as NSError
                let isConnRefused = nsError.domain == NSURLErrorDomain
                    && (nsError.code == NSURLErrorCannotConnectToHost
                        || nsError.code == NSURLErrorNetworkConnectionLost
                        || nsError.code == -1004)
                if !isConnRefused {
                    self.onStatusChanged?("Agent results poll error: \(error.localizedDescription)")
                }
                return
            }
            guard let data = data, !data.isEmpty,
                  let records = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
                return
            }
            for record in records {
                if let result = self.parseRecord(record) {
                    DispatchQueue.main.async { self.onResult?(result) }
                }
            }
        }.resume()
    }

    // MARK: - Parsing

    private func parseRecord(_ record: [String: Any]) -> AgentResult? {
        let topic = record["topic"] as? String ?? resultsTopic

        var valueDict: [String: Any]?
        if let dict = record["value"] as? [String: Any] {
            valueDict = dict
        } else if let str = record["value"] as? String,
                  let data = str.data(using: .utf8),
                  let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            valueDict = dict
        }

        let text: String
        if let dict = valueDict {
            text = extractText(from: dict)
        } else if let raw = record["value"] as? String, !raw.isEmpty {
            text = raw
        } else {
            return nil
        }

        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return nil }

        let agentName = valueDict.flatMap { (d: [String: Any]) -> String? in
            (d["agent"] as? String) ?? (d["agent_name"] as? String) ?? (d["source"] as? String)
        }
        let taskID = valueDict.flatMap { (d: [String: Any]) -> String? in
            (d["task_id"] as? String) ?? (d["request_id"] as? String) ?? (d["id"] as? String)
        }
        return AgentResult(text: text, agentName: agentName, taskID: taskID, topic: topic)
    }

    private func extractText(from dict: [String: Any]) -> String {
        for key in ["result", "output", "text", "response", "message", "content", "data"] {
            if let value = dict[key] as? String,
               !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                return value
            }
            if let nested = dict[key] as? [String: Any],
               let t = nested["text"] as? String, !t.isEmpty {
                return t
            }
        }
        if let data = try? JSONSerialization.data(withJSONObject: dict, options: [.prettyPrinted]),
           let str = String(data: data, encoding: .utf8) {
            return str
        }
        return ""
    }

    private func deleteConsumer() {
        guard isConsumerCreated else { return }
        isConsumerCreated = false
        isSubscribed = false
        let urlStr = "\(pandaproxyBaseURL)/consumers/\(groupID)/instances/\(instanceName)"
        var request = URLRequest(url: URL(string: urlStr)!)
        request.httpMethod = "DELETE"
        request.setValue("application/vnd.kafka.v2+json", forHTTPHeaderField: "Content-Type")
        URLSession.shared.dataTask(with: request).resume()
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
