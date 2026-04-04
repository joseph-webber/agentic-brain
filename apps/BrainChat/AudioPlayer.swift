import AVFoundation
import AudioToolbox
import Combine
import CoreAudio
import Foundation

final class AudioPlayer: ObservableObject, @unchecked Sendable {
    struct OutputRoute: Equatable {
        let name: String
        let isAirPods: Bool
    }

    enum AudioPlayerError: LocalizedError {
        case unsupportedChannelCount(Int)
        case invalidPCMChunk

        var errorDescription: String? {
            switch self {
            case .unsupportedChannelCount(let count):
                return "Only mono and stereo PCM streams are supported. Received \(count) channels."
            case .invalidPCMChunk:
                return "Received an invalid PCM audio chunk."
            }
        }
    }

    private struct StreamState {
        var format: AVAudioFormat
        var channelCount: Int
        var pendingBuffers = 0
        var didReceiveEndOfStream = false
    }

    @Published private(set) var currentRoute = OutputRoute(name: "Unknown Output", isAirPods: false)
    @Published private(set) var isPlaying = false

    var onStreamFinished: ((UUID) -> Void)?

    private let engine = AVAudioEngine()
    private let playerNode = AVAudioPlayerNode()
    private var streams: [UUID: StreamState] = [:]

    init() {
        engine.attach(playerNode)
        engine.connect(playerNode, to: engine.mainMixerNode, format: nil)
        refreshOutputRoute()
    }

    func prepareStream(id: UUID, sampleRate: Double = 24_000, channels: AVAudioChannelCount = 1) {
        let format = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: sampleRate, channels: channels, interleaved: false)
        streams[id] = StreamState(format: format!, channelCount: Int(channels))
        refreshOutputRoute()
    }

    func appendPCMChunk(_ data: Data, for id: UUID) throws {
        guard var state = streams[id] else { return }
        guard state.channelCount == 1 || state.channelCount == 2 else {
            throw AudioPlayerError.unsupportedChannelCount(state.channelCount)
        }

        let bytesPerSample = MemoryLayout<Int16>.size
        let bytesPerFrame = bytesPerSample * state.channelCount
        let frameCount = data.count / bytesPerFrame
        guard frameCount > 0 else { return }

        try startEngineIfNeeded()
        refreshOutputRoute()

        guard let buffer = AVAudioPCMBuffer(pcmFormat: state.format, frameCapacity: AVAudioFrameCount(frameCount)) else {
            throw AudioPlayerError.invalidPCMChunk
        }
        buffer.frameLength = buffer.frameCapacity

        try data.withUnsafeBytes { rawBuffer in
            let source = rawBuffer.bindMemory(to: Int16.self)
            guard let sourceBase = source.baseAddress else {
                throw AudioPlayerError.invalidPCMChunk
            }

            if state.channelCount == 1 {
                guard let destination = buffer.int16ChannelData?[0] else {
                    throw AudioPlayerError.invalidPCMChunk
                }
                destination.update(from: sourceBase, count: frameCount)
            } else {
                guard let left = buffer.int16ChannelData?[0], let right = buffer.int16ChannelData?[1] else {
                    throw AudioPlayerError.invalidPCMChunk
                }
                for frame in 0..<frameCount {
                    left[frame] = sourceBase[frame * 2]
                    right[frame] = sourceBase[frame * 2 + 1]
                }
            }
        }

        state.pendingBuffers += 1
        streams[id] = state

        playerNode.scheduleBuffer(buffer) { [weak self] in
            DispatchQueue.main.async {
                self?.bufferDidFinish(for: id)
            }
        }

        if !playerNode.isPlaying {
            playerNode.play()
        }
        isPlaying = true
    }

    func finishStream(id: UUID) {
        guard var state = streams[id] else { return }
        state.didReceiveEndOfStream = true
        streams[id] = state
        finishIfNeeded(for: id)
    }

    func cancelCurrentSpeech() {
        streams.removeAll()
        playerNode.stop()
        engine.pause()
        isPlaying = false
    }

    func refreshOutputRoute() {
        let name = Self.currentOutputDeviceName() ?? "Unknown Output"
        currentRoute = OutputRoute(
            name: name,
            isAirPods: name.localizedCaseInsensitiveContains("AirPods")
        )
    }

    private func startEngineIfNeeded() throws {
        if !engine.isRunning {
            try engine.start()
        }
    }

    private func bufferDidFinish(for id: UUID) {
        guard var state = streams[id] else { return }
        state.pendingBuffers = max(0, state.pendingBuffers - 1)
        streams[id] = state
        finishIfNeeded(for: id)
    }

    private func finishIfNeeded(for id: UUID) {
        guard let state = streams[id], state.didReceiveEndOfStream, state.pendingBuffers == 0 else { return }
        streams[id] = nil

        if streams.isEmpty {
            playerNode.stop()
            engine.pause()
            isPlaying = false
        }

        onStreamFinished?(id)
    }

    private static func currentOutputDeviceName() -> String? {
        var address = AudioObjectPropertyAddress(
            mSelector: kAudioHardwarePropertyDefaultOutputDevice,
            mScope: kAudioObjectPropertyScopeGlobal,
            mElement: kAudioObjectPropertyElementMain
        )
        var deviceID = AudioDeviceID(0)
        var size = UInt32(MemoryLayout<AudioDeviceID>.size)

        let status = AudioObjectGetPropertyData(
            AudioObjectID(kAudioObjectSystemObject),
            &address,
            0,
            nil,
            &size,
            &deviceID
        )
        guard status == noErr else { return nil }
        return deviceName(for: deviceID)
    }

    private static func deviceName(for id: AudioDeviceID) -> String? {
        var address = AudioObjectPropertyAddress(
            mSelector: kAudioObjectPropertyName,
            mScope: kAudioObjectPropertyScopeGlobal,
            mElement: kAudioObjectPropertyElementMain
        )
        var name: CFString = "" as CFString
        var size = UInt32(MemoryLayout<CFString>.size)

        let status = AudioObjectGetPropertyData(id, &address, 0, nil, &size, &name)
        guard status == noErr else { return nil }
        return name as String
    }
}
