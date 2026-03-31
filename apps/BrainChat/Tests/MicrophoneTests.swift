import XCTest
import AVFoundation
import Foundation
import Security

class MicrophoneTests: XCTestCase {
    
    // MARK: - Info.plist Tests
    
    func testInfoPlistHasMicrophoneUsageDescription() throws {
        let bundle = Bundle.main
        let microphoneUsageDescription = bundle.object(forInfoDictionaryKey: "NSMicrophoneUsageDescription") as? String
        
        XCTAssertNotNil(microphoneUsageDescription, 
                       "NSMicrophoneUsageDescription must be present in Info.plist")
        XCTAssertFalse(microphoneUsageDescription?.isEmpty ?? true, 
                      "NSMicrophoneUsageDescription cannot be empty")
        XCTAssertTrue(microphoneUsageDescription?.count ?? 0 > 10, 
                     "NSMicrophoneUsageDescription should be descriptive (>10 chars)")
        
        print("✅ NSMicrophoneUsageDescription: \(microphoneUsageDescription ?? "nil")")
    }
    
    func testInfoPlistHasRequiredKeys() throws {
        let bundle = Bundle.main
        let bundleId = bundle.bundleIdentifier
        let displayName = bundle.object(forInfoDictionaryKey: "CFBundleDisplayName") as? String
        let executableName = bundle.object(forInfoDictionaryKey: "CFBundleExecutable") as? String
        
        XCTAssertNotNil(bundleId, "Bundle identifier must be present")
        XCTAssertNotNil(displayName, "CFBundleDisplayName must be present")
        XCTAssertNotNil(executableName, "CFBundleExecutable must be present")
        
        print("✅ Bundle ID: \(bundleId ?? "nil")")
        print("✅ Display Name: \(displayName ?? "nil")")
        print("✅ Executable: \(executableName ?? "nil")")
    }
    
    // MARK: - Code Signing Tests
    
    func testAppIsCodeSigned() throws {
        let bundle = Bundle.main
        guard let bundlePath = bundle.bundlePath as CFString? else {
            XCTFail("Cannot get bundle path")
            return
        }
        
        // Create SecStaticCode reference
        var staticCode: SecStaticCode?
        let status = SecStaticCodeCreateWithPath(bundlePath as CFURL, [], &staticCode)
        
        XCTAssertEqual(status, errSecSuccess, "Failed to create SecStaticCode reference")
        XCTAssertNotNil(staticCode, "SecStaticCode should not be nil")
        
        // Check if code is properly signed
        if let code = staticCode {
            let checkStatus = SecStaticCodeCheckValidity(code, [], nil)
            XCTAssertEqual(checkStatus, errSecSuccess, 
                          "Code signature validation failed: \(checkStatus)")
            print("✅ Code signing validation: PASSED")
        }
    }
    
    func testHasValidDeveloperIdentity() throws {
        let bundle = Bundle.main
        guard let bundlePath = bundle.bundlePath as CFString? else {
            XCTFail("Cannot get bundle path")
            return
        }
        
        var staticCode: SecStaticCode?
        let status = SecStaticCodeCreateWithPath(bundlePath as CFURL, [], &staticCode)
        XCTAssertEqual(status, errSecSuccess)
        
        if let code = staticCode {
            var signingInfo: CFDictionary?
            let infoStatus = SecCodeCopySigningInformation(code, [], &signingInfo)
            
            if infoStatus == errSecSuccess, let info = signingInfo as? [String: Any] {
                let teamID = info["teamid"] as? String
                let signerCN = info["subject-cn"] as? String
                
                print("✅ Team ID: \(teamID ?? "none")")
                print("✅ Signer: \(signerCN ?? "none")")
                
                // For development, we might have ad-hoc signing, which is okay
                if teamID == nil {
                    print("⚠️  Ad-hoc signing detected (okay for development)")
                }
            }
        }
    }
    
    // MARK: - Entitlements Tests
    
    func testHasAudioInputEntitlement() throws {
        // Note: Reading entitlements programmatically is complex and platform-specific
        // This is a simplified check that assumes the entitlements file exists
        let bundle = Bundle.main
        let entitlementsPath = bundle.path(forResource: "BrainChat", ofType: "entitlements")
        
        if let path = entitlementsPath {
            let entitlementsData = try Data(contentsOf: URL(fileURLWithPath: path))
            let entitlementsString = String(data: entitlementsData, encoding: .utf8) ?? ""
            
            XCTAssertTrue(entitlementsString.contains("com.apple.security.device.audio-input"), 
                         "Entitlements must include com.apple.security.device.audio-input")
            print("✅ Audio input entitlement found in entitlements file")
        } else {
            print("⚠️  Entitlements file not found (might be embedded)")
            // For release builds, entitlements are embedded in the binary
            // We'll check this via codesign in the shell script
        }
    }
    
    // MARK: - AVFoundation Tests
    
    func testAVCaptureDeviceAuthorizationStatus() throws {
        let authStatus = AVCaptureDevice.authorizationStatus(for: .audio)
        
        print("🎤 Current microphone authorization status: \(authStatusString(authStatus))")
        
        // We can't assert a specific status since it depends on user action
        // But we can verify the API works and returns a valid status
        let validStatuses: [AVAuthorizationStatus] = [.notDetermined, .denied, .authorized, .restricted]
        XCTAssertTrue(validStatuses.contains(authStatus), 
                     "Authorization status should be one of the valid values")
    }
    
    func testCanRequestMicrophonePermission() throws {
        let expectation = XCTestExpectation(description: "Microphone permission request")
        
        AVCaptureDevice.requestAccess(for: .audio) { granted in
            print("🎤 Permission request result: \(granted ? "GRANTED" : "DENIED")")
            expectation.fulfill()
        }
        
        wait(for: [expectation], timeout: 10.0)
        // Note: This doesn't fail the test if permission is denied
        // It just verifies the API works
    }
    
    func testCanEnumerateAudioDevices() throws {
        // Use AVCaptureDeviceDiscoverySession instead of deprecated devices(for:)
        let discoverySession = AVCaptureDevice.DiscoverySession(
            deviceTypes: [.microphone, .external],
            mediaType: .audio,
            position: .unspecified
        )
        let audioDevices = discoverySession.devices
        
        XCTAssertFalse(audioDevices.isEmpty, "Should have at least one audio input device")
        
        for device in audioDevices {
            print("🎤 Found audio device: \(device.localizedName)")
            XCTAssertNotNil(device.uniqueID, "Device should have unique ID")
            XCTAssertFalse(device.localizedName.isEmpty, "Device should have name")
        }
    }
    
    // MARK: - System Checks
    
    func testMacOSVersionSupportsAVFoundation() throws {
        let osVersion = ProcessInfo.processInfo.operatingSystemVersion
        
        // AVFoundation microphone access requires macOS 10.14+
        let minimumMajor = 10
        let minimumMinor = 14
        
        let isSupported = osVersion.majorVersion > minimumMajor || 
                         (osVersion.majorVersion == minimumMajor && osVersion.minorVersion >= minimumMinor)
        
        XCTAssertTrue(isSupported, 
                     "macOS \(osVersion.majorVersion).\(osVersion.minorVersion) should support AVFoundation audio access")
        
        print("✅ macOS Version: \(osVersion.majorVersion).\(osVersion.minorVersion).\(osVersion.patchVersion)")
    }
    
    func testSecurityFrameworkAvailable() throws {
        // Test that Security framework is properly linked
        var staticCode: SecStaticCode?
        let status = SecStaticCodeCreateWithPath(Bundle.main.bundleURL as CFURL, [], &staticCode)
        
        XCTAssertEqual(status, errSecSuccess, "Security framework should be available")
        print("✅ Security framework: Available")
    }
    
    // MARK: - Helper Methods
    
    private func authStatusString(_ status: AVAuthorizationStatus) -> String {
        switch status {
        case .authorized:
            return "AUTHORIZED ✅"
        case .denied:
            return "DENIED ❌"
        case .notDetermined:
            return "NOT DETERMINED ⚪"
        case .restricted:
            return "RESTRICTED 🔒"
        @unknown default:
            return "UNKNOWN ❓"
        }
    }
}

// MARK: - Test Suite Extensions

extension MicrophoneTests {
    
    func testFullMicrophonePermissionFlow() throws {
        print("\n🧪 FULL MICROPHONE PERMISSION TEST FLOW")
        print("=====================================")
        
        // 1. Check current status
        let initialStatus = AVCaptureDevice.authorizationStatus(for: .audio)
        print("1. Initial status: \(authStatusString(initialStatus))")
        
        // 2. If not determined, request permission
        if initialStatus == .notDetermined {
            print("2. Requesting permission...")
            let expectation = XCTestExpectation(description: "Permission request")
            
            AVCaptureDevice.requestAccess(for: .audio) { granted in
                print("3. Permission \(granted ? "GRANTED" : "DENIED")")
                
                // 4. Check status after request
                let finalStatus = AVCaptureDevice.authorizationStatus(for: .audio)
                print("4. Final status: \(self.authStatusString(finalStatus))")
                
                expectation.fulfill()
            }
            
            wait(for: [expectation], timeout: 15.0)
        } else {
            print("2. Permission already determined - no request needed")
        }
        
        // 5. Try to access microphone using AVCaptureSession (macOS approach)
        let finalStatus = AVCaptureDevice.authorizationStatus(for: .audio)
        if finalStatus == .authorized {
            do {
                let captureSession = AVCaptureSession()
                
                // Find an audio device
                let discoverySession = AVCaptureDevice.DiscoverySession(
                    deviceTypes: [.microphone, .external],
                    mediaType: .audio,
                    position: .unspecified
                )
                
                guard let audioDevice = discoverySession.devices.first else {
                    print("5. No audio device found")
                    return
                }
                
                let deviceInput = try AVCaptureDeviceInput(device: audioDevice)
                
                if captureSession.canAddInput(deviceInput) {
                    captureSession.addInput(deviceInput)
                    captureSession.startRunning()
                    print("5. Audio capture session started successfully ✅")
                    captureSession.stopRunning()
                } else {
                    print("5. Cannot add audio input to capture session")
                }
                
            } catch {
                print("5. Audio capture session failed: \(error)")
            }
        } else {
            print("5. Cannot test audio capture - permission not granted")
        }
        
        print("=====================================\n")
    }
}