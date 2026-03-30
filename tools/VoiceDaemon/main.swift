import AVFoundation
import Foundation

struct VoiceDaemonConfig {
    let mode: String
    let duration: TimeInterval
    let voice: String
    let once: Bool
    let recordingsDirectory: URL

    static func parse(arguments: [String]) -> VoiceDaemonConfig {
        var mode = "standalone"
        var duration: TimeInterval = 5
        var voice = "Karen"
        var once = false
        let defaultDirectory = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
            .appendingPathComponent("recordings", isDirectory: true)
        var recordingsDirectory = defaultDirectory

        var index = 1
        while index < arguments.count {
            let arg = arguments[index]
            switch arg {
            case "--mode":
                if index + 1 < arguments.count {
                    mode = arguments[index + 1]
                    index += 1
                }
            case "--duration":
                if index + 1 < arguments.count {
                    duration = Double(arguments[index + 1]) ?? duration
                    index += 1
                }
            case "--voice":
                if index + 1 < arguments.count {
                    voice = arguments[index + 1]
                    index += 1
                }
            case "--recordings-dir":
                if index + 1 < arguments.count {
                    recordingsDirectory = URL(fileURLWithPath: arguments[index + 1], isDirectory: true)
                    index += 1
                }
            case "--once":
                once = true
            case "--help", "-h":
                printUsageAndExit()
            default:
                break
            }
            index += 1
        }

        return VoiceDaemonConfig(
            mode: mode,
            duration: duration,
            voice: voice,
            once: once,
            recordingsDirectory: recordingsDirectory
        )
    }

    static func printUsageAndExit() -> Never {
        let usage = """
        VoiceDaemon

        Usage:
          ./VoiceDaemon --mode standalone
          ./VoiceDaemon --mode copilot --once

        Options:
          --mode standalone|copilot
          --duration <seconds>       Recording duration per turn (default: 5)
          --voice <name>             macOS say voice (default: Karen)
          --recordings-dir <path>    Directory for WAV files
          --once                     Run a single record/transcribe/respond cycle
          --help                     Show this help
        """
        print(usage)
        exit(0)
    }
}

func timestampString() -> String {
    let formatter = DateFormatter()
    formatter.dateFormat = "yyyyMMdd-HHmmss"
    return formatter.string(from: Date())
}

func authorizationDescription(_ status: AVAuthorizationStatus) -> String {
    switch status {
    case .notDetermined: return "notDetermined"
    case .restricted: return "restricted"
    case .denied: return "denied"
    case .authorized: return "authorized"
    @unknown default: return "unknown(\(status.rawValue))"
    }
}

@main
struct VoiceDaemonMain {
    static func pause(seconds: Double) async {
        let nanoseconds = UInt64(seconds * 1_000_000_000)
        try? await Task.sleep(nanoseconds: nanoseconds)
    }

    static func main() async {
        let config = VoiceDaemonConfig.parse(arguments: CommandLine.arguments)
        let redis = RedisClient()
        let capture = AudioCapture()
        let speech = SpeechOutput(voice: config.voice)
        let bridge = CopilotBridge()

        func report(_ event: String, _ payload: [String: Any]) {
            _ = redis.report(event: event, payload: payload)
        }

        do {
            try FileManager.default.createDirectory(
                at: config.recordingsDirectory,
                withIntermediateDirectories: true
            )
        } catch {
            fputs("Failed to create recordings directory: \(error)\n", stderr)
            exit(1)
        }

        let startupPayload: [String: Any] = [
            "mode": config.mode,
            "duration": config.duration,
            "recordingsDirectory": config.recordingsDirectory.path,
            "microphone": capture.defaultInputName(),
            "redisAvailable": redis.isAvailable(),
            "status": authorizationDescription(capture.authorizationStatus()),
        ]
        report("startup", startupPayload)
        print("VoiceDaemon starting in \(config.mode) mode")
        print("Microphone: \(capture.defaultInputName())")

        do {
            guard try capture.requestPermissionIfNeeded() else {
                report("permission_denied", ["status": authorizationDescription(capture.authorizationStatus())])
                fputs("Microphone permission denied.\n", stderr)
                exit(1)
            }
        } catch {
            report("permission_error", ["error": error.localizedDescription])
            fputs("Permission error: \(error)\n", stderr)
            exit(1)
        }

        repeat {
            let wavURL = config.recordingsDirectory.appendingPathComponent("voice-input-\(timestampString()).wav")
            report("recording_started", ["file": wavURL.path, "mode": config.mode])
            print("Recording to \(wavURL.lastPathComponent)...")

            do {
                let metrics = try capture.record(to: wavURL, duration: config.duration)
                report("recording_finished", [
                    "file": wavURL.path,
                    "duration": metrics.duration,
                    "rms": metrics.rms,
                    "peak": metrics.peak,
                    "silent": metrics.isSilent,
                ])

                guard !metrics.isSilent else {
                    print("No speech detected, waiting for next cycle.")
                    report("silent_cycle", ["file": wavURL.path, "rms": metrics.rms])
                    if !config.once {
                        await pause(seconds: 0.4)
                    }
                    continue
                }

                report("transcription_started", ["file": wavURL.path])
                let transcript = try await bridge.transcribeAudio(fileURL: wavURL)
                report("transcription_finished", ["file": wavURL.path, "transcript": transcript])
                print("Transcript: \(transcript)")

                guard !transcript.isEmpty else {
                    report("empty_transcript", ["file": wavURL.path])
                    continue
                }

                report("response_started", ["mode": config.mode])
                let response = try await bridge.generateResponse(for: transcript, mode: config.mode)
                report("response_finished", ["response": response])
                print("Response: \(response)")

                report("speech_started", ["voice": config.voice])
                try speech.speak(response)
                report("speech_finished", ["voice": config.voice])
            } catch {
                report("cycle_error", ["error": error.localizedDescription])
                fputs("Cycle error: \(error.localizedDescription)\n", stderr)
                if config.once {
                    break
                }
                await pause(seconds: 1.0)
            }

            if !config.once {
                await pause(seconds: 0.4)
            }
        } while !config.once

        report("done", [
            "mode": config.mode,
            "recordingsDirectory": config.recordingsDirectory.path,
        ])
        print("VoiceDaemon finished.")
    }
}
