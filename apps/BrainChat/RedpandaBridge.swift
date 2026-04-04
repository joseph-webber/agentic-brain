import Foundation

actor RedpandaBridge {
    private let inputTopic = "brain.voice.input"
    private let responseTopic = "brain.voice.response"
    private let consumerGroupID = "brainchat-swift"

    private let client: PandaproxyClient
    private var listenerTask: Task<Void, Never>?
    private var bufferedResponses: [VoiceResponseEvent] = []
    private var waiters: [(id: UUID, continuation: CheckedContinuation<VoiceResponseEvent, Error>)] = []
    private var responseHandler: (@Sendable (VoiceResponseEvent) -> Void)?

    init(client: PandaproxyClient = PandaproxyClient()) {
        self.client = client
    }

    func configure(baseURL: URL) async {
        await stop()
        await client.updateBaseURL(baseURL)
    }

    func startListening(onResponse: (@Sendable (VoiceResponseEvent) -> Void)? = nil) async throws {
        responseHandler = onResponse
        try await ensureListener()
    }

    func stop() async {
        listenerTask?.cancel()
        listenerTask = nil

        let pendingWaiters = waiters
        waiters.removeAll()
        bufferedResponses.removeAll()
        pendingWaiters.forEach { $0.continuation.resume(throwing: RedpandaBridgeError.cancelled) }

        await client.closeConsumer()
    }

    func publish(_ event: VoiceInputEvent) async throws {
        try await ensureListener()
        try await client.publish(topic: inputTopic, event: event)
    }

    func publishFastRequest(_ prompt: String) async throws {
        try await client.publishFastRequest(prompt)
    }

    func subscribeToLLMResponses() async -> AsyncStream<LLMResponse> {
        await client.subscribeToResponses()
    }

    func requestResponse(
        text: String,
        targetLLM: String,
        yoloMode: Bool,
        timeout: TimeInterval,
        source: String = "brainchat"
    ) async throws -> VoiceResponseEvent {
        let event = VoiceInputEvent(
            text: text,
            source: source,
            targetLLM: targetLLM,
            yoloMode: yoloMode
        )
        return try await requestResponse(for: event, timeout: timeout)
    }

    func requestResponse(
        for event: VoiceInputEvent,
        timeout: TimeInterval
    ) async throws -> VoiceResponseEvent {
        try await ensureListener()

        let waiterID = UUID()
        let responseTask = Task<VoiceResponseEvent, Error> {
            try await self.nextResponse(waiterID: waiterID)
        }

        do {
            try await client.publish(topic: inputTopic, event: event)
            let response = try await Self.withTimeout(seconds: timeout) {
                try await responseTask.value
            }

            guard response.success else {
                throw RedpandaBridgeError.responseFailed(provider: response.provider, message: response.text)
            }

            return response
        } catch {
            responseTask.cancel()
            failWaiter(id: waiterID, error: error)
            throw error
        }
    }

    private func ensureListener() async throws {
        if let listenerTask, !listenerTask.isCancelled {
            return
        }

        try await client.ensureConsumer(groupID: consumerGroupID, topic: responseTopic)
        listenerTask = Task { [weak self] in
            await self?.runListenerLoop()
        }
    }

    private func runListenerLoop() async {
        while !Task.isCancelled {
            do {
                let records = try await client.poll(as: VoiceResponseEvent.self)
                if records.isEmpty {
                    continue
                }

                for record in records {
                    await deliver(record.value)
                }
            } catch {
                if Task.isCancelled {
                    break
                }

                let bridgeError = error as? RedpandaBridgeError
                    ?? RedpandaBridgeError.unavailable(error.localizedDescription)
                let pendingWaiters = waiters
                waiters.removeAll()
                listenerTask = nil
                pendingWaiters.forEach { $0.continuation.resume(throwing: bridgeError) }
                break
            }
        }
    }

    private func nextResponse(waiterID: UUID) async throws -> VoiceResponseEvent {
        if !bufferedResponses.isEmpty {
            return bufferedResponses.removeFirst()
        }

        return try await withCheckedThrowingContinuation { continuation in
            waiters.append((id: waiterID, continuation: continuation))
        }
    }

    private func deliver(_ response: VoiceResponseEvent) async {
        if let responseHandler {
            responseHandler(response)
        }

        if !waiters.isEmpty {
            let waiter = waiters.removeFirst()
            waiter.continuation.resume(returning: response)
        } else {
            bufferedResponses.append(response)
        }
    }

    private func failWaiter(id: UUID, error: Error) {
        guard let index = waiters.firstIndex(where: { $0.id == id }) else { return }
        let waiter = waiters.remove(at: index)
        waiter.continuation.resume(throwing: error)
    }

    nonisolated private static func withTimeout<T: Sendable>(
        seconds: TimeInterval,
        operation: @escaping @Sendable () async throws -> T
    ) async throws -> T {
        try await withThrowingTaskGroup(of: T.self) { group in
            group.addTask {
                try await operation()
            }

            group.addTask {
                let timeout = UInt64(max(seconds, 0.1) * 1_000_000_000)
                try await Task.sleep(nanoseconds: timeout)
                throw RedpandaBridgeError.requestTimedOut(seconds)
            }

            guard let value = try await group.next() else {
                throw RedpandaBridgeError.unavailable("No bridge task was scheduled.")
            }

            group.cancelAll()
            return value
        }
    }
}
