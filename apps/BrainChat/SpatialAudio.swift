import Foundation
import AVFoundation

struct SpatialVoicePlacement: Codable, Equatable {
    let name: String
    let azimuth: Float
    let elevation: Float
    let distance: Float
    let gain: Float

    static let karenFront = SpatialVoicePlacement(
        name: "Karen",
        azimuth: 0,
        elevation: 0,
        distance: 1.0,
        gain: 1.0
    )
}

final class SpatialAudioController {
    private let engine = AVAudioEngine()
    private let environment = AVAudioEnvironmentNode()
    private var players: [String: AVAudioPlayerNode] = [:]

    private(set) var spatialAudioEnabled = true

    init() {
        engine.attach(environment)
        engine.connect(environment, to: engine.mainMixerNode, format: nil)

        environment.listenerPosition = AVAudio3DPoint(x: 0, y: 0, z: 0)
        environment.listenerAngularOrientation = AVAudio3DAngularOrientation(yaw: 0, pitch: 0, roll: 0)
        environment.renderingAlgorithm = .HRTFHQ
        environment.reverbParameters.enable = false
        environment.distanceAttenuationParameters.distanceAttenuationModel = .exponential
        environment.distanceAttenuationParameters.rolloffFactor = 0.4
    }

    func configure(sampleRate: Double = 48_000) throws {
        if !engine.isRunning {
            engine.prepare()
            try engine.start()
        }

        if engine.outputNode.outputFormat(forBus: 0).sampleRate == 0,
           let format = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 2) {
            engine.connect(environment, to: engine.mainMixerNode, format: format)
        }
    }

    func setSpatialAudioEnabled(_ enabled: Bool) {
        spatialAudioEnabled = enabled
    }

    func setListenerFacingFront() {
        updateListenerOrientation(yaw: 0, pitch: 0, roll: 0)
    }

    func updateListenerOrientation(yaw: Float, pitch: Float, roll: Float) {
        environment.listenerAngularOrientation = AVAudio3DAngularOrientation(yaw: yaw, pitch: pitch, roll: roll)
    }

    func playSpeechFile(at url: URL, placement: SpatialVoicePlacement = .karenFront) throws {
        let audioFile = try AVAudioFile(forReading: url)
        let player = playerNode(for: placement.name, format: audioFile.processingFormat)
        apply(placement: placement, to: player)

        if !engine.isRunning {
            try configure(sampleRate: audioFile.processingFormat.sampleRate)
        }

        player.scheduleFile(audioFile, at: nil)
        player.play()
    }

    func play(buffer: AVAudioPCMBuffer, placement: SpatialVoicePlacement = .karenFront) throws {
        let player = playerNode(for: placement.name, format: buffer.format)
        apply(placement: placement, to: player)

        if !engine.isRunning {
            try configure(sampleRate: buffer.format.sampleRate)
        }

        player.scheduleBuffer(buffer, at: nil, options: [])
        player.play()
    }

    func stopAll() {
        for player in players.values {
            player.stop()
        }
        engine.pause()
    }

    private func playerNode(for voiceName: String, format: AVAudioFormat) -> AVAudioPlayerNode {
        if let player = players[voiceName] {
            return player
        }

        let player = AVAudioPlayerNode()
        engine.attach(player)
        engine.connect(player, to: environment, format: format)
        players[voiceName] = player
        return player
    }

    private func apply(placement: SpatialVoicePlacement, to player: AVAudioPlayerNode) {
        let position = spatialAudioEnabled ? point(for: placement) : AVAudio3DPoint(x: 0, y: 0, z: 1)
        player.position = position
        player.renderingAlgorithm = .HRTFHQ
        player.reverbBlend = 0
        player.volume = placement.gain
    }

    private func point(for placement: SpatialVoicePlacement) -> AVAudio3DPoint {
        let azimuthRadians = placement.azimuth * .pi / 180
        let elevationRadians = placement.elevation * .pi / 180
        let clampedDistance = max(0.25, placement.distance)

        let x = clampedDistance * sin(azimuthRadians) * cos(elevationRadians)
        let y = clampedDistance * sin(elevationRadians)
        let z = clampedDistance * cos(azimuthRadians) * cos(elevationRadians)

        return AVAudio3DPoint(x: x, y: y, z: z)
    }
}
