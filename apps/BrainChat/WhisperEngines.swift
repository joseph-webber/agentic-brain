import AVFoundation
import Foundation

/// OpenAI Whisper API client for speech-to-text
/// Requires OpenAI API key, sends audio to cloud for transcription
final class WhisperAPIEngine: @unchecked Sendable {
    private let apiKey: String
    private let endpoint = "https://api.openai.com/v1/audio/transcriptions"
    
    init(apiKey: String) {
        self.apiKey = apiKey
    }
    
    /// Transcribe audio file using OpenAI Whisper API
    func transcribe(audioURL: URL, language: String = "en") async throws -> String {
        guard !apiKey.isEmpty else {
            throw WhisperError.missingAPIKey
        }
        
        let audioData = try Data(contentsOf: audioURL)
        
        // Build multipart form data
        let boundary = UUID().uuidString
        var body = Data()
        
        // Add file field
        body.append(Data("--\(boundary)\r\n".utf8))
        body.append(Data("Content-Disposition: form-data; name=\"file\"; filename=\"audio.m4a\"\r\n".utf8))
        body.append(Data("Content-Type: audio/m4a\r\n\r\n".utf8))
        body.append(audioData)
        body.append(Data("\r\n".utf8))
        
        // Add model field
        body.append(Data("--\(boundary)\r\n".utf8))
        body.append(Data("Content-Disposition: form-data; name=\"model\"\r\n\r\n".utf8))
        body.append(Data("whisper-1\r\n".utf8))
        
        // Add language field
        body.append(Data("--\(boundary)\r\n".utf8))
        body.append(Data("Content-Disposition: form-data; name=\"language\"\r\n\r\n".utf8))
        body.append(Data("\(language)\r\n".utf8))
        
        body.append(Data("--\(boundary)--\r\n".utf8))
        
        guard let url = URL(string: endpoint) else {
            throw WhisperError.invalidEndpoint(endpoint)
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = body
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw WhisperError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw WhisperError.apiError(httpResponse.statusCode, errorMessage)
        }
        
        // Parse JSON response
        let json = try JSONDecoder().decode(WhisperResponse.self, from: data)
        return json.text
    }
    
    /// Transcribe audio buffer directly (records to temp file first)
    func transcribe(buffer: AVAudioPCMBuffer, format: AVAudioFormat) async throws -> String {
        let tempURL = FileManager.default.temporaryDirectory.appendingPathComponent("whisper_\(UUID().uuidString).m4a")
        
        // Write buffer to file
        let file = try AVAudioFile(forWriting: tempURL, settings: format.settings, commonFormat: .pcmFormatFloat32, interleaved: false)
        try file.write(from: buffer)
        
        defer {
            try? FileManager.default.removeItem(at: tempURL)
        }
        
        return try await transcribe(audioURL: tempURL)
    }
}

struct WhisperResponse: Decodable {
    let text: String
}

enum WhisperError: LocalizedError {
    case missingAPIKey
    case invalidResponse
    case apiError(Int, String)
    case recordingFailed
    case noAudioData
    case invalidEndpoint(String)
    
    var errorDescription: String? {
        switch self {
        case .missingAPIKey: return "OpenAI API key required for Whisper API"
        case .invalidResponse: return "Invalid response from Whisper API"
        case .apiError(let code, let message): return "Whisper API error \(code): \(message)"
        case .recordingFailed: return "Failed to record audio"
        case .noAudioData: return "No audio data captured"
        case .invalidEndpoint(let url): return "Invalid Whisper API endpoint URL: \(url)"
        }
    }
}

/// Local whisper.cpp engine using command line tool
/// Requires whisper.cpp to be installed: brew install whisper-cpp
final class WhisperCppEngine: @unchecked Sendable {
    private let modelPath: String
    private let whisperPath: String
    
    init() {
        // Check common installation paths
        let brewPath = "/opt/homebrew/bin/whisper-cpp"
        let usrLocalPath = "/usr/local/bin/whisper-cpp"
        
        if FileManager.default.fileExists(atPath: brewPath) {
            self.whisperPath = brewPath
        } else if FileManager.default.fileExists(atPath: usrLocalPath) {
            self.whisperPath = usrLocalPath
        } else {
            self.whisperPath = "whisper-cpp" // Hope it's in PATH
        }
        
        // Default model path
        let homeDir = FileManager.default.homeDirectoryForCurrentUser.path
        self.modelPath = "\(homeDir)/.whisper/models/ggml-base.en.bin"
    }
    
    var isAvailable: Bool {
        let binaryOK = FileManager.default.fileExists(atPath: whisperPath) || 
            Process.run("/usr/bin/which", ["whisper-cpp"]) != nil
        let modelOK = FileManager.default.fileExists(atPath: modelPath)
        return binaryOK && modelOK
    }
    
    /// Transcribe audio file using whisper.cpp
    func transcribe(audioURL: URL, language: String = "en") async throws -> String {
        // Convert to WAV if needed (whisper.cpp prefers WAV)
        let wavURL = try await convertToWAV(audioURL)
        defer { try? FileManager.default.removeItem(at: wavURL) }
        
        let process = Process()
        process.executableURL = URL(fileURLWithPath: whisperPath)
        process.arguments = [
            "-m", modelPath,
            "-f", wavURL.path,
            "-l", language,
            "--no-timestamps",
            "-otxt"
        ]
        
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        
        try process.run()
        process.waitUntilExit()
        
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let output = String(data: data, encoding: .utf8) ?? ""
        
        // Parse output - whisper.cpp outputs transcript directly
        return output.trimmingCharacters(in: .whitespacesAndNewlines)
    }
    
    private func convertToWAV(_ inputURL: URL) async throws -> URL {
        let outputURL = FileManager.default.temporaryDirectory.appendingPathComponent("whisper_\(UUID().uuidString).wav")
        
        // Use ffmpeg or afconvert for conversion
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/afconvert")
        process.arguments = [
            inputURL.path,
            outputURL.path,
            "-f", "WAVE",
            "-d", "LEI16@16000"  // 16-bit, 16kHz for Whisper
        ]
        
        try process.run()
        process.waitUntilExit()
        
        return outputURL
    }
}

extension Process {
    static func run(_ executable: String, _ arguments: [String]) -> String? {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments
        
        let pipe = Pipe()
        process.standardOutput = pipe
        
        do {
            try process.run()
            process.waitUntilExit()
            
            if process.terminationStatus == 0 {
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                return String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines)
            }
        } catch {
            return nil
        }
        return nil
    }
}
