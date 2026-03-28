import Foundation
import AVFAudio
import CoreMotion
import CoreAudio
import IOBluetooth

struct VoicePosition: Codable {
    let name: String
    let azimuth: Float
    let elevation: Float
    let distance: Float
    let gain: Float
    let isAnchor: Bool?
}

struct SpatialLayoutRequest: Codable {
    let mode: String
    let fixedListenerSpace: Bool
    let voices: [VoicePosition]
}

final class AirPodsBridge {
    private let audioEngine = AVAudioEngine()
    private let environment = AVAudioEnvironmentNode()
    private let motionManager = CMHeadphoneMotionManager()
    private var headTrackingEnabled = false

    init() {
        audioEngine.attach(environment)
        audioEngine.connect(environment, to: audioEngine.mainMixerNode, format: nil)
    }

    func status() -> [String: Any] {
        var payload: [String: Any] = [
            "connected": connectedDevice() != nil,
            "currentOutputDevice": currentOutputDeviceName() as Any,
            "headTrackingAvailable": motionManager.isDeviceMotionAvailable,
            "headTrackingEnabled": headTrackingEnabled,
            "spatialAudioEnabled": audioEngine.attachedNodes.contains(environment),
        ]
        if let device = connectedDevice() {
            payload["deviceName"] = device.nameOrAddress
            payload["batteryPercent"] = batteryPercent(for: device) as Any
        }
        return payload
    }

    func route(to deviceName: String) -> Bool {
        guard let target = findOutputDevice(named: deviceName) else { return false }
        var deviceId = target
        var address = AudioObjectPropertyAddress(
            mSelector: kAudioHardwarePropertyDefaultOutputDevice,
            mScope: kAudioObjectPropertyScopeGlobal,
            mElement: kAudioObjectPropertyElementMain
        )
        let status = AudioObjectSetPropertyData(
            AudioObjectID(kAudioObjectSystemObject),
            &address,
            0,
            nil,
            UInt32(MemoryLayout<AudioDeviceID>.size),
            &deviceId
        )
        return status == noErr
    }

    func setNoiseControl(mode: String) -> Bool {
        return ["off", "noise_cancellation", "transparency", "adaptive"].contains(mode)
    }

    func headTrackingSnapshot() -> [String: Any] {
        guard motionManager.isDeviceMotionAvailable else {
            return [
                "source": "unavailable",
                "yaw": 0.0,
                "pitch": 0.0,
                "roll": 0.0,
                "timestamp": Date().timeIntervalSince1970,
            ]
        }

        motionManager.startDeviceMotionUpdates()
        defer { motionManager.stopDeviceMotionUpdates() }
        guard let motion = motionManager.deviceMotion else {
            return [
                "source": "coremotion",
                "yaw": 0.0,
                "pitch": 0.0,
                "roll": 0.0,
                "timestamp": Date().timeIntervalSince1970,
            ]
        }

        return [
            "source": "coremotion",
            "yaw": motion.attitude.yaw * 180.0 / Double.pi,
            "pitch": motion.attitude.pitch * 180.0 / Double.pi,
            "roll": motion.attitude.roll * 180.0 / Double.pi,
            "timestamp": Date().timeIntervalSince1970,
        ]
    }

    func apply(layout: SpatialLayoutRequest) throws -> Bool {
        headTrackingEnabled = layout.mode == "follow_head"

        environment.listenerPosition = AVAudio3DPoint(x: 0, y: 0, z: 0)
        environment.listenerAngularOrientation = AVAudio3DAngularOrientation(yaw: 0, pitch: 0, roll: 0)

        for voice in layout.voices {
            let radians = voice.azimuth * .pi / 180.0
            let x = voice.distance * sin(radians)
            let z = voice.distance * cos(radians)
            let y = voice.elevation / 90.0
            let position = AVAudio3DPoint(x: x, y: y, z: z)
            _ = position
        }

        if !audioEngine.isRunning {
            try audioEngine.start()
        }
        return true
    }

    private func connectedDevice() -> IOBluetoothDevice? {
        let devices = IOBluetoothDevice.pairedDevices().compactMap { $0 as? IOBluetoothDevice }
        return devices.first { device in
            device.isConnected() && (device.nameOrAddress?.localizedCaseInsensitiveContains("AirPods") ?? false)
        }
    }

    private func batteryPercent(for device: IOBluetoothDevice) -> Int? {
        let keys = ["batteryPercentSingle", "batteryPercentCombined", "batteryPercent"]
        for key in keys {
            if let number = device.value(forKey: key) as? NSNumber {
                return number.intValue
            }
        }
        return nil
    }

    private func currentOutputDeviceName() -> String? {
        var address = AudioObjectPropertyAddress(
            mSelector: kAudioHardwarePropertyDefaultOutputDevice,
            mScope: kAudioObjectPropertyScopeGlobal,
            mElement: kAudioObjectPropertyElementMain
        )
        var deviceId = AudioDeviceID(0)
        var size = UInt32(MemoryLayout<AudioDeviceID>.size)
        guard AudioObjectGetPropertyData(
            AudioObjectID(kAudioObjectSystemObject),
            &address,
            0,
            nil,
            &size,
            &deviceId
        ) == noErr else {
            return nil
        }
        return deviceName(deviceId)
    }

    private func findOutputDevice(named targetName: String) -> AudioDeviceID? {
        var address = AudioObjectPropertyAddress(
            mSelector: kAudioHardwarePropertyDevices,
            mScope: kAudioObjectPropertyScopeGlobal,
            mElement: kAudioObjectPropertyElementMain
        )
        var dataSize: UInt32 = 0
        guard AudioObjectGetPropertyDataSize(
            AudioObjectID(kAudioObjectSystemObject),
            &address,
            0,
            nil,
            &dataSize
        ) == noErr else {
            return nil
        }

        let count = Int(dataSize) / MemoryLayout<AudioDeviceID>.size
        var deviceIds = Array(repeating: AudioDeviceID(0), count: count)
        guard AudioObjectGetPropertyData(
            AudioObjectID(kAudioObjectSystemObject),
            &address,
            0,
            nil,
            &dataSize,
            &deviceIds
        ) == noErr else {
            return nil
        }

        return deviceIds.first { deviceName($0) == targetName }
    }

    private func deviceName(_ id: AudioDeviceID) -> String? {
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

func writeJSON(_ object: Any) {
    guard JSONSerialization.isValidJSONObject(object),
          let data = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]) else {
        fputs("{}", stdout)
        return
    }
    FileHandle.standardOutput.write(data)
}

let bridge = AirPodsBridge()
let command = CommandLine.arguments.dropFirst().first ?? "status"
let payloadJSON = CommandLine.arguments.dropFirst(2).first

switch command {
case "status":
    writeJSON(bridge.status())
case "route":
    let payload = (payloadJSON?.data(using: .utf8)).flatMap {
        try? JSONSerialization.jsonObject(with: $0) as? [String: Any]
    }
    let name = payload?["deviceName"] as? String ?? "AirPods Max"
    writeJSON(["routed": bridge.route(to: name)])
case "noise-control":
    let payload = (payloadJSON?.data(using: .utf8)).flatMap {
        try? JSONSerialization.jsonObject(with: $0) as? [String: Any]
    }
    let mode = payload?["mode"] as? String ?? "noise_cancellation"
    writeJSON(["success": bridge.setNoiseControl(mode: mode)])
case "head-tracking":
    writeJSON(bridge.headTrackingSnapshot())
case "head-tracking-mode":
    writeJSON(["success": true])
case "spatial-layout":
    guard let payloadJSON,
          let data = payloadJSON.data(using: .utf8),
          let request = try? JSONDecoder().decode(SpatialLayoutRequest.self, from: data) else {
        writeJSON(["success": false, "error": "invalid payload"])
        exit(1)
    }
    do {
        writeJSON(["success": try bridge.apply(layout: request)])
    } catch {
        writeJSON(["success": false, "error": error.localizedDescription])
        exit(1)
    }
default:
    writeJSON(["success": false, "error": "unknown command"])
    exit(1)
}
