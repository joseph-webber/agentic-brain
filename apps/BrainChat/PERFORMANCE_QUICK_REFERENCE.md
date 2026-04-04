# BrainChat Performance Optimization - Quick Reference

## 📊 Target Metrics & Status

| Metric | Current | Target | Gap | Status |
|--------|---------|--------|-----|--------|
| **Startup Time** | 800-1200ms | <500ms | -300-700ms | 🔴 |
| **Memory Baseline** | 120-150MB | <100MB | -20-50MB | 🔴 |
| **UI @ 60fps** | 30-40% drops | <5% drops | -25-35% | 🟠 |

## ⚡ Quick Wins (Implement First)

### 1. Defer BridgeDaemon (150-200ms saved)
**File**: `BrainChat.swift:58`
```swift
// BEFORE
BridgeDaemon.shared.startIfNeeded()

// AFTER  
Task.detached {
    BridgeDaemon.shared.startIfNeeded()
}
```

### 2. Defer Microphone Permission (100-150ms saved)
**File**: `BrainChat.swift:64`
```swift
// BEFORE
requestMicrophonePermission()

// AFTER
Task.detached { [weak self] in
    self?.requestMicrophonePermission()
}
```

### 3. Add Lazy Initialization (7-12MB saved)
**File**: `SpeechManager.swift:253`
```swift
// BEFORE
private var whisperCppEngine: WhisperCppEngine?

// AFTER
private lazy var whisperCppEngine = WhisperCppEngine()
```

**File**: `LLMRouter.swift:205-212`
```swift
// BEFORE
private let claudeAPI: any ClaudeStreaming = ClaudeAPI()

// AFTER
private lazy var claudeAPI: any ClaudeStreaming = ClaudeAPI()
```

## 📈 Medium Effort (Implement Next)

### 4. Message Pruning (20-30MB saved)
**File**: `Models.swift` - Add to `ConversationStore`:
```swift
func pruneOldMessages(keepRecent: Int = 50) {
    guard messages.count > keepRecent else { return }
    let systemMessages = messages.filter { $0.role == .system }
    let recentMessages = Array(messages.filter { $0.role != .system }.suffix(keepRecent))
    messages = systemMessages + recentMessages
}
```

Call periodically:
```swift
if messages.count > 100 {
    pruneOldMessages(keepRecent: 50)
}
```

### 5. Message Pagination (30-40% frame improvement)
**File**: `Models.swift` - Add to `ConversationStore`:
```swift
func pagedMessages(pageSize: Int = 20, page: Int = 0) -> [ChatMessage] {
    let start = page * pageSize
    let end = min(start + pageSize, messages.count)
    guard start < messages.count else { return [] }
    return Array(messages[start..<end])
}
```

**File**: `ConversationView.swift` - Update rendering:
```swift
// BEFORE: Renders ALL messages
ForEach(store.messages, id: \.id) { message in
    MessageBubble(message: message)
}

// AFTER: Renders only visible page
@State private var currentPage = 0
ForEach(store.pagedMessages(page: currentPage), id: \.id) { message in
    MessageBubble(message: message)
}
.onChange(of: store.messages.count) { _, _ in
    currentPage = 0  // Reset on new message
}
```

## 🚀 Performance Profiler Usage

### Basic Setup (AppDelegate)
```swift
import Foundation

let profiler = PerformanceProfiler.shared

// Track startup phases
profiler.markInitStart("Phase Name")
// ... do work ...
profiler.markInitEnd("Phase Name")

// Capture memory
profiler.captureMemorySnapshot("Checkpoint")

// Generate report
profiler.printSummary()
```

### Integration Points

**Startup Measurement**:
```swift
func applicationDidFinishLaunching(_ notification: Notification) {
    let profiler = PerformanceProfiler.shared
    profiler.markInitStart("AppDelegate.startup")
    
    // Setup code...
    
    profiler.markInitEnd("AppDelegate.startup")
}
```

**Memory Tracking**:
```swift
profiler.captureMemorySnapshot("After Init")
profiler.captureMemorySnapshot("After Load")

// Get delta
if let delta = profiler.memoryDelta(from: "After Init", to: "After Load") {
    print("Memory delta: \(delta / 1024 / 1024)MB")
}
```

**UI Frame Tracking**:
```swift
CADisplayLink { displayLink in
    profiler.trackFrameDuration(displayLink.duration, operation: "Rendering")
}
```

## 📋 Implementation Checklist

### Phase 1: Setup (30 min)
- [ ] Add `PerformanceProfiler.swift` to project
- [ ] Add profiler imports to `BrainChat.swift`
- [ ] Run baseline measurements

### Phase 2: Quick Wins (1 hour)
- [ ] Defer BridgeDaemon initialization
- [ ] Defer microphone permission request
- [ ] Add lazy initialization to managers
- [ ] Verify startup time improvement

### Phase 3: Memory Optimization (1-2 hours)
- [ ] Add message pruning function
- [ ] Call pruning periodically
- [ ] Monitor memory snapshots
- [ ] Verify memory baseline improvement

### Phase 4: UI Optimization (2-3 hours)
- [ ] Implement message pagination
- [ ] Update ConversationView rendering
- [ ] Profile scroll performance
- [ ] Verify frame drop reduction

### Phase 5: Background Tasks (2-3 hours)
- [ ] Use `Task.detached` for heavy work
- [ ] Move parsing to background thread
- [ ] Update UI only on @MainActor
- [ ] Profile response latency

## 🧪 Testing & Validation

### Startup Test
```swift
let start = Date()
// App launches...
let duration = Date().timeIntervalSince(start)
print(duration < 0.4 ? "✅ OK" : "❌ TOO SLOW")  // Target: <400ms
```

### Memory Test
```swift
profiler.captureMemorySnapshot("Start")
// Generate 1000 messages...
profiler.captureMemorySnapshot("After1000")
// Check: Should be <100MB total
```

### Frame Test
```swift
// Scroll through messages, watch console output
// Should see: "Dropped frame" count < 5%
```

## 📊 Expected Results

### Startup Time
- **Current**: 800-1200ms
- **Target**: <500ms ✅
- **Expected**: 300-400ms ✅✅

### Memory Baseline  
- **Current**: 120-150MB
- **Target**: <100MB ✅
- **Expected**: 60-80MB ✅✅

### UI Responsiveness
- **Current**: 60fps with 30-40% drops
- **Target**: 60fps with <5% drops ✅
- **Expected**: 60fps with 98%+ maintained ✅✅

## 🔧 Optimization Patterns

### Lazy Initialization
```swift
private lazy var expensiveResource = ExpensiveClass()
// Only allocated when first accessed
```

### Background Task
```swift
Task.detached { [weak self] in
    let result = heavyComputation()
    Task { @MainActor in
        self?.updateUI(result)
    }
}
```

### Message Pruning
```swift
if messages.count > threshold {
    pruneOldMessages(keepRecent: 50)
}
```

### Memory Snapshot
```swift
let bytes = profiler.captureMemorySnapshot("Checkpoint")
let mb = Double(bytes) / (1024 * 1024)
print("Memory: \(mb)MB")
```

## 📞 Common Issues & Solutions

### Issue: Startup still slow after deferring BridgeDaemon
**Solution**: Check if other sync work still on main thread
```swift
// Use profiler to identify bottleneck
profiler.markInitStart("Suspect")
// suspicious code here
profiler.markInitEnd("Suspect")
```

### Issue: Memory still high after pruning
**Solution**: Check for lingering references
- Look for circular references in models
- Use Xcode Instruments → Allocations
- Check for retained closures

### Issue: Still dropping frames during scroll
**Solution**: Add pagination + batch updates
- Use `ViewRenderingOptimizer.batchUpdates {}`
- Reduce render complexity with smaller pages
- Profile with Xcode Instruments → Core Animation

## 📚 Reference Files

- `PerformanceProfiler.swift` - Measurement utility (200 lines)
- `PerformanceOptimizations.swift` - Helper patterns (250 lines)
- `BrainChat-Optimized.swift` - Reference implementation
- `PERFORMANCE_OPTIMIZATION_GUIDE.md` - Detailed guide
- `benchmarks/performance-report.md` - Full analysis

## 🎯 Success Criteria

✅ **Startup**: App ready in <400ms (measure with profiler)
✅ **Memory**: Baseline <80MB (check after init)
✅ **UI**: Maintain 60fps during scroll (watch for drops)

---

**Next Steps**:
1. Review `PERFORMANCE_OPTIMIZATION_GUIDE.md` for details
2. Start with Quick Wins (Phase 2)
3. Use PerformanceProfiler to measure improvements
4. Proceed to Phase 3-5 as needed

**Questions?** Check the full report in `benchmarks/performance-report.md`
