// SPDX-License-Identifier: Apache-2.0
// Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
//
// Spatial Audio Swift Bridge — positions ladies in 3D around Joseph.
//
// This companion binary works alongside airpods_bridge.swift to provide
// per-utterance 3D positioning via AVAudioEngine.  It:
//
//   1. Receives a mono AIFF speech file + position JSON from Python
//   2. Creates an AVAudioPlayerNode attached to an AVAudioEnvironmentNode
//   3. Sets the source's 3D position (azimuth → x/z cartesian)
//   4. Plays through AirPods with real spatial audio
//   5. Exits when playback completes
//
// Build:
//   xcrun swiftc -O -framework AVFAudio -framework CoreMotion \
//       -o spatial_play spatial_swift.swift
//
// Usage:
//   ./spatial_play play '{"file":"/path/to/speech.aiff","azimuth":30,"elevation":0,"distance":1.0}'
//   ./spatial_play positions   # dumps all lady positions as JSON
//   ./spatial_play test        # plays a test tone from 90° right

import Foundation
import AVFAudio
#if canImport(CoreMotion)
import CoreMotion
#endif

// MARK: - Data models

struct LadyPosition: Codable {
    let name: String
    let azimuth: Float
    let elevation: Float
    let distance: Float
}

struct PlayRequest: Codable {
    let file: String
    let azimuth: Float
    let elevation: Float
    let distance: Float
    let gain: Float?
}

// All 14 ladies — must match spatial_audio.py LADY_POSITIONS
let ladyPositions: [LadyPosition] = [
    LadyPosition(name: "Karen",    azimuth: 0,   elevation: 0, distance: 1.0),
    LadyPosition(name: "Kyoko",    azimuth: 30,  elevation: 0, distance: 1.0),
    LadyPosition(name: "Tingting", azimuth: 55,  elevation: 0, distance: 1.0),
    LadyPosition(name: "Yuna",     azimuth: 80,  elevation: 0, distance: 1.0),
    LadyPosition(name: "Linh",     azimuth: 110, elevation: 0, distance: 1.0),
    LadyPosition(name: "Kanya",    azimuth: 140, elevation: 0, distance: 1.0),
    LadyPosition(name: "Dewi",     azimuth: 165, elevation: 0, distance: 1.0),
    LadyPosition(name: "Sari",     azimuth: 180, elevation: 0, distance: 1.0),
    LadyPosition(name: "Wayan",    azimuth: 195, elevation: 0, distance: 1.0),
    LadyPosition(name: "Moira",    azimuth: 225, elevation: 0, distance: 1.0),
    LadyPosition(name: "Alice",    azimuth: 255, elevation: 0, distance: 1.0),
    LadyPosition(name: "Zosia",    azimuth: 285, elevation: 0, distance: 1.0),
    LadyPosition(name: "Flo",      azimuth: 315, elevation: 0, distance: 1.0),
    LadyPosition(name: "Shelley",  azimuth: 345, elevation: 0, distance: 1.0),
]

// MARK: - Coordinate conversion

/// Convert spherical (azimuth, elevation, distance) → AVAudio3DPoint (x, y, z).
/// Convention: x = right, y = up, z = front.
func toCartesian(azimuthDeg: Float, elevationDeg: Float, distance: Float) -> AVAudio3DPoint {
    let az = azimuthDeg * .pi / 180.0
    let el = elevationDeg * .pi / 180.0
    let x = distance * sin(az) * cos(el)
    let y = distance * sin(el)
    let z = distance * cos(az) * cos(el)
    return AVAudio3DPoint(x: x, y: y, z: z)
}

// MARK: - Spatial Player

final class SpatialPlayer {
    private let engine = AVAudioEngine()
    private let environment = AVAudioEnvironmentNode()
    private let playerNode = AVAudioPlayerNode()
    private let semaphore = DispatchSemaphore(value: 0)
    #if canImport(CoreMotion)
    private let motionManager = CMHeadphoneMotionManager()
    #endif

    init() {
        engine.attach(environment)
        engine.attach(playerNode)
    }

    /// Play a mono AIFF file positioned in 3D space.
    func play(
        file: URL,
        azimuth: Float,
        elevation: Float,
        distance: Float,
        gain: Float
    ) -> Bool {
        guard let audioFile = try? AVAudioFile(forReading: file) else {
            fputs("Error: cannot open audio file \(file.path)\n", stderr)
            return false
        }

        let format = audioFile.processingFormat

        // Wire: playerNode → environment → mainMixer → output
        engine.connect(playerNode, to: environment, format: format)
        engine.connect(environment, to: engine.mainMixerNode, format: nil)

        // Set listener at origin facing forward
        environment.listenerPosition = AVAudio3DPoint(x: 0, y: 0, z: 0)
        environment.listenerAngularOrientation = AVAudio3DAngularOrientation(
            yaw: 0, pitch: 0, roll: 0
        )
        environment.renderingAlgorithm = .HRTFHQ

        // Set source position from azimuth
        let position = toCartesian(
            azimuthDeg: azimuth,
            elevationDeg: elevation,
            distance: max(0.25, distance)
        )
        playerNode.position = position
        playerNode.reverbBlend = 0.0  // Dry — no room reverb
        environment.outputVolume = gain

        // Start engine
        do {
            try engine.start()
        } catch {
            fputs("Error: AVAudioEngine failed to start: \(error)\n", stderr)
            return false
        }

        // Schedule file and signal completion
        playerNode.scheduleFile(audioFile, at: nil) { [weak self] in
            self?.semaphore.signal()
        }
        playerNode.play()

        // Block until playback finishes (with 60s safety timeout)
        let timeout = DispatchTime.now() + .seconds(60)
        let result = semaphore.wait(timeout: timeout)

        // Teardown
        playerNode.stop()
        engine.stop()

        return result == .success
    }

    /// Generate and play a simple test tone (sine wave) from a given position.
    func playTestTone(
        azimuth: Float,
        frequency: Float = 440.0,
        duration: Float = 1.5,
        sampleRate: Double = 44100.0
    ) -> Bool {
        let frameCount = AVAudioFrameCount(sampleRate * Double(duration))
        guard let format = AVAudioFormat(
            standardFormatWithSampleRate: sampleRate, channels: 1
        ) else { return false }
        guard let buffer = AVAudioPCMBuffer(
            pcmFormat: format, frameCapacity: frameCount
        ) else { return false }

        buffer.frameLength = frameCount
        guard let channelData = buffer.floatChannelData?[0] else { return false }

        // Generate sine wave
        for i in 0..<Int(frameCount) {
            let t = Float(i) / Float(sampleRate)
            channelData[i] = 0.5 * sin(2.0 * .pi * frequency * t)
        }

        // Wire engine
        engine.connect(playerNode, to: environment, format: format)
        engine.connect(environment, to: engine.mainMixerNode, format: nil)

        environment.listenerPosition = AVAudio3DPoint(x: 0, y: 0, z: 0)
        environment.listenerAngularOrientation = AVAudio3DAngularOrientation(
            yaw: 0, pitch: 0, roll: 0
        )
        environment.renderingAlgorithm = .HRTFHQ

        let position = toCartesian(
            azimuthDeg: azimuth, elevationDeg: 0, distance: 1.0
        )
        playerNode.position = position
        playerNode.reverbBlend = 0.0

        do {
            try engine.start()
        } catch {
            fputs("Error: \(error)\n", stderr)
            return false
        }

        playerNode.scheduleBuffer(buffer, at: nil) { [weak self] in
            self?.semaphore.signal()
        }
        playerNode.play()

        let timeout = DispatchTime.now() + .seconds(Int(duration) + 2)
        let result = semaphore.wait(timeout: timeout)
        playerNode.stop()
        engine.stop()
        return result == .success
    }
}

// MARK: - JSON helpers

func writeJSON(_ object: Any) {
    guard JSONSerialization.isValidJSONObject(object),
          let data = try? JSONSerialization.data(
              withJSONObject: object, options: [.sortedKeys]
          ) else {
        fputs("{}", stdout)
        return
    }
    FileHandle.standardOutput.write(data)
}

func writeEncodable<T: Encodable>(_ value: T) {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    guard let data = try? encoder.encode(value) else {
        fputs("[]", stdout)
        return
    }
    FileHandle.standardOutput.write(data)
}

// MARK: - CLI entry point

let command = CommandLine.arguments.dropFirst().first ?? "positions"
let payloadJSON = CommandLine.arguments.dropFirst(2).first

switch command {

case "play":
    guard let payloadJSON,
          let data = payloadJSON.data(using: .utf8),
          let request = try? JSONDecoder().decode(PlayRequest.self, from: data)
    else {
        writeJSON(["success": false, "error": "invalid payload"])
        exit(1)
    }

    let fileURL = URL(fileURLWithPath: request.file)
    let player = SpatialPlayer()
    let ok = player.play(
        file: fileURL,
        azimuth: request.azimuth,
        elevation: request.elevation,
        distance: request.distance,
        gain: request.gain ?? 1.0
    )
    writeJSON(["success": ok])
    exit(ok ? 0 : 1)

case "test":
    // Play a test tone sweeping from left to right
    let player = SpatialPlayer()
    let azimuth: Float = Float(payloadJSON ?? "90") ?? 90.0
    let ok = player.playTestTone(azimuth: azimuth, frequency: 440, duration: 1.5)
    writeJSON(["success": ok, "azimuth": azimuth])
    exit(ok ? 0 : 1)

case "positions":
    writeEncodable(ladyPositions)
    exit(0)

case "cartesian":
    // Convert all lady positions to cartesian for debugging
    var results: [[String: Any]] = []
    for lady in ladyPositions {
        let point = toCartesian(
            azimuthDeg: lady.azimuth,
            elevationDeg: lady.elevation,
            distance: lady.distance
        )
        results.append([
            "name": lady.name,
            "azimuth": lady.azimuth,
            "x": point.x,
            "y": point.y,
            "z": point.z,
        ])
    }
    writeJSON(results)
    exit(0)

default:
    writeJSON(["success": false, "error": "unknown command: \(command)"])
    exit(1)
}
