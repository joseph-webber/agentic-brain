import Foundation

private let terminalBridgeDefaultURL = URL(string: "ws://localhost:8765")!

@MainActor
public protocol TerminalBridgeDelegate: AnyObject {
    func terminalBridgeDidConnect(_ bridge: TerminalBridge)
    func terminalBridgeDidDisconnect(_ bridge: TerminalBridge, error: Error?)
    func terminalBridge(_ bridge: TerminalBridge, didReceiveOutput output: String)
    func terminalBridge(_ bridge: TerminalBridge, didReceiveError message: String)
}

public extension TerminalBridgeDelegate {
    func terminalBridgeDidConnect(_ bridge: TerminalBridge) {}
    func terminalBridgeDidDisconnect(_ bridge: TerminalBridge, error: Error?) {}
    func terminalBridge(_ bridge: TerminalBridge, didReceiveError message: String) {}
}

public enum TerminalBridgeError: LocalizedError {
    case invalidURL
    case connectionTimedOut
    case notConnected
    case disconnected(reason: String?)
    case serverError(String)
    case unexpectedMessage
    case invalidPayload

    public var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "The terminal bridge URL is invalid."
        case .connectionTimedOut:
            return "The terminal bridge connection timed out."
        case .notConnected:
            return "The terminal bridge is not connected."
        case .disconnected(let reason):
            if let reason, !reason.isEmpty {
                return "The terminal bridge disconnected: \(reason)"
            }
            return "The terminal bridge disconnected."
        case .serverError(let message):
            return "Terminal server error: \(message)"
        case .unexpectedMessage:
            return "The terminal bridge received an unexpected message."
        case .invalidPayload:
            return "The terminal bridge received an invalid payload."
        }
    }
}

@MainActor
public final class TerminalBridge: NSObject {
    public weak var delegate: TerminalBridgeDelegate?

    public private(set) var isConnected = false

    private let url: URL
    private let reconnectBaseDelay: TimeInterval
    private let maxReconnectDelay: TimeInterval
    private let connectionTimeout: TimeInterval
    private lazy var session: URLSession = {
        let configuration = URLSessionConfiguration.default
        configuration.waitsForConnectivity = false
        configuration.timeoutIntervalForRequest = connectionTimeout
        configuration.timeoutIntervalForResource = connectionTimeout
        return URLSession(configuration: configuration, delegate: self, delegateQueue: nil)
    }()

    private var webSocketTask: URLSessionWebSocketTask?
    private var receiveTask: Task<Void, Never>?
    private var reconnectTask: Task<Void, Never>?
    private var connectTask: Task<Void, Error>?
    private var connectContinuation: CheckedContinuation<Void, Error>?
    private var manuallyDisconnected = false
    private var disconnectHandled = false
    private var reconnectAttempt = 0

    public init(
        url: URL = terminalBridgeDefaultURL,
        reconnectBaseDelay: TimeInterval = 1,
        maxReconnectDelay: TimeInterval = 30,
        connectionTimeout: TimeInterval = 10
    ) {
        self.url = url
        self.reconnectBaseDelay = reconnectBaseDelay
        self.maxReconnectDelay = maxReconnectDelay
        self.connectionTimeout = connectionTimeout
        super.init()
    }

    public func connect() async throws {
        guard url.scheme?.hasPrefix("ws") == true else {
            throw TerminalBridgeError.invalidURL
        }

        if isConnected {
            return
        }

        if let connectTask {
            return try await connectTask.value
        }

        manuallyDisconnected = false
        reconnectTask?.cancel()
        reconnectTask = nil

        let task = Task<Void, Error> { @MainActor [weak self] in
            guard let self else { return }
            try await self.openSocket()
        }

        connectTask = task

        do {
            try await task.value
            connectTask = nil
        } catch {
            connectTask = nil
            throw error
        }
    }

    public func sendInput(_ text: String) async throws {
        try await ensureConnected()
        try await send(TerminalOutgoingMessage(type: "input", data: text))
    }

    public func resize(cols: Int, rows: Int) async throws {
        try await ensureConnected()
        try await send(TerminalOutgoingMessage(type: "resize", rows: rows, cols: cols))
    }

    public func disconnect() {
        manuallyDisconnected = true
        reconnectTask?.cancel()
        reconnectTask = nil
        connectTask?.cancel()
        connectTask = nil
        receiveTask?.cancel()
        receiveTask = nil
        resolveConnectContinuation(with: .failure(TerminalBridgeError.disconnected(reason: "Disconnected by client.")))
        disconnectHandled = true
        isConnected = false

        if let webSocketTask {
            webSocketTask.cancel(with: .normalClosure, reason: nil)
            self.webSocketTask = nil
        }

        delegate?.terminalBridgeDidDisconnect(self, error: nil)
    }

    private func ensureConnected() async throws {
        if isConnected {
            return
        }

        try await connect()

        guard isConnected else {
            throw TerminalBridgeError.notConnected
        }
    }

    private func openSocket() async throws {
        receiveTask?.cancel()
        receiveTask = nil

        if let webSocketTask {
            webSocketTask.cancel(with: .goingAway, reason: nil)
            self.webSocketTask = nil
        }

        disconnectHandled = false

        let task = session.webSocketTask(with: url)
        webSocketTask = task
        task.resume()

        try await waitForOpen()
    }

    private func waitForOpen() async throws {
        try await withThrowingTaskGroup(of: Void.self) { group in
            group.addTask { @MainActor [weak self] in
                guard let self else { return }
                try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
                    self.connectContinuation = continuation
                }
            }

            group.addTask { [connectionTimeout] in
                let nanoseconds = UInt64(connectionTimeout * 1_000_000_000)
                try await Task.sleep(nanoseconds: nanoseconds)
                throw TerminalBridgeError.connectionTimedOut
            }

            guard let result: Void = try await group.next() else {
                throw TerminalBridgeError.connectionTimedOut
            }
            group.cancelAll()
            _ = result
        }
    }

    private func send(_ message: TerminalOutgoingMessage) async throws {
        guard let webSocketTask else {
            throw TerminalBridgeError.notConnected
        }

        let payload = try JSONEncoder().encode(message)
        guard let stringPayload = String(data: payload, encoding: .utf8) else {
            throw TerminalBridgeError.invalidPayload
        }

        do {
            try await webSocketTask.send(.string(stringPayload))
        } catch {
            await handleUnexpectedDisconnect(error)
            throw error
        }
    }

    private func startReceiveLoop() {
        receiveTask?.cancel()

        receiveTask = Task { [weak self] in
            guard let self else { return }

            while !Task.isCancelled {
                do {
                    let message = try await self.receiveMessage()
                    try await self.handleIncomingMessage(message)
                } catch is CancellationError {
                    break
                } catch {
                    await self.handleUnexpectedDisconnect(error)
                    break
                }
            }
        }
    }

    private func receiveMessage() async throws -> URLSessionWebSocketTask.Message {
        guard let webSocketTask else {
            throw TerminalBridgeError.notConnected
        }

        return try await webSocketTask.receive()
    }

    private func handleIncomingMessage(_ message: URLSessionWebSocketTask.Message) async throws {
        let payload: Data

        switch message {
        case .string(let string):
            guard let data = string.data(using: .utf8) else {
                throw TerminalBridgeError.invalidPayload
            }
            payload = data
        case .data(let data):
            payload = data
        @unknown default:
            throw TerminalBridgeError.unexpectedMessage
        }

        let decoded = try JSONDecoder().decode(TerminalIncomingMessage.self, from: payload)

        switch decoded.type {
        case "output":
            guard let output = decoded.data else {
                throw TerminalBridgeError.invalidPayload
            }
            delegate?.terminalBridge(self, didReceiveOutput: output)

        case "error":
            let message = decoded.data ?? "Unknown terminal server error."
            delegate?.terminalBridge(self, didReceiveError: message)

        default:
            throw TerminalBridgeError.unexpectedMessage
        }
    }

    private func resolveConnectContinuation(with result: Result<Void, Error>) {
        guard let continuation = connectContinuation else { return }
        connectContinuation = nil
        continuation.resume(with: result)
    }

    private func handleSocketOpened() {
        isConnected = true
        reconnectAttempt = 0
        disconnectHandled = false
        resolveConnectContinuation(with: .success(()))
        delegate?.terminalBridgeDidConnect(self)
        startReceiveLoop()
    }

    private func handleSocketClosed(reason: Error?) async {
        guard !disconnectHandled else { return }
        disconnectHandled = true
        isConnected = false
        receiveTask?.cancel()
        receiveTask = nil
        webSocketTask = nil

        if let reason {
            resolveConnectContinuation(with: .failure(reason))
        } else {
            resolveConnectContinuation(with: .failure(TerminalBridgeError.disconnected(reason: nil)))
        }

        delegate?.terminalBridgeDidDisconnect(self, error: reason)

        guard !manuallyDisconnected else { return }
        scheduleReconnect()
    }

    private func handleUnexpectedDisconnect(_ error: Error) async {
        await handleSocketClosed(reason: error)
    }

    private func scheduleReconnect() {
        guard reconnectTask == nil, !manuallyDisconnected else { return }

        reconnectAttempt += 1
        let exponentialDelay = reconnectBaseDelay * pow(2, Double(max(0, reconnectAttempt - 1)))
        let delay = min(exponentialDelay, maxReconnectDelay)

        reconnectTask = Task { @MainActor [weak self] in
            guard let self else { return }

            do {
                let nanoseconds = UInt64(delay * 1_000_000_000)
                try await Task.sleep(nanoseconds: nanoseconds)
                self.reconnectTask = nil
                guard !self.manuallyDisconnected else { return }
                try await self.connect()
            } catch is CancellationError {
                self.reconnectTask = nil
            } catch {
                self.reconnectTask = nil
                await self.handleUnexpectedDisconnect(error)
            }
        }
    }
}

extension TerminalBridge: URLSessionWebSocketDelegate, URLSessionTaskDelegate {
    nonisolated public func urlSession(
        _ session: URLSession,
        webSocketTask: URLSessionWebSocketTask,
        didOpenWithProtocol protocol: String?
    ) {
        Task { @MainActor [weak self] in
            self?.handleSocketOpened()
        }
    }

    nonisolated public func urlSession(
        _ session: URLSession,
        webSocketTask: URLSessionWebSocketTask,
        didCloseWith closeCode: URLSessionWebSocketTask.CloseCode,
        reason: Data?
    ) {
        let reasonText = reason.flatMap { String(data: $0, encoding: .utf8) }
        let error = TerminalBridgeError.disconnected(reason: reasonText ?? closeCode.rawValue.description)

        Task { @MainActor [weak self] in
            await self?.handleSocketClosed(reason: error)
        }
    }

    nonisolated public func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        didCompleteWithError error: Error?
    ) {
        guard let error else { return }

        Task { @MainActor [weak self] in
            await self?.handleUnexpectedDisconnect(error)
        }
    }
}

private struct TerminalIncomingMessage: Decodable {
    let type: String
    let data: String?
    let rows: Int?
    let cols: Int?
}

private struct TerminalOutgoingMessage: Encodable {
    let type: String
    let data: String?
    let rows: Int?
    let cols: Int?

    init(type: String, data: String? = nil, rows: Int? = nil, cols: Int? = nil) {
        self.type = type
        self.data = data
        self.rows = rows
        self.cols = cols
    }
}
