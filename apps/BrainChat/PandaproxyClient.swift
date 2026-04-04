import Foundation

actor PandaproxyClient {
    struct ConsumerRecord<Value: Decodable & Sendable>: Sendable where Value: Sendable {
        let topic: String
        let partition: Int
        let offset: Int
        let key: String?
        let value: Value
    }

    private struct ConsumerInstance: Sendable {
        let groupID: String
        let baseURI: URL
        var topics: Set<String>
    }

    private let session: URLSession
    private var proxyBaseURL: URL
    private var consumers: [String: ConsumerInstance] = [:]
    private var defaultConsumerGroupID: String?

    init(baseURL: URL = URL(string: ProcessInfo.processInfo.environment["PANDAPROXY_URL"] ?? "http://localhost:8082")!, session: URLSession = .shared) {
        self.proxyBaseURL = baseURL
        self.session = session
    }

    func updateBaseURL(_ url: URL) {
        proxyBaseURL = url
        consumers.removeAll()
        defaultConsumerGroupID = nil
    }

    func publish<Event: Encodable>(topic: String, event: Event) async throws {
        var request = URLRequest(url: proxyBaseURL.appending(path: "topics/\(topic)"))
        request.httpMethod = "POST"
        request.setValue("application/vnd.kafka.v2+json", forHTTPHeaderField: "Accept")
        request.setValue("application/vnd.kafka.json.v2+json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: [
            "records": [
                ["value": try Self.jsonObject(for: event)]
            ]
        ])

        _ = try await perform(request)
    }

    func publish<Message: Encodable>(topic: String, message: Message) async throws {
        try await publish(topic: topic, event: message)
    }

    func ensureConsumer(groupID: String, topic: String) async throws {
        defaultConsumerGroupID = defaultConsumerGroupID ?? groupID

        if var consumer = consumers[groupID] {
            if !consumer.topics.contains(topic) {
                try await subscribe(to: topic, consumer: consumer)
                consumer.topics.insert(topic)
                consumers[groupID] = consumer
            }
            return
        }

        var request = URLRequest(url: proxyBaseURL.appending(path: "consumers/\(groupID)"))
        request.httpMethod = "POST"
        request.setValue("application/vnd.kafka.v2+json", forHTTPHeaderField: "Accept")
        request.setValue("application/vnd.kafka.v2+json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: [
            "name": "brainchat-\(UUID().uuidString.lowercased())",
            "format": "json",
            "auto.offset.reset": "latest",
            "consumer.request.timeout.ms": 30_000
        ])

        let data = try await perform(request)
        guard
            let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
            let baseURIString = json["base_uri"] as? String,
            let baseURI = URL(string: baseURIString)
        else {
            throw RedpandaBridgeError.unavailable("Pandaproxy did not return a consumer base URI.")
        }

        let consumer = ConsumerInstance(groupID: groupID, baseURI: baseURI, topics: [topic])
        consumers[groupID] = consumer
        try await subscribe(to: topic, consumer: consumer)
    }

    func poll<Value: Decodable & Sendable>(
        as type: Value.Type,
        timeoutMs: Int = 1_500,
        maxBytes: Int = 65_536
    ) async throws -> [ConsumerRecord<Value>] {
        guard let defaultConsumerGroupID else {
            throw RedpandaBridgeError.consumerNotReady
        }
        return try await poll(
            groupID: defaultConsumerGroupID,
            as: type,
            timeoutMs: timeoutMs,
            maxBytes: maxBytes
        )
    }

    func poll<Value: Decodable & Sendable>(
        groupID: String,
        as type: Value.Type,
        timeoutMs: Int = 1_500,
        maxBytes: Int = 65_536
    ) async throws -> [ConsumerRecord<Value>] {
        guard let consumer = consumers[groupID] else {
            throw RedpandaBridgeError.consumerNotReady
        }

        var components = URLComponents(url: consumer.baseURI.appending(path: "records"), resolvingAgainstBaseURL: false)
        components?.queryItems = [
            URLQueryItem(name: "timeout", value: String(timeoutMs)),
            URLQueryItem(name: "max_bytes", value: String(maxBytes))
        ]

        guard let url = components?.url else {
            throw RedpandaBridgeError.unavailable("Unable to build Pandaproxy polling URL.")
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/vnd.kafka.json.v2+json", forHTTPHeaderField: "Accept")

        let data = try await perform(request)
        return try Self.decodeRecords(from: data, as: type)
    }

    func closeConsumer() async {
        if let defaultConsumerGroupID {
            await closeConsumer(groupID: defaultConsumerGroupID)
        } else {
            await closeAllConsumers()
        }
    }

    func closeConsumer(groupID: String) async {
        guard let consumer = consumers[groupID] else { return }

        var request = URLRequest(url: consumer.baseURI)
        request.httpMethod = "DELETE"
        request.setValue("application/vnd.kafka.v2+json", forHTTPHeaderField: "Accept")

        _ = try? await perform(request, acceptedStatusCodes: [204, 404])
        consumers[groupID] = nil
        if defaultConsumerGroupID == groupID {
            defaultConsumerGroupID = consumers.keys.first
        }
    }

    func closeAllConsumers() async {
        let groupIDs = Array(consumers.keys)
        for groupID in groupIDs {
            await closeConsumer(groupID: groupID)
        }
        defaultConsumerGroupID = nil
    }

    private func subscribe(to topic: String, consumer: ConsumerInstance) async throws {
        var request = URLRequest(url: consumer.baseURI.appending(path: "subscription"))
        request.httpMethod = "POST"
        request.setValue("application/vnd.kafka.v2+json", forHTTPHeaderField: "Accept")
        request.setValue("application/vnd.kafka.v2+json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["topics": [topic]])
        _ = try await perform(request)
    }

    private func perform(
        _ request: URLRequest,
        acceptedStatusCodes: Set<Int> = Set(200...299)
    ) async throws -> Data {
        do {
            let (data, response) = try await session.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                throw RedpandaBridgeError.unavailable("Pandaproxy returned a non-HTTP response.")
            }

            guard acceptedStatusCodes.contains(httpResponse.statusCode) else {
                let body = String(data: data, encoding: .utf8) ?? "No error payload"
                throw RedpandaBridgeError.unavailable("HTTP \(httpResponse.statusCode): \(body)")
            }

            return data
        } catch let error as RedpandaBridgeError {
            throw error
        } catch {
            throw RedpandaBridgeError.unavailable(error.localizedDescription)
        }
    }

    static func makeEncoder() -> JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }

    static func makeDecoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }

    static func jsonObject<Value: Encodable>(for value: Value) throws -> Any {
        let data = try makeEncoder().encode(value)
        return try JSONSerialization.jsonObject(with: data)
    }

    static func decodeRecords<Value: Decodable & Sendable>(
        from data: Data,
        as type: Value.Type
    ) throws -> [ConsumerRecord<Value>] {
        let rawRecords = try JSONSerialization.jsonObject(with: data) as? [[String: Any]] ?? []
        let decoder = makeDecoder()

        return try rawRecords.compactMap { record in
            guard let topic = record["topic"] as? String else {
                return nil
            }

            let rawValue = record["value"] ?? NSNull()
            let valueData = try JSONSerialization.data(withJSONObject: rawValue)

            return ConsumerRecord(
                topic: topic,
                partition: record["partition"] as? Int ?? 0,
                offset: record["offset"] as? Int ?? 0,
                key: record["key"] as? String,
                value: try decoder.decode(Value.self, from: valueData)
            )
        }
    }
}

extension PandaproxyClient {
    private var llmResponseTopics: [String] {
        [
            BrainTopic.llmResponseFast.rawValue,
            BrainTopic.llmResponseDeep.rawValue,
            BrainTopic.llmResponseConsensus.rawValue
        ]
    }

    func publishFastRequest(_ prompt: String) async throws {
        let request = LLMRequest(
            prompt: prompt,
            priority: .instant,
            layers: [.fast, .deep]
        )
        try await publish(topic: BrainTopic.llmRequest.rawValue, message: request)
    }

    func subscribeToResponses(
        groupID: String = "brainchat-llm-\(UUID().uuidString.lowercased())"
    ) -> AsyncStream<LLMResponse> {
        let topics = llmResponseTopics

        return AsyncStream { continuation in
            let task = Task {
                do {
                    for topic in topics {
                        try await ensureConsumer(groupID: groupID, topic: topic)
                    }

                    while !Task.isCancelled {
                        let records = try await poll(groupID: groupID, as: LLMResponse.self)
                        if records.isEmpty {
                            continue
                        }

                        for record in records {
                            var response = record.value
                            response.apply(topic: record.topic)
                            continuation.yield(response)
                        }
                    }
                } catch {
                    continuation.finish()
                }

                await closeConsumer(groupID: groupID)
            }

            continuation.onTermination = { _ in
                task.cancel()
            }
        }
    }
}
