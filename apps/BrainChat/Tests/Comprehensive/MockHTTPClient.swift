import Foundation
@testable import BrainChatLib

final class MockHTTPClient: HTTPClient {
    var lastRequest: URLRequest?
    var nextResult: Result<(Data, HTTPURLResponse), Error> = .failure(TestError(message: "No result configured"))

    func send(request: URLRequest, completion: @escaping (Result<(Data, HTTPURLResponse), Error>) -> Void) {
        lastRequest = request
        completion(nextResult)
    }
}
