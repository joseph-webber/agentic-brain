import Foundation

actor PandaproxyClient {
    struct ConsumerRecord<Value: Decodable & Sendable>: Sendable {
        let topic: String
        let partition: Int
        let offset: Int
        let key: String?
        let value: Value
    }

    private struct ConsumerInstance: Sendable {
        let groupID: String
        let baseURI: URL
    }

    private let session: URLSession
    private var proxyBaseURL: URL
    private var consumer: ConsumerInstance?

    init(baseURL: URL = URL(string: "http://localhost:8082")!, session: URLSession = .shared) {
        self.proxyBaseURL = baseURL
        self.session = session
    }

    func updateBaseURL(_ url: URL) {
        proxyBaseURL = url
        consumer = nil
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

    func ensureConsumer(groupID: String, topic: String) async throws {
        if let consumer, consumer.groupID == groupID {
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

        consumer = ConsumerInstance(groupID: groupID, baseURI: baseURI)
        try await subscribe(to: topic)
    }

    func poll<Value: Decodable & Sendable>(
        as type: Value.Type,
        timeoutMs: Int = 1_500,
        maxBytes: Int = 65_536
    ) async throws -> [ConsumerRecord<Value>] {
        guard let consumer else {
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
        guard let consumer else { return }

        var request = URLRequest(url: consumer.baseURI)
        request.httpMethod = "DELETE"
        request.setValue("application/vnd.kafka.v2+json", forHTTPHeaderField: "Accept")

        _ = try? await perform(request, acceptedStatusCodes: [204, 404])
        self.consumer = nil
    }

    private func subscribe(to topic: String) async throws {
        guard let consumer else {
            throw RedpandaBridgeError.consumerNotReady
        }

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
