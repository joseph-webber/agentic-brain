import AVFoundation
import Foundation
@testable import BrainChat

final class MockAudioPlayer: CartesiaAudioPlaying {
    var onStreamFinished: ((UUID) -> Void)?
    var preparedIDs: [UUID] = []
    var appendedChunks: [UUID: [Data]] = [:]
    var finishedIDs: [UUID] = []
    var cancelCallCount = 0
    var appendError: Error?

    func prepareStream(id: UUID, sampleRate: Double, channels: AVAudioChannelCount) {
        preparedIDs.append(id)
    }

    func appendPCMChunk(_ data: Data, for id: UUID) throws {
        if let appendError { throw appendError }
        appendedChunks[id, default: []].append(data)
    }

    func finishStream(id: UUID) {
        finishedIDs.append(id)
        onStreamFinished?(id)
    }

    func cancelCurrentSpeech() {
        cancelCallCount += 1
    }
}
