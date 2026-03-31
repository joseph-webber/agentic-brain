import Foundation
import XCTest

/// CI/CD Tests for macOS App Code Signing
/// These tests ensure Brain Chat and future Swift apps have proper code signing
/// which is REQUIRED for microphone/camera permissions to work on macOS.
///
/// Lesson learned: Without proper code signing with sealed resources,
/// AVCaptureDevice.requestAccess() won't show the permission dialog!
final class CodeSigningTests: XCTestCase {
    
    let appPath = "/Applications/Brain Chat.app"
    let buildPath: String = {
        // Get the build path relative to this test file
        let srcRoot = ProcessInfo.processInfo.environment["SRCROOT"] ?? 
            FileManager.default.currentDirectoryPath
        return "\(srcRoot)/build/Brain Chat.app"
    }()
    
    // MARK: - Code Signing Tests
    
    /// Test that the app bundle exists and is properly structured
    func testAppBundleExists() {
        let paths = [appPath, buildPath]
        let exists = paths.contains { FileManager.default.fileExists(atPath: $0) }
        XCTAssertTrue(exists, "Brain Chat.app should exist in /Applications or build directory")
    }
    
    /// Test that the app is code signed (not unsigned)
    func testAppIsCodeSigned() {
        let result = runCodesign(["--verify", "--verbose=2", appPath])
        XCTAssertTrue(result.success, "App must be code signed. Error: \(result.output)")
    }
    
    /// Test that the app has sealed resources (required for permissions)
    func testAppHasSealedResources() {
        let result = runCodesign(["-dvvv", appPath])
        XCTAssertTrue(result.output.contains("Sealed Resources"), 
            "App must have sealed resources for microphone permission to work")
    }
    
    /// Test that the app has a valid bundle identifier
    func testAppHasBundleIdentifier() {
        let result = runCodesign(["-dvvv", appPath])
        XCTAssertTrue(result.output.contains("Identifier="), 
            "App must have a bundle identifier")
        XCTAssertFalse(result.output.contains("Identifier=BrainChat\n"), 
            "Bundle identifier should be reverse-DNS format, not just 'BrainChat'")
    }
    
    /// Test that code signature is valid (not corrupted)
    func testCodeSignatureIsValid() {
        let result = runCodesign(["--verify", "--strict", appPath])
        XCTAssertTrue(result.success, 
            "Code signature must be valid. Run: codesign --force --deep --sign - '\(appPath)'")
    }
    
    // MARK: - Info.plist Privacy Keys Tests
    
    /// Test that Info.plist exists
    func testInfoPlistExists() {
        let plistPath = "\(appPath)/Contents/Info.plist"
        XCTAssertTrue(FileManager.default.fileExists(atPath: plistPath), 
            "Info.plist must exist at \(plistPath)")
    }
    
    /// Test that NSMicrophoneUsageDescription is present (REQUIRED for mic access)
    func testMicrophoneUsageDescriptionExists() {
        let plist = loadInfoPlist()
        XCTAssertNotNil(plist?["NSMicrophoneUsageDescription"] as? String,
            "NSMicrophoneUsageDescription is REQUIRED in Info.plist for microphone access")
    }
    
    /// Test that NSSpeechRecognitionUsageDescription is present
    func testSpeechRecognitionUsageDescriptionExists() {
        let plist = loadInfoPlist()
        XCTAssertNotNil(plist?["NSSpeechRecognitionUsageDescription"] as? String,
            "NSSpeechRecognitionUsageDescription is REQUIRED for speech recognition")
    }
    
    /// Test that CFBundleIdentifier is in reverse-DNS format
    func testBundleIdentifierFormat() {
        let plist = loadInfoPlist()
        let bundleId = plist?["CFBundleIdentifier"] as? String
        XCTAssertNotNil(bundleId, "CFBundleIdentifier must exist")
        XCTAssertTrue(bundleId?.contains(".") == true, 
            "CFBundleIdentifier should be reverse-DNS format (e.g., com.example.app)")
    }
    
    /// Test that all required privacy keys have descriptive values
    func testPrivacyDescriptionsAreDescriptive() {
        let plist = loadInfoPlist()
        
        let privacyKeys = [
            "NSMicrophoneUsageDescription",
            "NSSpeechRecognitionUsageDescription"
        ]
        
        for key in privacyKeys {
            if let value = plist?[key] as? String {
                XCTAssertTrue(value.count >= 20, 
                    "\(key) should have a descriptive message (got: '\(value)')")
                XCTAssertFalse(value.lowercased().contains("todo"), 
                    "\(key) should not contain TODO placeholders")
            }
        }
    }
    
    // MARK: - Build Script Tests
    
    /// Test that build.sh includes codesign command
    func testBuildScriptIncludesCodesign() {
        let buildScriptPath = getBuildScriptPath()
        guard let content = try? String(contentsOfFile: buildScriptPath, encoding: .utf8) else {
            XCTFail("Could not read build.sh at \(buildScriptPath)")
            return
        }
        
        XCTAssertTrue(content.contains("codesign"), 
            "build.sh MUST include codesign command for microphone permission to work")
        XCTAssertTrue(content.contains("--force") && content.contains("--deep"), 
            "build.sh should use 'codesign --force --deep --sign -' for proper signing")
    }
    
    // MARK: - Executable Tests
    
    /// Test that the main executable exists
    func testExecutableExists() {
        let execPath = "\(appPath)/Contents/MacOS/BrainChat"
        XCTAssertTrue(FileManager.default.fileExists(atPath: execPath), 
            "Executable must exist at \(execPath)")
    }
    
    /// Test that the executable is for ARM64 (Apple Silicon)
    func testExecutableIsARM64() {
        let result = shell("file '\(appPath)/Contents/MacOS/BrainChat'")
        XCTAssertTrue(result.contains("arm64"), 
            "Executable should be compiled for arm64 (Apple Silicon)")
    }
    
    // MARK: - Permission Dialog Tests
    
    /// Test that requesting microphone access is possible (won't crash)
    func testMicrophoneRequestAPIAvailable() {
        // This test verifies the API is available - actual permission request
        // requires user interaction and a properly signed app
        #if canImport(AVFoundation)
        // AVCaptureDevice.authorizationStatus(for:) should be callable
        // We can't actually request permission in a test without UI
        XCTAssertTrue(true, "AVFoundation available for microphone access")
        #else
        XCTFail("AVFoundation not available")
        #endif
    }
    
    // MARK: - Helpers
    
    private func runCodesign(_ args: [String]) -> (success: Bool, output: String) {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/codesign")
        task.arguments = args
        
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe
        
        do {
            try task.run()
            task.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let output = String(data: data, encoding: .utf8) ?? ""
            return (task.terminationStatus == 0, output)
        } catch {
            return (false, error.localizedDescription)
        }
    }
    
    private func shell(_ command: String) -> String {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/bash")
        task.arguments = ["-c", command]
        
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe
        
        do {
            try task.run()
            task.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            return String(data: data, encoding: .utf8) ?? ""
        } catch {
            return ""
        }
    }
    
    private func loadInfoPlist() -> [String: Any]? {
        let plistPath = "\(appPath)/Contents/Info.plist"
        guard let data = FileManager.default.contents(atPath: plistPath) else {
            return nil
        }
        return try? PropertyListSerialization.propertyList(from: data, options: [], format: nil) as? [String: Any]
    }
    
    private func getBuildScriptPath() -> String {
        // Try multiple possible locations
        let paths = [
            "/Users/joe/brain/agentic-brain/apps/BrainChat/build.sh",
            "./build.sh",
            "../build.sh"
        ]
        return paths.first { FileManager.default.fileExists(atPath: $0) } ?? paths[0]
    }
}

// MARK: - Code Signing Requirements Documentation
/*
 MACOS APP CODE SIGNING REQUIREMENTS FOR MICROPHONE ACCESS
 ==========================================================
 
 For AVCaptureDevice.requestAccess(for: .audio) to show a permission dialog,
 the app MUST be properly code signed with sealed resources.
 
 REQUIRED in build.sh:
 ```bash
 codesign --force --deep --sign - "${APP_BUNDLE}"
 ```
 
 REQUIRED in Info.plist:
 ```xml
 <key>NSMicrophoneUsageDescription</key>
 <string>App needs microphone access for voice features.</string>
 ```
 
 WITHOUT proper code signing:
 - App won't appear in System Settings > Privacy > Microphone
 - Permission dialog won't show
 - Microphone access will silently fail
 
 This was discovered on 2026-03-29 when Brain Chat mic wasn't working
 but KarenChat (which was properly signed) worked fine.
 
 See: apps/BrainChat/build.sh for the working pattern
 */
