import Foundation
import Network
import CryptoKit

enum VoiceBridgeTarget: String, Codable, Sendable {
    case auto
    case copilot
    case claude
    case gpt
    case ollama
}

enum VoiceBridgeRoute: String, Codable, Sendable {
    case copilot
    case claude
    case gpt
    case ollama
}

struct VoiceBridgeRequest: Codable, Sendable {
    let id: UUID
    let message: String
    let history: [AIChatMessage]
    let systemPrompt: String
    let preferredTarget: VoiceBridgeTarget
    let yolo: Bool
    let claudeAPIKey: String
    let claudeModel: String
    let openAIAPIKey: String
    let openAIModel: String
    let ollamaEndpoint: String
    let ollamaModel: String

    init(
        id: UUID = UUID(),
        message: String,
        history: [AIChatMessage],
        systemPrompt: String,
        preferredTarget: VoiceBridgeTarget = .auto,
        yolo: Bool = false,
        claudeAPIKey: String,
        claudeModel: String,
        openAIAPIKey: String,
        openAIModel: String,
        ollamaEndpoint: String,
        ollamaModel: String
    ) {
        self.id = id
        self.message = message
        self.history = history
        self.systemPrompt = systemPrompt
        self.preferredTarget = preferredTarget
        self.yolo = yolo
        self.claudeAPIKey = claudeAPIKey
        self.claudeModel = claudeModel
        self.openAIAPIKey = openAIAPIKey
        self.openAIModel = openAIModel
        self.ollamaEndpoint = ollamaEndpoint
        self.ollamaModel = ollamaModel
    }
}

struct VoiceBridgeResponse: Codable, Sendable {
    let id: UUID
    let success: Bool
    let route: VoiceBridgeRoute
    let provider: String
    let reply: String
    let mode: String
    let duration: TimeInterval
    let error: String?
}

actor VoiceBridgeClient {
    static let shared = VoiceBridgeClient()

    func send(_ request: VoiceBridgeRequest, endpoint: String) async throws -> VoiceBridgeResponse {
        guard let url = URL(string: endpoint) else {
            throw AIServiceError.invalidURL(endpoint)
        }

        let session = URLSession(configuration: .ephemeral)
        let socket = session.webSocketTask(with: url)
        socket.resume()
        defer {
            socket.cancel(with: .goingAway, reason: nil)
            session.invalidateAndCancel()
        }

        let payload = try JSONEncoder().encode(request)
        try await socket.send(.data(payload))
        let message = try await socket.receive()

        let responseData: Data
        switch message {
        case .data(let data):
            responseData = data
        case .string(let text):
            responseData = Data(text.utf8)
        @unknown default:
            throw AIServiceError.invalidResponse
        }

        return try JSONDecoder().decode(VoiceBridgeResponse.self, from: responseData)
    }
}

final class VoiceBridgeServer: @unchecked Sendable {
    static let shared = VoiceBridgeServer()

    private let port: NWEndpoint.Port = 8765
    private let router = CopilotVoiceRouter.shared
    private let queue = DispatchQueue(label: "com.brain.voice-bridge.server")

    private var listener: NWListener?
    private var connections: [UUID: VoiceBridgeSocketConnection] = [:]

    private init() {}

    func start() throws {
        guard listener == nil else { return }

        let parameters = NWParameters.tcp
        parameters.allowLocalEndpointReuse = true

        let listener = try NWListener(using: parameters, on: port)
        listener.stateUpdateHandler = { state in
            if case .failed(let error) = state {
                print("Voice bridge listener failed: \(error)")
            }
        }
        listener.newConnectionHandler = { [weak self] connection in
            self?.accept(connection: connection)
        }
        listener.start(queue: queue)
        self.listener = listener
    }

    func stop() {
        listener?.cancel()
        listener = nil
        connections.values.forEach { $0.stop() }
        connections.removeAll()
    }

    private func accept(connection: NWConnection) {
        let socket = VoiceBridgeSocketConnection(connection: connection, router: router)
        socket.onClose = { [weak self] id in
            self?.queue.async {
                self?.connections.removeValue(forKey: id)
            }
        }
        connections[socket.id] = socket
        socket.start(on: queue)
    }
}

private final class VoiceBridgeSocketConnection: @unchecked Sendable {
    let id = UUID()
    var onClose: ((UUID) -> Void)?

    private let connection: NWConnection
    private let router: CopilotVoiceRouter
    private var buffer = Data()
    private var handshakeComplete = false
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    init(connection: NWConnection, router: CopilotVoiceRouter) {
        self.connection = connection
        self.router = router
    }

    func start(on queue: DispatchQueue) {
        connection.stateUpdateHandler = { [weak self] state in
            guard let self else { return }
            switch state {
            case .ready:
                self.receiveNext()
            case .failed, .cancelled:
                self.onClose?(self.id)
            default:
                break
            }
        }
        connection.start(queue: queue)
    }

    func stop() {
        connection.cancel()
        onClose?(id)
    }

    private func receiveNext() {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 65_536) { [weak self] data, _, isComplete, error in
            guard let self else { return }
            if let data, !data.isEmpty {
                self.buffer.append(data)
                self.processBuffer()
            }

            if isComplete || error != nil {
                self.stop()
                return
            }

            self.receiveNext()
        }
    }

    private func processBuffer() {
        if !handshakeComplete {
            performHandshakeIfPossible()
        }

        guard handshakeComplete else { return }
        while processFrameIfPossible() {}
    }

    private func performHandshakeIfPossible() {
        guard let range = buffer.range(of: Data("\r\n\r\n".utf8)) else { return }
        let headerData = buffer.subdata(in: 0..<range.upperBound)
        buffer.removeSubrange(0..<range.upperBound)

        guard
            let request = String(data: headerData, encoding: .utf8),
            let key = websocketKey(from: request)
        else {
            stop()
            return
        }

        let acceptKey = websocketAccept(for: key)
        let response = "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: \(acceptKey)\r\n\r\n"
        sendRaw(Data(response.utf8))
        handshakeComplete = true
    }

    private func websocketKey(from request: String) -> String? {
        request
            .components(separatedBy: "\r\n")
            .first(where: { $0.lowercased().hasPrefix("sec-websocket-key:") })?
            .split(separator: ":", maxSplits: 1)
            .last?
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func websocketAccept(for key: String) -> String {
        let magic = key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        let digest = Insecure.SHA1.hash(data: Data(magic.utf8))
        return Data(digest).base64EncodedString()
    }

    private func processFrameIfPossible() -> Bool {
        guard buffer.count >= 2 else { return false }

        let bytes = [UInt8](buffer)
        let opcode = bytes[0] & 0x0F
        let masked = (bytes[1] & 0x80) != 0
        var payloadLength = Int(bytes[1] & 0x7F)
        var offset = 2

        if payloadLength == 126 {
            guard bytes.count >= offset + 2 else { return false }
            payloadLength = Int(bytes[offset]) << 8 | Int(bytes[offset + 1])
            offset += 2
        } else if payloadLength == 127 {
            guard bytes.count >= offset + 8 else { return false }
            payloadLength = bytes[offset..<offset + 8].reduce(0) { ($0 << 8) | Int($1) }
            offset += 8
        }

        var maskKey: [UInt8] = []
        if masked {
            guard bytes.count >= offset + 4 else { return false }
            maskKey = Array(bytes[offset..<offset + 4])
            offset += 4
        }

        guard bytes.count >= offset + payloadLength else { return false }

        var payload = Array(bytes[offset..<offset + payloadLength])
        buffer.removeSubrange(0..<offset + payloadLength)

        if masked {
            for index in payload.indices {
                payload[index] ^= maskKey[index % 4]
            }
        }

        switch opcode {
        case 0x1:
            guard let text = String(bytes: payload, encoding: .utf8) else { return true }
            Task {
                await self.handleTextFrame(text)
            }
        case 0x8:
            sendFrame(opcode: 0x8, payload: Data())
            stop()
        case 0x9:
            sendFrame(opcode: 0xA, payload: Data(payload))
        default:
            break
        }

        return true
    }

    private func handleTextFrame(_ text: String) async {
        let response: VoiceBridgeResponse

        do {
            let request = try decoder.decode(VoiceBridgeRequest.self, from: Data(text.utf8))
            response = await router.handle(request)
        } catch {
            response = VoiceBridgeResponse(
                id: UUID(),
                success: false,
                route: .ollama,
                provider: "Voice Bridge",
                reply: "The voice bridge could not read the incoming request.",
                mode: "standard",
                duration: 0,
                error: error.localizedDescription
            )
        }

        let data = (try? encoder.encode(response)) ?? Data("{\"reply\":\"encoding failure\"}".utf8)
        sendFrame(opcode: 0x1, payload: data)
    }

    private func sendRaw(_ data: Data) {
        connection.send(content: data, completion: .contentProcessed { _ in })
    }

    private func sendFrame(opcode: UInt8, payload: Data) {
        var frame = Data()
        frame.append(0x80 | opcode)

        if payload.count < 126 {
            frame.append(UInt8(payload.count))
        } else if payload.count < 65_536 {
            frame.append(126)
            frame.append(UInt8((payload.count >> 8) & 0xFF))
            frame.append(UInt8(payload.count & 0xFF))
        } else {
            frame.append(127)
            for shift in stride(from: 56, through: 0, by: -8) {
                frame.append(UInt8((UInt64(payload.count) >> UInt64(shift)) & 0xFF))
            }
        }

        frame.append(payload)
        sendRaw(frame)
    }
}
