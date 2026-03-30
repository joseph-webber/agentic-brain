import XCTest
@testable import BrainChatLib

final class TestAirPodsManager: XCTestCase {
    func testReconnectTriggersRoutingAndNotification() {
        let disconnected = AirPodsState(connected: false, outputDevice: nil, inputDevice: nil, batteryPercent: nil, noiseControlMode: .unknown)
        let connected = AirPodsState(
            connected: true,
            outputDevice: AudioHardwareDevice(id: 1, name: "AirPods Max", sampleRate: 48000, hasInput: false, hasOutput: true),
            inputDevice: AudioHardwareDevice(id: 2, name: "AirPods Max", sampleRate: 48000, hasInput: true, hasOutput: false),
            batteryPercent: 80,
            noiseControlMode: .noiseCancellation
        )
        let hardware = MockAirPodsHardware(state: disconnected)
        let manager = AirPodsManager(hardware: hardware)
        var notifications: [String] = []
        manager.onNotification = { notifications.append($0) }
        hardware.state = connected
        _ = manager.refreshState(reason: "manual")
        XCTAssertEqual(hardware.routeAllCalls, 1)
        XCTAssertTrue(notifications.last?.contains("connected") == true)
        XCTAssertTrue(manager.prefersNoiseCancellation())
    }

    func testDisconnectNotifies() {
        let connected = AirPodsState(
            connected: true,
            outputDevice: AudioHardwareDevice(id: 1, name: "AirPods Max", sampleRate: 48000, hasInput: false, hasOutput: true),
            inputDevice: nil,
            batteryPercent: 90,
            noiseControlMode: .adaptive
        )
        let hardware = MockAirPodsHardware(state: connected)
        let manager = AirPodsManager(hardware: hardware)
        var disconnectedCalled = false
        manager.onDisconnected = { disconnectedCalled = true }
        hardware.state = AirPodsState(connected: false, outputDevice: nil, inputDevice: nil, batteryPercent: nil, noiseControlMode: .unknown)
        _ = manager.refreshState(reason: "audio-hardware-change")
        XCTAssertTrue(disconnectedCalled)
    }

    func testRouteMicrophoneUsesHardwareController() throws {
        let connected = AirPodsState(
            connected: true,
            outputDevice: AudioHardwareDevice(id: 1, name: "AirPods Max", sampleRate: 48000, hasInput: false, hasOutput: true),
            inputDevice: nil,
            batteryPercent: 90,
            noiseControlMode: .off
        )
        let hardware = MockAirPodsHardware(state: connected)
        let manager = AirPodsManager(hardware: hardware)
        _ = try manager.useAirPodsMicrophone()
        XCTAssertEqual(hardware.routeInputCalls, 1)
    }
}
