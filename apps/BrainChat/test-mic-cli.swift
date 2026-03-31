#!/usr/bin/env swift

import AVFoundation
import Foundation

// ANSI color codes
struct Colors {
    static let green = "\u{001B}[32m"
    static let red = "\u{001B}[31m"
    static let yellow = "\u{001B}[33m"
    static let blue = "\u{001B}[34m"
    static let reset = "\u{001B}[0m"
    static let bold = "\u{001B}[1m"
}

class MicrophonePermissionTester {
    
    func run() {
        print("\(Colors.bold)\(Colors.blue)🎤 MICROPHONE PERMISSION TESTER\(Colors.reset)")
        print("================================")
        
        // 1. Check system info
        checkSystemInfo()
        
        // 2. Check current permission status
        checkCurrentPermissionStatus()
        
        // 3. List available audio devices
        listAudioDevices()
        
        // 4. Test permission request if needed
        testPermissionRequest()
        
        // 5. Test audio session activation
        testAudioSession()
        
        print("\n\(Colors.bold)Test completed!\(Colors.reset)")
    }
    
    func checkSystemInfo() {
        print("\n📍 SYSTEM INFORMATION")
        print("--------------------")
        
        let osVersion = ProcessInfo.processInfo.operatingSystemVersion
        print("macOS Version: \(osVersion.majorVersion).\(osVersion.minorVersion).\(osVersion.patchVersion)")
        
        let bundleId = Bundle.main.bundleIdentifier ?? "Unknown"
        print("Bundle ID: \(bundleId)")
        
        let processName = ProcessInfo.processInfo.processName
        print("Process: \(processName)")
        
        // Check if running as standalone or in app
        if bundleId.contains("test-mic") || processName.contains("test-mic") {
            print("\(Colors.yellow)⚠️  Running as standalone CLI tool\(Colors.reset)")
        } else {
            print("\(Colors.green)✅ Running within app bundle\(Colors.reset)")
        }
    }
    
    func checkCurrentPermissionStatus() {
        print("\n🔐 CURRENT PERMISSION STATUS")
        print("---------------------------")
        
        let authStatus = AVCaptureDevice.authorizationStatus(for: .audio)
        let statusMessage = authStatusString(authStatus)
        
        print("Microphone Permission: \(statusMessage)")
        
        switch authStatus {
        case .authorized:
            print("\(Colors.green)✅ Permission granted - microphone access available\(Colors.reset)")
        case .denied:
            print("\(Colors.red)❌ Permission denied - user must enable in System Preferences\(Colors.reset)")
            print("   → System Preferences → Security & Privacy → Privacy → Microphone")
        case .notDetermined:
            print("\(Colors.yellow)⚪ Permission not yet requested\(Colors.reset)")
        case .restricted:
            print("\(Colors.red)🔒 Permission restricted - might be managed by IT policy\(Colors.reset)")
        @unknown default:
            print("\(Colors.red)❓ Unknown permission status\(Colors.reset)")
        }
    }
    
    func listAudioDevices() {
        print("\n🎛️  AVAILABLE AUDIO DEVICES")
        print("-------------------------")
        
        // Use AVCaptureDeviceDiscoverySession instead of deprecated devices(for:)
        let discoverySession = AVCaptureDevice.DiscoverySession(
            deviceTypes: [.microphone, .external],
            mediaType: .audio,
            position: .unspecified
        )
        let audioDevices = discoverySession.devices
        
        if audioDevices.isEmpty {
            print("\(Colors.red)❌ No audio input devices found\(Colors.reset)")
        } else {
            print("Found \(audioDevices.count) audio device(s):")
            
            for (index, device) in audioDevices.enumerated() {
                print("  \(index + 1). \(device.localizedName)")
                print("     ID: \(device.uniqueID)")
                print("     Connected: \(device.isConnected ? "Yes" : "No")")
                
                if device.hasMediaType(.audio) {
                    print("     \(Colors.green)✅ Supports audio input\(Colors.reset)")
                } else {
                    print("     \(Colors.red)❌ No audio input support\(Colors.reset)")
                }
            }
        }
    }
    
    func testPermissionRequest() {
        print("\n🔄 PERMISSION REQUEST TEST")
        print("-------------------------")
        
        let currentStatus = AVCaptureDevice.authorizationStatus(for: .audio)
        
        if currentStatus == .notDetermined {
            print("Requesting microphone permission...")
            print("\(Colors.yellow)⚠️  A system dialog should appear - please respond\(Colors.reset)")
            
            let semaphore = DispatchSemaphore(value: 0)
            
            AVCaptureDevice.requestAccess(for: .audio) { [weak self] granted in
                print("\nPermission request completed:")
                
                if granted {
                    print("\(Colors.green)✅ Permission GRANTED\(Colors.reset)")
                } else {
                    print("\(Colors.red)❌ Permission DENIED\(Colors.reset)")
                }
                
                // Check final status
                let finalStatus = AVCaptureDevice.authorizationStatus(for: .audio)
                let statusMessage = self?.authStatusString(finalStatus) ?? "Unknown"
                print("Final status: \(statusMessage)")
                
                semaphore.signal()
            }
            
            // Wait up to 30 seconds for user response
            let timeout = DispatchTime.now() + .seconds(30)
            let result = semaphore.wait(timeout: timeout)
            
            if result == .timedOut {
                print("\(Colors.red)❌ Permission request timed out after 30 seconds\(Colors.reset)")
            }
            
        } else {
            print("Permission already determined - skipping request")
            print("Current status: \(authStatusString(currentStatus))")
        }
    }
    
    func testAudioSession() {
        print("\n🔊 AUDIO CAPTURE TEST")
        print("--------------------")
        
        let authStatus = AVCaptureDevice.authorizationStatus(for: .audio)
        
        guard authStatus == .authorized else {
            print("\(Colors.yellow)⚠️  Skipping audio capture test - microphone permission not granted\(Colors.reset)")
            return
        }
        
        do {
            // Create capture session (macOS approach)
            let captureSession = AVCaptureSession()
            
            // Find default audio device
            let discoverySession = AVCaptureDevice.DiscoverySession(
                deviceTypes: [.microphone, .external],
                mediaType: .audio,
                position: .unspecified
            )
            
            guard let audioDevice = discoverySession.devices.first else {
                print("\(Colors.red)❌ No audio input device found\(Colors.reset)")
                return
            }
            
            print("Using audio device: \(audioDevice.localizedName)")
            
            // Create device input
            let deviceInput = try AVCaptureDeviceInput(device: audioDevice)
            
            if captureSession.canAddInput(deviceInput) {
                captureSession.addInput(deviceInput)
                print("✅ Audio input added to capture session")
            } else {
                print("\(Colors.red)❌ Cannot add audio input to capture session\(Colors.reset)")
                return
            }
            
            // Start the session briefly to test
            captureSession.startRunning()
            print("\(Colors.green)✅ Audio capture session started successfully\(Colors.reset)")
            
            // Stop immediately (we're just testing)
            captureSession.stopRunning()
            print("Audio capture session stopped")
            
        } catch {
            print("\(Colors.red)❌ Audio capture error: \(error)\(Colors.reset)")
            
            if let avError = error as? AVError {
                print("AVError code: \(avError.code.rawValue)")
                print("Description: \(avError.localizedDescription)")
            }
        }
    }
    
    // MARK: - Helper Methods
    
    func authStatusString(_ status: AVAuthorizationStatus) -> String {
        switch status {
        case .authorized:
            return "\(Colors.green)AUTHORIZED ✅\(Colors.reset)"
        case .denied:
            return "\(Colors.red)DENIED ❌\(Colors.reset)"
        case .notDetermined:
            return "\(Colors.yellow)NOT DETERMINED ⚪\(Colors.reset)"
        case .restricted:
            return "\(Colors.red)RESTRICTED 🔒\(Colors.reset)"
        @unknown default:
            return "\(Colors.red)UNKNOWN ❓\(Colors.reset)"
        }
    }
    
    func formatDeviceInfo(_ device: AVCaptureDevice) -> String {
        var info = "Device: \(device.localizedName)"
        info += "\n       ID: \(device.uniqueID)"
        info += "\n       Connected: \(device.isConnected ? "Yes" : "No")"
        
        if #available(macOS 10.15, *) {
            info += "\n       In use: \(device.isInUseByAnotherApplication ? "Yes" : "No")"
        }
        
        return info
    }
}

// MARK: - Main Execution

func main() {
    let args = CommandLine.arguments
    
    if args.contains("--help") || args.contains("-h") {
        printUsage()
        exit(0)
    }
    
    if args.contains("--version") || args.contains("-v") {
        print("Microphone Permission Tester v1.0")
        print("Compatible with macOS 10.14+")
        exit(0)
    }
    
    let tester = MicrophonePermissionTester()
    tester.run()
    
    // Exit with appropriate code
    let finalStatus = AVCaptureDevice.authorizationStatus(for: .audio)
    let exitCode: Int32 = (finalStatus == .authorized) ? 0 : 1
    
    if finalStatus == .authorized {
        print("\n\(Colors.green)🎉 SUCCESS: Microphone access is working!\(Colors.reset)")
    } else {
        print("\n\(Colors.red)⚠️  WARNING: Microphone access not available\(Colors.reset)")
        print("Exit code: \(exitCode)")
    }
    
    exit(exitCode)
}

func printUsage() {
    print("""
    Microphone Permission Tester
    
    Usage: ./test-mic [OPTIONS]
    
    This tool tests microphone permissions for macOS apps.
    It checks the current permission status, requests permission if needed,
    lists available audio devices, and tests audio session activation.
    
    OPTIONS:
        -h, --help     Show this help message
        -v, --version  Show version information
    
    COMPILATION:
        xcrun swiftc test-mic-cli.swift -o test-mic
    
    EXAMPLES:
        ./test-mic                    # Run full test suite
        ./test-mic --help            # Show this help
        ./test-mic --version         # Show version
    
    EXIT CODES:
        0  Success - microphone access granted
        1  Failed - permission denied or error
    """)
}

// Run the main function
main()