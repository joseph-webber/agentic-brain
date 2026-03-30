/**
 MicCaptureCLI.swift — Audio capture proxy with hardened runtime + mic entitlement
 
 This CLI tool has:
 - Hardened runtime (flags=0x10002)
 - com.apple.security.device.audio-input entitlement
 - com.josephbrain.micrequestapp bundle ID (reuses existing TCC grant!)
 
 Usage:
   MicCaptureCLI <duration_seconds>    # capture N seconds, write raw int16 to stdout
   MicCaptureCLI --check               # print TCC status
   MicCaptureCLI --stream              # continuous stream until killed
 
 Raw output: int16 LE, mono, 24000 Hz — read by sox_capture.py
 */
import AVFoundation
import Foundation

func checkStatus() -> AVAuthorizationStatus {
    return AVCaptureDevice.authorizationStatus(for: .audio)
}

func runCapture(duration: Double) {
    let status = checkStatus()
    fputs("TCC status: \(status.rawValue) (3=authorized)\n", stderr)
    
    guard status == .authorized else {
        fputs("ERROR: Not authorized. Run MicRequestApp.app first to grant permission.\n", stderr)
        exit(1)
    }
    
    let sampleRate: Double = 24000
    let engine = AVAudioEngine()
    let inputNode = engine.inputNode
    let format = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 1)!
    
    var outputData = Data()
    let lock = NSLock()
    var done = false
    
    inputNode.installTap(onBus: 0, bufferSize: 4800, format: format) { buffer, _ in
        guard !done else { return }
        let channelData = buffer.floatChannelData![0]
        let frameLength = Int(buffer.frameLength)
        lock.lock()
        for i in 0..<frameLength {
            let s = Int16(max(-32768, min(32767, channelData[i] * 32768.0)))
            withUnsafeBytes(of: s) { outputData.append(contentsOf: $0) }
        }
        lock.unlock()
    }
    
    do {
        try engine.start()
        fputs("Recording \(duration)s...\n", stderr)
    } catch {
        fputs("Engine start error: \(error)\n", stderr)
        exit(1)
    }
    
    Thread.sleep(forTimeInterval: duration)
    done = true
    engine.stop()
    
    lock.lock()
    let captured = outputData
    lock.unlock()
    
    FileHandle.standardOutput.write(captured)
    fputs("Wrote \(captured.count) bytes (\(captured.count/2) samples @ \(Int(sampleRate))Hz)\n", stderr)
}

func runStream() {
    let status = checkStatus()
    guard status == .authorized else {
        fputs("ERROR: Not authorized\n", stderr)
        exit(1)
    }
    
    let sampleRate: Double = 24000
    let engine = AVAudioEngine()
    let format = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 1)!
    
    let stdoutFH = FileHandle.standardOutput
    
    engine.inputNode.installTap(onBus: 0, bufferSize: 4800, format: format) { buffer, _ in
        let channelData = buffer.floatChannelData![0]
        let frameLength = Int(buffer.frameLength)
        var chunk = Data(count: frameLength * 2)
        chunk.withUnsafeMutableBytes { ptr in
            let buf = ptr.bindMemory(to: Int16.self)
            for i in 0..<frameLength {
                buf[i] = Int16(max(-32768, min(32767, channelData[i] * 32768.0)))
            }
        }
        stdoutFH.write(chunk)
    }
    
    do {
        try engine.start()
        fputs("Streaming (Ctrl+C to stop)...\n", stderr)
    } catch {
        fputs("Engine error: \(error)\n", stderr)
        exit(1)
    }
    
    RunLoop.main.run()  // Run forever until signal
}

// MAIN
let args = CommandLine.arguments

if args.contains("--check") {
    let s = checkStatus()
    let names = [0: "NotDetermined", 1: "Restricted", 2: "Denied", 3: "Authorized"]
    print("TCC kTCCServiceMicrophone: \(s.rawValue) = \(names[Int(s.rawValue)] ?? "Unknown")")
    exit(0)
} else if args.contains("--stream") {
    runStream()
} else {
    let duration = args.count > 1 ? Double(args[1]) ?? 2.0 : 2.0
    runCapture(duration: duration)
}
