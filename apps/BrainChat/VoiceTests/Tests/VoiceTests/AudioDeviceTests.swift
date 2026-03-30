import XCTest
@testable import VoiceTestLib

// MARK: - Audio Device Tests

final class AudioDeviceTests: XCTestCase {

    // MARK: - Device Enumeration

    func testDeviceEnumeration() {
        let controller = MockSpeechRecognitionController()
        let devices = controller.availableInputDevices()
        XCTAssertGreaterThanOrEqual(devices.count, 1)
    }

    func testBuiltInMicrophoneAlwaysPresent() {
        let controller = MockSpeechRecognitionController()
        let devices = controller.availableInputDevices()
        XCTAssertNotNil(devices.first(where: { $0.name.contains("Built-in") }))
    }

    func testDevicesFallbackToBuiltIn() {
        let emptyDevices: [TestAudioDevice] = []
        let resolved = emptyDevices.isEmpty
            ? [TestAudioDevice(id: "default", name: "Built-in Microphone")]
            : emptyDevices
        XCTAssertEqual(resolved.count, 1)
        XCTAssertEqual(resolved[0].name, "Built-in Microphone")
    }

    func testDeviceIdentifiersAreUnique() {
        let devices = [
            TestAudioDevice(id: "1", name: "Built-in Microphone"),
            TestAudioDevice(id: "2", name: "AirPods Max"),
            TestAudioDevice(id: "3", name: "External USB Mic"),
        ]
        let ids = Set(devices.map(\.id))
        XCTAssertEqual(ids.count, devices.count)
    }

    func testDeviceHashability() {
        let d1 = TestAudioDevice(id: "1", name: "Mic A")
        let d2 = TestAudioDevice(id: "2", name: "Mic B")
        let d3 = TestAudioDevice(id: "1", name: "Mic A")
        var s: Set<TestAudioDevice> = [d1, d2, d3]
        XCTAssertEqual(s.count, 2)
        s.remove(d1)
        XCTAssertEqual(s.count, 1)
    }

    // MARK: - AirPods Max Detection

    func testAirPodsMaxDetectedByName() {
        let cases: [(String, Bool)] = [
            ("AirPods Max", true),
            ("Joseph's AirPods Max", true),
            ("AIRPODS MAX", true),
            ("AirPods Pro", false),
            ("AirPods", false),
            ("Built-in Microphone", false),
        ]
        for (name, expected) in cases {
            XCTAssertEqual(name.lowercased().contains("airpods max"), expected,
                           "Detection failed for '\(name)'")
        }
    }

    func testAirPodsMaxAutoSelected() {
        let devices = [
            TestAudioDevice(id: "1", name: "Built-in Microphone"),
            TestAudioDevice(id: "2", name: "Joseph's AirPods Max", isAirPodsMax: true),
            TestAudioDevice(id: "3", name: "External Mic"),
        ]
        let selected = devices.first(where: { $0.isAirPodsMax }) ?? devices[0]
        XCTAssertTrue(selected.isAirPodsMax)
        XCTAssertEqual(selected.name, "Joseph's AirPods Max")
    }

    func testFallbackWhenNoAirPods() {
        let devices = [
            TestAudioDevice(id: "1", name: "Built-in Microphone"),
            TestAudioDevice(id: "2", name: "External USB Mic"),
        ]
        let selected = devices.first(where: { $0.isAirPodsMax }) ?? devices[0]
        XCTAssertFalse(selected.isAirPodsMax)
        XCTAssertEqual(selected.name, "Built-in Microphone")
    }

    func testAirPodsMaxStateObject() {
        let airpods = MockAirPods()
        airpods.simulateConnect()
        let state = airpods.currentState()
        XCTAssertTrue(state.connected)
        XCTAssertEqual(state.deviceName, "Joseph's AirPods Max")
        XCTAssertEqual(state.battery, 85)
    }

    func testAirPodsMaxDisconnectedState() {
        let airpods = MockAirPods()
        let state = airpods.currentState()
        XCTAssertFalse(state.connected)
        XCTAssertNil(state.deviceName)
    }

    // MARK: - Audio Routing

    func testRouteAudioToAirPods() throws {
        let airpods = MockAirPods()
        airpods.simulateConnect()
        try airpods.routeAllAudioToAirPods()
        XCTAssertEqual(airpods.routeAllCallCount, 1)
    }

    func testRouteInputToAirPods() throws {
        let airpods = MockAirPods()
        airpods.simulateConnect()
        try airpods.routeAirPodsInput()
        XCTAssertEqual(airpods.routeInputCallCount, 1)
    }

    func testRoutingFailsWhenDisconnected() {
        let airpods = MockAirPods()
        XCTAssertThrowsError(try airpods.routeAllAudioToAirPods()) { error in
            XCTAssertEqual((error as? MockAirPodsError), .notConnected)
        }
        XCTAssertThrowsError(try airpods.routeAirPodsInput()) { error in
            XCTAssertEqual((error as? MockAirPodsError), .notConnected)
        }
    }

    func testMultipleRoutingCalls() throws {
        let airpods = MockAirPods()
        airpods.simulateConnect()
        for _ in 0..<3 { try airpods.routeAllAudioToAirPods() }
        XCTAssertEqual(airpods.routeAllCallCount, 3)
    }

    func testRouteAfterReconnect() throws {
        let airpods = MockAirPods()
        airpods.simulateConnect()
        try airpods.routeAllAudioToAirPods()
        airpods.simulateDisconnect()
        XCTAssertThrowsError(try airpods.routeAllAudioToAirPods())
        airpods.simulateConnect()
        try airpods.routeAllAudioToAirPods()
        XCTAssertEqual(airpods.routeAllCallCount, 2)
    }

    // MARK: - Sample Rate Configuration

    func testCartesiaSampleRate() {
        XCTAssertEqual(VoiceTestHelpers.cartesiaSampleRate, 24_000)
    }

    func testCaptureSampleRate() {
        XCTAssertEqual(VoiceTestHelpers.captureSampleRate, 48_000)
    }

    func testPCMFormatSpec() {
        XCTAssertEqual(MemoryLayout<Int16>.size, 2, "PCM uses 16-bit per sample")
    }

    func testPCMDataSizeCalculation() {
        let expectedBytes = 24_000 * 1 * MemoryLayout<Int16>.size
        XCTAssertEqual(expectedBytes, 48_000, "1s mono 24kHz PCM16 = 48KB")
    }

    func testStereoPCMDataSizeCalculation() {
        let expectedBytes = 48_000 * 2 * MemoryLayout<Int16>.size
        XCTAssertEqual(expectedBytes, 192_000, "1s stereo 48kHz PCM16 = 192KB")
    }

    // MARK: - PCM Data Generation

    func testPCMDataGeneration() {
        let data = VoiceTestHelpers.makePCMData(frameCount: 480, channels: 1)
        XCTAssertEqual(data.count, 480 * MemoryLayout<Int16>.size)
        XCTAssertFalse(data.isEmpty)
    }

    func testStereoPCMDataGeneration() {
        let data = VoiceTestHelpers.makePCMData(frameCount: 480, channels: 2)
        XCTAssertEqual(data.count, 480 * 2 * MemoryLayout<Int16>.size)
    }

    func testEmptyPCMData() {
        XCTAssertTrue(VoiceTestHelpers.makeEmptyPCMData().isEmpty)
    }

    // MARK: - Device Monitoring

    func testMonitoringStartStop() {
        let airpods = MockAirPods()
        airpods.startMonitoring()
        XCTAssertTrue(airpods.monitoringActive)
        airpods.stopMonitoring()
        XCTAssertFalse(airpods.monitoringActive)
    }

    func testStateChangeNotifications() {
        let airpods = MockAirPods()
        var changes: [Bool] = []
        airpods.onStateChange = { changes.append($0) }
        airpods.simulateConnect()
        airpods.simulateDisconnect()
        airpods.simulateConnect()
        XCTAssertEqual(changes, [true, false, true])
    }

    func testNoNotificationOnDuplicateState() {
        let airpods = MockAirPods()
        var notifications: [String] = []
        airpods.onNotification = { notifications.append($0) }
        airpods.simulateDisconnect()
        XCTAssertEqual(notifications.count, 0, "No notification for redundant disconnect")
        airpods.simulateConnect()
        airpods.simulateConnect()
        XCTAssertEqual(notifications.count, 1, "No notification for redundant connect")
    }

    // MARK: - Output Route Detection

    func testOutputRouteAirPodsDetection() {
        for route in ["AirPods Max", "Joseph's AirPods Max", "AirPods Pro", "AirPods"] {
            XCTAssertTrue(route.localizedCaseInsensitiveContains("AirPods"))
        }
    }

    func testOutputRouteNonAirPods() {
        for route in ["Built-in Output", "External Speakers", "HDMI Audio"] {
            XCTAssertFalse(route.localizedCaseInsensitiveContains("AirPods"))
        }
    }

    // MARK: - Device Selection Priority

    func testAirPodsMaxHighestPriority() {
        let devices = [
            TestAudioDevice(id: "1", name: "Built-in Microphone"),
            TestAudioDevice(id: "2", name: "USB Microphone"),
            TestAudioDevice(id: "3", name: "Joseph's AirPods Max", isAirPodsMax: true),
            TestAudioDevice(id: "4", name: "Bluetooth Speaker"),
        ]
        let selected = devices.first(where: { $0.isAirPodsMax }) ?? devices[0]
        XCTAssertEqual(selected.id, "3")
    }

    func testDeviceSelectionFallbackChain() {
        let devices = [
            TestAudioDevice(id: "1", name: "Built-in Microphone"),
            TestAudioDevice(id: "2", name: "USB Mic"),
        ]
        let selected = devices.first(where: { $0.isAirPodsMax })
            ?? devices.first(where: { $0.name.contains("Built-in") })
            ?? devices[0]
        XCTAssertEqual(selected.name, "Built-in Microphone")
    }
}
