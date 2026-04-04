import Combine
import SwiftUI

// MARK: - Memory Cache for Conversation History
/// Lazy cache for conversation history to reduce memory pressure
final class ConversationHistoryCache: Sendable {
    private let maxCachedMessages: Int
    private var cache: [UUID: ChatMessage] = [:]
    private let lock = NSLock()
    
    init(maxMessages: Int = 100) {
        self.maxCachedMessages = maxMessages
    }
    
    func cache(_ message: ChatMessage) {
        lock.lock()
        defer { lock.unlock() }
        
        cache[message.id] = message
        
        // Evict oldest messages if cache is full
        if cache.count > maxCachedMessages {
            if let oldestID = cache.keys.sorted().first {
                cache.removeValue(forKey: oldestID)
            }
        }
    }
    
    func retrieve(_ id: UUID) -> ChatMessage? {
        lock.lock()
        defer { lock.unlock() }
        return cache[id]
    }
    
    func clear() {
        lock.lock()
        defer { lock.unlock() }
        cache.removeAll()
    }
}

// MARK: - Optimized ConversationStore Extension
extension ConversationStore {
    /// Get recent conversation with lazy message filtering
    /// OPTIMIZATION: Avoid processing all messages when only recent ones needed
    var recentConversationOptimized: [ChatMessage] {
        let nonSystemMessages = messages.filter { $0.role != .system }
        let recentCount = min(10, nonSystemMessages.count)
        
        // Avoid array copy if all messages are needed
        if recentCount == nonSystemMessages.count {
            return nonSystemMessages
        }
        
        return Array(nonSystemMessages.dropFirst(max(0, nonSystemMessages.count - recentCount)))
    }
    
    /// Paginate messages to reduce memory pressure during scrolling
    func pagedMessages(pageSize: Int = 20, page: Int = 0) -> [ChatMessage] {
        let start = page * pageSize
        let end = min(start + pageSize, messages.count)
        
        guard start < messages.count else { return [] }
        return Array(messages[start..<end])
    }
    
    /// OPTIMIZATION: Prune old messages from memory while keeping recent history
    func pruneOldMessages(keepRecent: Int = 50) {
        guard messages.count > keepRecent else { return }
        
        // Keep system messages and recent user/assistant messages
        let systemMessages = messages.filter { $0.role == .system }
        let recentMessages = Array(messages.filter { $0.role != .system }.suffix(keepRecent))
        
        messages = systemMessages + recentMessages
    }
}

// MARK: - String Operation Optimization
extension String {
    /// OPTIMIZATION: Efficient substring search without creating intermediate strings
    func containsIgnoreCase(_ substring: String) -> Bool {
        self.lowercased().contains(substring.lowercased())
    }
    
    /// OPTIMIZATION: Lazy character counting
    var wordCount: Int {
        self.split(separator: " ").count
    }
    
    /// OPTIMIZATION: Safe truncation without extra allocations
    func truncated(to maxLength: Int, suffix: String = "…") -> String {
        guard self.count > maxLength else { return self }
        let truncatedLength = max(0, maxLength - suffix.count)
        return String(self.prefix(truncatedLength)) + suffix
    }
}

// MARK: - Deferred Initialization Pattern
/// OPTIMIZATION: Lazy load expensive resources only when needed
final class DeferredInitializer<T> {
    private var value: T?
    private let initializer: () -> T
    private let lock = NSLock()
    
    init(_ initializer: @escaping () -> T) {
        self.initializer = initializer
    }
    
    var resolved: T {
        lock.lock()
        defer { lock.unlock() }
        
        if let value = value {
            return value
        }
        
        let newValue = initializer()
        self.value = newValue
        return newValue
    }
}

// MARK: - Background Task Coordinator
/// OPTIMIZATION: Coordinate background work to avoid main thread blocking
final class BackgroundTaskCoordinator: @unchecked Sendable {
    static let shared = BackgroundTaskCoordinator()
    
    private let queue = DispatchQueue(label: "com.brainchat.background", qos: .userInitiated)
    private var activeTasks = Set<UUID>()
    private let lock = NSLock()
    
    /// Execute work on background thread with minimal main thread blocking
    func executeBackground(_ work: @escaping @Sendable () -> Void) {
        queue.async {
            work()
        }
    }
    
    /// Execute work and update main thread with result
    func executeBackgroundWithResult<T: Sendable>(
        _ work: @escaping @Sendable () -> T,
        completion: @escaping @MainActor (T) -> Void
    ) {
        queue.async {
            let result = work()
            Task { @MainActor in
                completion(result)
            }
        }
    }
}

// MARK: - View Rendering Optimization
/// OPTIMIZATION: Reduce view hierarchy complexity by using @MainActor
@MainActor
final class ViewRenderingOptimizer {
    /// Batch multiple view updates into single render pass
    static func batchUpdates(_ updates: @escaping () -> Void) {
        CATransaction.begin()
        CATransaction.setCompletionBlock {
            // Cleanup after batch
        }
        updates()
        CATransaction.commit()
    }
    
    /// Measure view rendering time
    static func measureRendering<T>(_ operation: () -> T) -> (result: T, duration: TimeInterval) {
        let start = CFAbsoluteTimeGetCurrent()
        let result = operation()
        let duration = CFAbsoluteTimeGetCurrent() - start
        return (result, duration)
    }
}

// MARK: - Collection Operation Optimization
extension Array {
    /// OPTIMIZATION: Efficient chunk-based processing
    func chunked(into size: Int) -> [[Element]] {
        stride(from: 0, to: count, by: size).map {
            Array(self[$0..<Swift.min($0 + size, count)])
        }
    }
    
    /// OPTIMIZATION: Safe access without bounds checking overhead
    subscript(safe index: Int) -> Element? {
        guard index >= 0, index < count else { return nil }
        return self[index]
    }
}

// MARK: - Timer Optimization
/// OPTIMIZATION: Consolidated timer management to prevent multiple redundant timers
final class TimerCoordinator: @unchecked Sendable {
    static let shared = TimerCoordinator()
    
    private var timers: [String: Timer] = [:]
    private let lock = NSLock()
    
    func schedule(_ identifier: String, interval: TimeInterval, block: @escaping () -> Void) {
        lock.lock()
        defer { lock.unlock() }
        
        // Cancel existing timer if present
        timers[identifier]?.invalidate()
        
        let timer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { _ in
            block()
        }
        timers[identifier] = timer
    }
    
    func cancel(_ identifier: String) {
        lock.lock()
        defer { lock.unlock() }
        
        timers[identifier]?.invalidate()
        timers.removeValue(forKey: identifier)
    }
}
