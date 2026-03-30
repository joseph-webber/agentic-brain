import Foundation

@MainActor
final class BridgeDaemon: ObservableObject {
    static let shared = BridgeDaemon()

    @Published private(set) var isRunning = false
    @Published private(set) var statusMessage = "Voice bridge stopped"

    private let server = VoiceBridgeServer.shared

    private init() {}

    func startIfNeeded() {
        guard !isRunning else { return }

        do {
            try server.start()
            isRunning = true
            statusMessage = "Voice bridge listening on localhost:8765"
        } catch {
            statusMessage = "Voice bridge failed to start: \(error.localizedDescription)"
        }
    }

    func stop() {
        guard isRunning else { return }
        server.stop()
        isRunning = false
        statusMessage = "Voice bridge stopped"
    }
}
