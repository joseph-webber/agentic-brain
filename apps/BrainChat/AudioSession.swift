import Foundation
import AVFoundation

enum BrainAudioSessionState: String {
    case idle
    case listening
    case pausedForDisconnect
}

struct AudioSessionStatus {
    let state: BrainAudioSessionState
    let sampleRate: Double
    let inputName: String?
    let outputName: String?
    let prefersNoiseCancellation: Bool
    let bufferDuration: TimeInterval
}

final class BrainAudioSession {
    let audioEngine = AVAudioEngine()

    private let playbackNode = AVAudioPlayerNode()
    private let preferredSampleRate = 48_000.0
    private let preferredBufferDuration = 0.005

    private var tapInstalled = false
    private var inputTapHandler: ((AVAudioPCMBuffer, AVAudioTime) -> Void)?

    private(set) var state: BrainAudioSessionState = .idle

    var onNotification: ((String) -> Void)?

    init() {
        audioEngine.attach(playbackNode)

        if let playbackFormat = AVAudioFormat(
            commonFormat: .pcmFormatFloat32,
            sampleRate: preferredSampleRate,
            channels: 1,
            interleaved: false
        ) {
            audioEngine.connect(playbackNode, to: audioEngine.mainMixerNode, format: playbackFormat)
        } else {
            audioEngine.connect(playbackNode, to: audioEngine.mainMixerNode, format: nil)
        }
    }

    func configure(using manager: AirPodsManager? = nil) throws {
        #if canImport(UIKit) || targetEnvironment(macCatalyst)
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .voiceChat, options: [.allowBluetooth, .allowBluetoothA2DP, .duckOthers])
        try session.setPreferredSampleRate(preferredSampleRate)
        try session.setPreferredIOBufferDuration(preferredBufferDuration)
        try session.setPreferredInputNumberOfChannels(1)
        try session.setPreferredOutputNumberOfChannels(2)
        try session.setActive(true, options: [])
        #endif

        if let manager, manager.isAirPodsMaxConnected() {
            try manager.routeAllAudioToAirPods()
        }

        audioEngine.prepare()
    }

    func bind(to manager: AirPodsManager) {
        manager.onDisconnected = { [weak self] in
            self?.pauseListeningForDisconnect()
        }

        manager.onReconnected = { [weak self, weak manager] in
            guard let self, let manager else { return }
            do {
                try self.resumeListeningIfPossible(using: manager)
            } catch {
                self.onNotification?("AirPods Max reconnected, but resuming audio failed: \(error.localizedDescription)")
            }
        }

        manager.onNotification = { [weak self] message in
            self?.onNotification?(message)
        }
    }

    func startListening(bufferHandler: @escaping (AVAudioPCMBuffer, AVAudioTime) -> Void) throws {
        inputTapHandler = bufferHandler
        try installTapIfNeeded()

        if !audioEngine.isRunning {
            try audioEngine.start()
        }

        state = .listening
    }

    func pauseListeningForDisconnect() {
        guard state == .listening else { return }
        audioEngine.pause()
        state = .pausedForDisconnect
        onNotification?("AirPods Max disconnected. Pausing microphone capture.")
    }

    func resumeListeningIfPossible(using manager: AirPodsManager) throws {
        guard manager.isAirPodsMaxConnected() else { return }

        try configure(using: manager)
        try installTapIfNeeded()

        if !audioEngine.isRunning {
            try audioEngine.start()
        }

        state = .listening
        onNotification?("AirPods Max reconnected. Resuming microphone capture.")
    }

    func stopListening() {
        if tapInstalled {
            audioEngine.inputNode.removeTap(onBus: 0)
            tapInstalled = false
        }

        if audioEngine.isRunning {
            audioEngine.stop()
        }

        state = .idle
    }

    func play(buffer: AVAudioPCMBuffer, at time: AVAudioTime? = nil, completion: (() -> Void)? = nil) throws {
        if !audioEngine.isRunning {
            try audioEngine.start()
        }

        playbackNode.scheduleBuffer(buffer, at: time, options: [], completionHandler: completion)
        if !playbackNode.isPlaying {
            playbackNode.play()
        }
    }

    func status(using manager: AirPodsManager? = nil) -> AudioSessionStatus {
        let airPodsState = manager?.currentState()
        return AudioSessionStatus(
            state: state,
            sampleRate: audioEngine.inputNode.inputFormat(forBus: 0).sampleRate,
            inputName: airPodsState?.currentInputName ?? AudioHardware.defaultInputDevice()?.name,
            outputName: airPodsState?.currentOutputName ?? AudioHardware.defaultOutputDevice()?.name,
            prefersNoiseCancellation: manager?.prefersNoiseCancellation() ?? false,
            bufferDuration: preferredBufferDuration
        )
    }

    private func installTapIfNeeded() throws {
        guard let inputTapHandler else { return }
        guard !tapInstalled else { return }

        let inputNode = audioEngine.inputNode
        let format = inputNode.inputFormat(forBus: 0)
        let tapFormat = AVAudioFormat(
            commonFormat: format.commonFormat,
            sampleRate: format.sampleRate > 0 ? format.sampleRate : preferredSampleRate,
            channels: format.channelCount > 0 ? format.channelCount : 1,
            interleaved: format.isInterleaved
        ) ?? format

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: tapFormat) { buffer, time in
            inputTapHandler(buffer, time)
        }

        tapInstalled = true
    }
}
