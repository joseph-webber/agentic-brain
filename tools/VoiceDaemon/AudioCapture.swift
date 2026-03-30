import AVFoundation
import Foundation

enum AudioCaptureError: Error, LocalizedError {
    case microphoneUnavailable
    case permissionDenied
    case recorderCreationFailed
    case recordingFailed
    case analysisFailed

    var errorDescription: String? {
        switch self {
        case .microphoneUnavailable:
            return "No microphone device is available."
        case .permissionDenied:
            return "Microphone permission is required."
        case .recorderCreationFailed:
            return "Unable to create the audio recorder."
        case .recordingFailed:
            return "Audio recording failed."
        case .analysisFailed:
            return "Unable to analyse the recorded audio."
        }
    }
}

struct RecordingMetrics {
    let duration: TimeInterval
    let rms: Float
    let peak: Float
    let isSilent: Bool
}

final class AudioCapture: NSObject {
    private let silenceThreshold: Float
    private var recorder: AVAudioRecorder?

    init(silenceThreshold: Float = 0.015) {
        self.silenceThreshold = silenceThreshold
        super.init()
    }

    func authorizationStatus() -> AVAuthorizationStatus {
        AVCaptureDevice.authorizationStatus(for: .audio)
    }

    func defaultInputName() -> String {
        AVCaptureDevice.default(for: .audio)?.localizedName ?? "Unknown microphone"
    }

    func requestPermissionIfNeeded() throws -> Bool {
        switch authorizationStatus() {
        case .authorized:
            return true
        case .notDetermined:
            let semaphore = DispatchSemaphore(value: 0)
            var granted = false
            AVCaptureDevice.requestAccess(for: .audio) { result in
                granted = result
                semaphore.signal()
            }
            semaphore.wait()
            return granted
        case .denied, .restricted:
            return false
        @unknown default:
            return false
        }
    }

    func record(to url: URL, duration: TimeInterval) throws -> RecordingMetrics {
        guard AVCaptureDevice.default(for: .audio) != nil else {
            throw AudioCaptureError.microphoneUnavailable
        }

        guard try requestPermissionIfNeeded() else {
            throw AudioCaptureError.permissionDenied
        }

        try? FileManager.default.removeItem(at: url)
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )

        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatLinearPCM),
            AVSampleRateKey: 16_000,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsBigEndianKey: false,
            AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue,
        ]

        guard let recorder = try? AVAudioRecorder(url: url, settings: settings) else {
            throw AudioCaptureError.recorderCreationFailed
        }

        self.recorder = recorder
        recorder.isMeteringEnabled = true
        recorder.prepareToRecord()

        guard recorder.record(forDuration: duration) else {
            throw AudioCaptureError.recordingFailed
        }

        while recorder.isRecording {
            RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.05))
        }

        return try analyse(url: url)
    }

    private func analyse(url: URL) throws -> RecordingMetrics {
        let audioFile = try AVAudioFile(forReading: url)
        let format = audioFile.processingFormat
        let frameCount = AVAudioFrameCount(audioFile.length)

        guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frameCount) else {
            throw AudioCaptureError.analysisFailed
        }

        try audioFile.read(into: buffer)
        let duration = Double(audioFile.length) / format.sampleRate

        if let int16Data = buffer.int16ChannelData {
            let channel = int16Data[0]
            let count = Int(buffer.frameLength)
            guard count > 0 else {
                return RecordingMetrics(duration: duration, rms: 0, peak: 0, isSilent: true)
            }

            var sumSquares: Double = 0
            var peak: Float = 0
            for index in 0..<count {
                let normalized = Float(channel[index]) / Float(Int16.max)
                let magnitude = abs(normalized)
                peak = max(peak, magnitude)
                sumSquares += Double(normalized * normalized)
            }

            let rms = Float(sqrt(sumSquares / Double(count)))
            return RecordingMetrics(duration: duration, rms: rms, peak: peak, isSilent: rms < silenceThreshold)
        }

        if let floatData = buffer.floatChannelData {
            let channel = floatData[0]
            let count = Int(buffer.frameLength)
            guard count > 0 else {
                return RecordingMetrics(duration: duration, rms: 0, peak: 0, isSilent: true)
            }

            var sumSquares: Float = 0
            var peak: Float = 0
            for index in 0..<count {
                let sample = channel[index]
                let magnitude = abs(sample)
                peak = max(peak, magnitude)
                sumSquares += sample * sample
            }

            let rms = sqrt(sumSquares / Float(count))
            return RecordingMetrics(duration: duration, rms: rms, peak: peak, isSilent: rms < silenceThreshold)
        }

        throw AudioCaptureError.analysisFailed
    }
}
