import Foundation
import XCTest

// MARK: - MockURLProtocol for network-free HTTP testing

public final class MockURLProtocol: URLProtocol, @unchecked Sendable {
    public static var requestHandler: (@Sendable (URLRequest) throws -> (HTTPURLResponse, Data))?
    public static var error: Error?

    public override class func canInit(with request: URLRequest) -> Bool { true }
    public override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    public override func startLoading() {
        if let error = Self.error {
            client?.urlProtocol(self, didFailWithError: error)
            return
        }

        guard let handler = Self.requestHandler else {
            XCTFail("MockURLProtocol.requestHandler not set")
            return
        }

        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    public override func stopLoading() {}

    public static func reset() {
        requestHandler = nil
        error = nil
    }
}

// MARK: - URLSession factory for tests

extension URLSession {
    public static func mocked() -> URLSession {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        return URLSession(configuration: config)
    }
}

// MARK: - Test Helpers

public func httpResponse(url: URL, statusCode: Int = 200,
                         headers: [String: String] = [:]) -> HTTPURLResponse {
    HTTPURLResponse(url: url, statusCode: statusCode, httpVersion: nil, headerFields: headers)!
}

public func jsonBody(_ request: URLRequest) throws -> [String: Any] {
    // URLSession may convert httpBody to httpBodyStream internally
    let data: Data
    if let body = request.httpBody {
        data = body
    } else if let stream = request.httpBodyStream {
        var collected = Data()
        stream.open()
        let bufferSize = 4096
        var buffer = [UInt8](repeating: 0, count: bufferSize)
        while stream.hasBytesAvailable {
            let count = stream.read(&buffer, maxLength: bufferSize)
            if count > 0 { collected.append(contentsOf: buffer[0..<count]) }
        }
        stream.close()
        data = collected
    } else {
        throw XCTSkip("Request has no body")
    }
    return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
}

// MARK: - Mutable reference boxes for use across async closures

public final class IntBox: @unchecked Sendable {
    public var value: Int = 0
    public init() {}
}

public final class StringArrayBox: @unchecked Sendable {
    public var values: [String] = []
    public init() {}

    /// Keyed dictionary storage for topic-tracking tests.
    public var dict: [String: String] = [:]
    public subscript(key: String) -> String? {
        get { dict[key] }
        set { dict[key] = newValue }
    }

    /// Returns all stored values as a `Set<String>`.
    public var valuesSet: Set<String> { Set(dict.values) }
}
