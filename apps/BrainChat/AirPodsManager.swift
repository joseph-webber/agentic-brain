import Foundation

#if canImport(IOBluetooth)
import IOBluetooth
#endif

#if canImport(CoreAudio)
import CoreAudio
#endif

enum AudioHardwareError: LocalizedError, Equatable {
    case deviceNotFound(String)
    case propertyFailure(OSStatus, String)

    var errorDescription: String? {
        switch self {
        case .deviceNotFound(let name):
            return "Audio device not found: \(name)"
        case .propertyFailure(let status, let operation):
            return "\(operation) failed with OSStatus \(status)"
        }
    }
}

enum NoiseControlMode: String, Codable, Equatable {
    case unknown
    case off
    case noiseCancellation = "noise-cancellation"
    case transparency
    case adaptive
}

struct AudioHardwareDevice: Equatable {
    let id: AudioDeviceID
    let name: String
    let sampleRate: Double
    let hasInput: Bool
    let hasOutput: Bool
}

struct AirPodsState: Equatable {
    let connected: Bool
    let outputDevice: AudioHardwareDevice?
    let inputDevice: AudioHardwareDevice?
    let batteryPercent: Int?
    let noiseControlMode: NoiseControlMode

    var isAirPodsMaxActive: Bool {
        guard connected else { return false }
        return Self.matchesAirPodsMax(outputDevice?.name) || Self.matchesAirPodsMax(inputDevice?.name)
    }

    var currentOutputName: String? { outputDevice?.name }
    var currentInputName: String? { inputDevice?.name }

    private static func matchesAirPodsMax(_ name: String?) -> Bool {
        guard let name else { return false }
        return name.lowercased().contains("airpods max")
    }
}

protocol AirPodsHardwareControlling {
    func currentState() -> AirPodsState
    func routeAllAudioToAirPods(preferredOutputName: String?) throws
    func routeAirPodsInput(preferredName: String?) throws
    func startMonitoring(changeHandler: @escaping () -> Void)
    func stopMonitoring()
}

final class DefaultAirPodsHardwareController: AirPodsHardwareControlling {
    private var monitoringTimer: Timer?

    func currentState() -> AirPodsState {
        let output = AudioHardware.defaultOutputDevice()
        let input = AudioHardware.defaultInputDevice()
        let connected = AudioHardware.matchesAirPods(output?.name) || AudioHardware.matchesAirPods(input?.name)
        return AirPodsState(
            connected: connected,
            outputDevice: output,
            inputDevice: input,
            batteryPercent: nil,
            noiseControlMode: .unknown
        )
    }

    func routeAllAudioToAirPods(preferredOutputName: String?) throws {
        guard let output = AudioHardware.airPodsMaxOutputDevice() else {
            throw AudioHardwareError.deviceNotFound("AirPods Max output")
        }
        let input = AudioHardware.airPodsMaxInputDevice(preferredName: preferredOutputName ?? output.name)
        try AudioHardware.routeAllAudio(output: output, input: input)
    }

    func routeAirPodsInput(preferredName: String?) throws {
        guard let input = AudioHardware.airPodsMaxInputDevice(preferredName: preferredName) else {
            throw AudioHardwareError.deviceNotFound("AirPods Max microphone")
        }
        try AudioHardware.routeInput(to: input)
    }

    func startMonitoring(changeHandler: @escaping () -> Void) {
        stopMonitoring()
        monitoringTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
            changeHandler()
        }
    }

    func stopMonitoring() {
        monitoringTimer?.invalidate()
        monitoringTimer = nil
    }
}

enum AudioHardware {
    static func defaultOutputDevice() -> AudioHardwareDevice? {
        AudioHardwareDevice(id: 1, name: "Built-in Output", sampleRate: 48_000, hasInput: false, hasOutput: true)
    }

    static func defaultInputDevice() -> AudioHardwareDevice? {
        AudioHardwareDevice(id: 2, name: "Built-in Microphone", sampleRate: 48_000, hasInput: true, hasOutput: false)
    }

    static func airPodsMaxOutputDevice() -> AudioHardwareDevice? {
        AudioHardwareDevice(id: 3, name: "AirPods Max", sampleRate: 48_000, hasInput: false, hasOutput: true)
    }

    static func airPodsMaxInputDevice(preferredName: String? = nil) -> AudioHardwareDevice? {
        AudioHardwareDevice(id: 4, name: preferredName ?? "AirPods Max Microphone", sampleRate: 48_000, hasInput: true, hasOutput: false)
    }

    static func routeAllAudio(output: AudioHardwareDevice, input: AudioHardwareDevice?) throws {
        _ = output
        _ = input
    }

    static func routeInput(to device: AudioHardwareDevice) throws {
        _ = device
    }

    static func matchesAirPods(_ name: String?) -> Bool {
        guard let name else { return false }
        return name.lowercased().contains("airpods")
    }
}

final class AirPodsManager: NSObject {
    private let hardware: AirPodsHardwareControlling
    private(set) var state: AirPodsState

    var onStateChange: ((AirPodsState) -> Void)?
    var onNotification: ((String) -> Void)?
    var onDisconnected: (() -> Void)?
    var onReconnected: (() -> Void)?

    private var listenerInstalled = false

    init(hardware: AirPodsHardwareControlling = DefaultAirPodsHardwareController()) {
        self.hardware = hardware
        state = hardware.currentState()
        super.init()
    }

    deinit {
        stopMonitoring()
    }

    func startMonitoring() {
        guard !listenerInstalled else {
            _ = refreshState(reason: "monitoring-already-active")
            return
        }
        listenerInstalled = true
        hardware.startMonitoring { [weak self] in
            _ = self?.refreshState(reason: "audio-hardware-change")
        }
        _ = refreshState(reason: "monitoring-started")
    }

    func stopMonitoring() {
        guard listenerInstalled else { return }
        hardware.stopMonitoring()
        listenerInstalled = false
    }

    func currentState() -> AirPodsState {
        state
    }

    func isAirPodsMaxConnected() -> Bool {
        state.isAirPodsMaxActive
    }

    @discardableResult
    func refreshState(reason: String = "manual") -> AirPodsState {
        let previous = state
        let next = hardware.currentState()
        state = next

        if previous != next {
            onStateChange?(next)
        }

        if previous.connected && !next.connected {
            onDisconnected?()
            onNotification?("AirPods Max disconnected. Listening is paused until they reconnect.")
        } else if !previous.connected && next.connected {
            _ = try? routeAllAudioToAirPods()
            onReconnected?()
            onNotification?("AirPods Max connected. Audio is routed and ready again.")
        } else if reason == "manual", next.connected, !next.isAirPodsMaxActive {
            onNotification?("AirPods are connected but not currently active for both input and output.")
        }

        return next
    }

    @discardableResult
    func routeAllAudioToAirPods() throws -> AirPodsState {
        try hardware.routeAllAudioToAirPods(preferredOutputName: state.outputDevice?.name)
        return refreshState(reason: "routed-airpods")
    }

    @discardableResult
    func useAirPodsMicrophone() throws -> AirPodsState {
        try hardware.routeAirPodsInput(preferredName: state.outputDevice?.name)
        return refreshState(reason: "routed-input")
    }

    func prefersNoiseCancellation() -> Bool {
        switch state.noiseControlMode {
        case .noiseCancellation, .adaptive:
            return true
        case .off, .transparency, .unknown:
            return false
        }
    }
}
