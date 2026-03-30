import Foundation

final class RedisClient {
    private let password: String?
    private let host: String
    private let port: Int

    init(
        password: String? = ProcessInfo.processInfo.environment["REDISCLI_AUTH"]
            ?? ProcessInfo.processInfo.environment["REDIS_PASSWORD"]
            ?? "BrainRedis2026",
        host: String = ProcessInfo.processInfo.environment["REDIS_HOST"] ?? "127.0.0.1",
        port: Int = Int(ProcessInfo.processInfo.environment["REDIS_PORT"] ?? "6379") ?? 6379
    ) {
        self.password = password
        self.host = host
        self.port = port
    }

    func isAvailable() -> Bool {
        run(arguments: ["PING"])?.status == 0
    }

    @discardableResult
    func set(_ key: String, value: String) -> Bool {
        run(arguments: ["SET", key, value])?.status == 0
    }

    @discardableResult
    func push(_ key: String, value: String) -> Bool {
        run(arguments: ["RPUSH", key, value])?.status == 0
    }

    @discardableResult
    func publish(_ channel: String, message: String) -> Bool {
        run(arguments: ["PUBLISH", channel, message])?.status == 0
    }

    @discardableResult
    func report(event: String, payload: [String: Any]) -> Bool {
        guard let data = try? JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]),
              let json = String(data: data, encoding: .utf8) else {
            return false
        }

        let time = ISO8601DateFormatter().string(from: Date())
        let eventKey = "voice:swift:events"
        let statusKey = "voice:swift:status"
        let channel = "voice:swift:pubsub"
        let wrapped = "{\"event\":\"\(escape(event))\",\"timestamp\":\"\(escape(time))\",\"payload\":\(json)}"

        let pushed = push(eventKey, value: wrapped)
        let stored = set(statusKey, value: wrapped)
        let published = publish(channel, message: wrapped)
        return pushed || stored || published
    }

    private func escape(_ value: String) -> String {
        value
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
    }

    private func baseArguments() -> [String] {
        var args = ["-h", host, "-p", String(port)]
        if let password, !password.isEmpty {
            args.append(contentsOf: ["-a", password])
        }
        return args
    }

    private func run(arguments: [String]) -> (status: Int32, output: String)? {
        let task = Process()
        let pipe = Pipe()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        task.arguments = ["redis-cli"] + baseArguments() + arguments
        task.standardOutput = pipe
        task.standardError = pipe

        do {
            try task.run()
            task.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let output = String(data: data, encoding: .utf8) ?? ""
            return (task.terminationStatus, output)
        } catch {
            return nil
        }
    }
}
