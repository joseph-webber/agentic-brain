import AVFoundation
import Foundation

// Minimal mic capture app - just records and saves
class VoiceCapture: NSObject, AVAudioRecorderDelegate {
    var recorder: AVAudioRecorder?
    let outputPath: String
    let duration: TimeInterval
    
    init(outputPath: String, duration: TimeInterval = 5.0) {
        self.outputPath = outputPath
        self.duration = duration
        super.init()
    }
    
    func start() {
        let url = URL(fileURLWithPath: outputPath)
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatLinearPCM),
            AVSampleRateKey: 16000,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false
        ]
        
        do {
            recorder = try AVAudioRecorder(url: url, settings: settings)
            recorder?.delegate = self
            recorder?.record(forDuration: duration)
            
            // Wait for recording to complete
            RunLoop.current.run(until: Date(timeIntervalSinceNow: duration + 0.5))
            
            print("RECORDED:\(outputPath)")
        } catch {
            print("ERROR:\(error.localizedDescription)")
            exit(1)
        }
    }
    
    func audioRecorderDidFinishRecording(_ recorder: AVAudioRecorder, successfully flag: Bool) {
        if flag {
            print("SUCCESS")
        } else {
            print("FAILED")
        }
    }
}

// Main
let args = CommandLine.arguments
let outputPath = args.count > 1 ? args[1] : "/tmp/voice_capture.wav"
let duration = args.count > 2 ? Double(args[2]) ?? 5.0 : 5.0

let capture = VoiceCapture(outputPath: outputPath, duration: duration)
capture.start()
