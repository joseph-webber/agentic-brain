import SwiftUI
import Combine

// =============================================================================
// YoloMode - Autonomous coding mode for BrainChat
// Toggle /yolo on/off, visual indicators, voice commands, LLM system prompts
// Karen announces every action. Safety limits enforced via SafetyGuard.
// =============================================================================

// MARK: - YOLO State

@MainActor
final class YoloMode: ObservableObject {
    static let shared = YoloMode()

    @Published var isActive = false
    @Published var session: YoloSession?
    @Published var pendingConfirmation: ConfirmationRequest?
    @Published var actionsFeed: [ActionFeedItem] = []

    let executor = YoloExecutor()
    private let system = SystemCommands.shared
    private let safety = SafetyGuard.shared

    /// Maximum actions per YOLO session (configurable)
    var maxActionsPerSession: Int = 50

    // MARK: - Activate / Deactivate

    /// Enable YOLO mode. Karen announces activation.
    func activate() {
        guard !isActive else { return }
        isActive = true
        let newSession = YoloSession(maxActions: maxActionsPerSession)
        session = newSession
        actionsFeed.removeAll()

        // Audio cue: activation
        playActivationSound()
        speak("YOLO mode activated. I will execute actions autonomously. \(maxActionsPerSession) actions available.")

        addFeedItem(icon: "⚡", text: "YOLO mode activated", type: .system)
    }

    /// Disable YOLO mode. Karen announces deactivation with session summary.
    func deactivate() {
        guard isActive else { return }

        let stats = session?.statistics
        session?.end()

        isActive = false

        // Audio cue: deactivation
        playDeactivationSound()

        if let stats = stats {
            speak(stats.spokenSummary)
            addFeedItem(icon: "🛑", text: "YOLO mode off. \(stats.spokenSummary)", type: .system)
        } else {
            speak("YOLO mode deactivated.")
            addFeedItem(icon: "🛑", text: "YOLO mode deactivated", type: .system)
        }

        session = nil
    }

    /// Toggle YOLO mode on/off.
    func toggle() {
        if isActive { deactivate() } else { activate() }
    }

    // MARK: - Process AI Response

    /// Process an AI response for YOLO commands. Parses and executes action blocks.
    /// Returns a summary of what was executed.
    func processAIResponse(_ response: String) async -> String {
        guard isActive, let session = session else {
            return "YOLO mode is not active."
        }

        let commands = YoloCommand.parse(from: response)
        guard !commands.isEmpty else {
            return "No executable actions found in response."
        }

        speak("Found \(commands.count) actions to execute.")
        addFeedItem(icon: "🔍", text: "Parsed \(commands.count) actions", type: .info)

        var summaryLines: [String] = []

        for (index, command) in commands.enumerated() {
            speak(command.description)
            addFeedItem(
                icon: iconFor(command.category),
                text: command.description,
                type: .action
            )

            let result = await executor.execute(
                command: command,
                session: session,
                confirmationHandler: { [weak self] reason in
                    await self?.requestConfirmation(reason: reason) ?? false
                }
            )

            if result.success {
                let msg = "[\(index + 1)/\(commands.count)] ✅ \(command.description)"
                summaryLines.append(msg)
                updateLastFeedItem(success: true)
            } else {
                let msg = "[\(index + 1)/\(commands.count)] ❌ \(result.output)"
                summaryLines.append(msg)
                updateLastFeedItem(success: false)

                // Stop batch on critical failure
                if command.category == .fileCreate || command.category == .fileEdit {
                    speak("Stopping due to file operation failure.")
                    break
                }
            }
        }

        let summary = summaryLines.joined(separator: "\n")
        speak("Finished. \(commands.count) actions processed.")
        return summary
    }

    // MARK: - Voice Command Handling

    /// Handle voice commands related to YOLO mode.
    /// Returns true if the input was a YOLO voice command that was handled.
    func handleVoiceCommand(_ input: String) -> Bool {
        let lower = input.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)

        // Activation commands
        if matchesActivation(lower) {
            activate()
            return true
        }

        // Deactivation commands
        if matchesDeactivation(lower) {
            deactivate()
            return true
        }

        // Undo command
        if matchesUndo(lower) {
            handleUndo()
            return true
        }

        // Status / "what did you do?"
        if matchesStatus(lower) {
            handleStatus()
            return true
        }

        // Recover from error
        if matchesRecover(lower) {
            handleRecover()
            return true
        }

        return false
    }

    // MARK: - Voice Pattern Matching

    private func matchesActivation(_ input: String) -> Bool {
        let patterns = [
            "enable yolo", "yolo on", "yolo mode", "activate yolo",
            "start yolo", "go yolo", "/yolo", "enter yolo",
        ]
        return patterns.contains { input.contains($0) }
    }

    private func matchesDeactivation(_ input: String) -> Bool {
        let patterns = [
            "yolo off", "disable yolo", "deactivate yolo", "stop yolo",
            "exit yolo", "end yolo", "cancel yolo",
        ]
        return patterns.contains { input.contains($0) }
    }

    private func matchesUndo(_ input: String) -> Bool {
        let patterns = [
            "undo last action", "undo last", "undo that", "revert",
            "take that back", "roll back", "undo",
        ]
        return patterns.contains { input.contains($0) }
    }

    private func matchesStatus(_ input: String) -> Bool {
        let patterns = [
            "what did you do", "yolo status", "yolo report", "show actions",
            "list actions", "what happened", "action log", "audit log",
        ]
        return patterns.contains { input.contains($0) }
    }

    private func matchesRecover(_ input: String) -> Bool {
        let patterns = [
            "recover", "fix that error", "recover from error",
            "repair", "fix it",
        ]
        return patterns.contains { input.contains($0) }
    }

    // MARK: - Voice Command Handlers

    private func handleUndo() {
        guard let session = session else {
            speak("No active YOLO session.")
            return
        }

        if let result = session.undoLastAction() {
            speak(result)
            addFeedItem(icon: "↩️", text: result, type: .undo)
        } else {
            speak("Nothing to undo.")
        }
    }

    private func handleStatus() {
        guard let session = session else {
            speak("No active YOLO session.")
            return
        }

        let report = session.actionReport()
        speak(session.statistics.spokenSummary)
        addFeedItem(icon: "📊", text: session.statistics.spokenSummary, type: .info)

        // Also log to system message
        print(report)
    }

    private func handleRecover() {
        guard let session = session else {
            speak("No active YOLO session.")
            return
        }

        let result = session.recoverFromError()
        speak(result)
        addFeedItem(icon: "🔧", text: result, type: .system)
    }

    // MARK: - Confirmation Dialog

    struct ConfirmationRequest: Identifiable {
        let id = UUID()
        let reason: String
        var continuation: CheckedContinuation<Bool, Never>?
    }

    private func requestConfirmation(reason: String) async -> Bool {
        return await withCheckedContinuation { continuation in
            pendingConfirmation = ConfirmationRequest(
                reason: reason,
                continuation: continuation
            )
        }
    }

    func confirmAction(_ confirmed: Bool) {
        pendingConfirmation?.continuation?.resume(returning: confirmed)
        pendingConfirmation = nil
    }

    // MARK: - LLM System Prompts for YOLO Mode

    /// System prompt addition when YOLO mode is active.
    /// Append this to the LLM system prompt so it knows to emit action blocks.
    static let yoloSystemPrompt = """
    YOLO MODE IS ACTIVE. You are operating in autonomous execution mode.

    When the user asks you to do something, emit executable action blocks using this format:

    ```yolo
    ACTION: create_file
    PATH: ~/brain/path/to/file.py
    DESC: Create utility module
    CONTENT:
    def hello():
        print("hello world")
    ```

    Available actions:
    - create_file: Create a new file (requires PATH and CONTENT)
    - edit_file: Replace file contents (requires PATH and CONTENT)
    - delete_file: Move file to trash (requires PATH)
    - shell: Run a shell command (requires COMMAND)
    - git: Run a git command (requires COMMAND)
    - generate: Generate and save code (requires PATH and CONTENT)

    You can include multiple action blocks in one response.
    For shell commands, you can also use inline format: $ command_here

    Rules:
    - Always explain what you're doing before the action blocks
    - File paths should be absolute or use ~/
    - Keep file content complete (not truncated)
    - Prefer safe operations (create > delete, branch > main)
    - After actions, explain what was done and suggest next steps

    Karen will announce each action as it executes.
    Safety guard will block dangerous operations automatically.
    """

    /// Per-provider YOLO prompt adjustments.
    static func yoloPrompt(for provider: String) -> String {
        let base = yoloSystemPrompt

        switch provider.lowercased() {
        case "copilot":
            return base + """

            You are GitHub Copilot in YOLO mode. Use your code expertise to:
            - Generate production-quality code with proper error handling
            - Follow existing project conventions
            - Include type annotations and documentation
            - Run tests after code changes when possible
            """

        case "claude":
            return base + """

            You are Claude in YOLO autonomous mode. Approach tasks methodically:
            - Plan the sequence of actions before executing
            - Create files in dependency order
            - Validate paths and imports
            - Suggest follow-up actions after completion
            """

        case "gpt", "openai":
            return base + """

            You are GPT in YOLO autonomous mode. Be efficient and precise:
            - Emit minimal, correct action blocks
            - Use descriptive filenames and paths
            - Include inline comments for complex logic
            - Batch related file operations together
            """

        default:
            return base + """

            You are in YOLO autonomous mode. Execute actions directly:
            - Use the action block format above
            - Keep responses focused on actions
            - Explain briefly, then act
            """
        }
    }

    // MARK: - Action Feed (for UI)

    struct ActionFeedItem: Identifiable {
        let id = UUID()
        let timestamp = Date()
        let icon: String
        let text: String
        let type: FeedItemType
        var succeeded: Bool?

        enum FeedItemType {
            case action, system, info, undo, error
        }
    }

    private func addFeedItem(icon: String, text: String, type: ActionFeedItem.FeedItemType) {
        let item = ActionFeedItem(icon: icon, text: text, type: type)
        actionsFeed.append(item)
        // Keep feed manageable
        if actionsFeed.count > 100 {
            actionsFeed.removeFirst(actionsFeed.count - 100)
        }
    }

    private func updateLastFeedItem(success: Bool) {
        guard !actionsFeed.isEmpty else { return }
        actionsFeed[actionsFeed.count - 1].succeeded = success
    }

    private func iconFor(_ category: ActionCategory) -> String {
        switch category {
        case .fileCreate:   return "📄"
        case .fileEdit:     return "✏️"
        case .fileDelete:   return "🗑️"
        case .shellCommand: return "💻"
        case .gitOperation: return "🔀"
        case .codeGenerate: return "🧬"
        case .appLaunch:    return "🚀"
        case .network:      return "🌐"
        case .system:       return "⚙️"
        }
    }

    // MARK: - Audio Cues

    private func playActivationSound() {
        // Quick ascending tone for activation
        _ = try? system.run(
            "afplay /System/Library/Sounds/Blow.aiff &",
            timeout: 5
        )
    }

    private func playDeactivationSound() {
        // Descending tone for deactivation
        _ = try? system.run(
            "afplay /System/Library/Sounds/Bottle.aiff &",
            timeout: 5
        )
    }

    private func speak(_ text: String) {
        system.speak(text, voice: "Karen (Premium)", rate: 160)
    }
}

// MARK: - YOLO Mode SwiftUI View Components

/// Status indicator showing YOLO mode state. Displays ⚡ when active.
struct YoloStatusBadge: View {
    @ObservedObject var yolo: YoloMode

    var body: some View {
        if yolo.isActive {
            HStack(spacing: 4) {
                Image(systemName: "bolt.fill")
                    .foregroundColor(.yellow)
                    .symbolEffect(.pulse, isActive: yolo.executor.isExecuting)
                Text("YOLO")
                    .font(.caption.bold())
                    .foregroundColor(.yellow)
                if let session = yolo.session {
                    Text("[\(session.actionsRemaining)]")
                        .font(.caption2)
                        .foregroundColor(.yellow.opacity(0.7))
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(
                Capsule()
                    .fill(Color.yellow.opacity(0.15))
                    .overlay(
                        Capsule()
                            .strokeBorder(Color.yellow.opacity(0.4), lineWidth: 1)
                    )
            )
            .accessibilityElement(children: .combine)
            .accessibilityLabel(
                "YOLO mode active. \(yolo.session?.actionsRemaining ?? 0) actions remaining."
            )
            .accessibilityHint("Double-tap to deactivate YOLO mode.")
            .onTapGesture { yolo.deactivate() }
        }
    }
}

/// Toggle button for YOLO mode, suitable for toolbar or settings.
struct YoloToggleButton: View {
    @ObservedObject var yolo: YoloMode

    var body: some View {
        Button(action: { yolo.toggle() }) {
            HStack(spacing: 4) {
                Image(systemName: yolo.isActive ? "bolt.fill" : "bolt.slash")
                Text(yolo.isActive ? "YOLO On" : "YOLO Off")
                    .font(.caption)
            }
        }
        .buttonStyle(.bordered)
        .tint(yolo.isActive ? .yellow : .secondary)
        .accessibilityLabel(
            yolo.isActive
                ? "Deactivate YOLO mode"
                : "Activate YOLO autonomous coding mode"
        )
        .accessibilityHint(
            yolo.isActive
                ? "Currently active with \(yolo.session?.actionsRemaining ?? 0) actions remaining"
                : "Enables AI to execute actions without confirmation"
        )
    }
}

/// Confirmation dialog for actions that need user approval.
struct YoloConfirmationDialog: View {
    @ObservedObject var yolo: YoloMode

    var body: some View {
        if let request = yolo.pendingConfirmation {
            VStack(spacing: 12) {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.orange)
                    Text("Confirmation Required")
                        .font(.headline)
                }

                Text(request.reason)
                    .font(.body)
                    .multilineTextAlignment(.center)
                    .foregroundColor(.secondary)

                HStack(spacing: 16) {
                    Button("Deny") { yolo.confirmAction(false) }
                        .buttonStyle(.bordered)
                        .tint(.red)
                        .accessibilityLabel("Deny this action")

                    Button("Allow") { yolo.confirmAction(true) }
                        .buttonStyle(.borderedProminent)
                        .tint(.green)
                        .accessibilityLabel("Allow this action to proceed")
                }
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color(nsColor: .controlBackgroundColor))
                    .shadow(radius: 4)
            )
            .accessibilityElement(children: .contain)
            .accessibilityLabel("YOLO confirmation dialog. \(request.reason)")
        }
    }
}

/// Live action feed showing YOLO session progress.
struct YoloActionFeed: View {
    @ObservedObject var yolo: YoloMode

    private let timeFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "HH:mm:ss"
        return f
    }()

    var body: some View {
        if yolo.isActive && !yolo.actionsFeed.isEmpty {
            ScrollViewReader { proxy in
                ScrollView(.vertical, showsIndicators: true) {
                    LazyVStack(alignment: .leading, spacing: 4) {
                        ForEach(yolo.actionsFeed) { item in
                            HStack(alignment: .top, spacing: 6) {
                                Text(item.icon)
                                    .font(.caption)
                                VStack(alignment: .leading, spacing: 1) {
                                    Text(item.text)
                                        .font(.caption)
                                        .foregroundColor(colorFor(item))
                                    Text(timeFormatter.string(from: item.timestamp))
                                        .font(.caption2)
                                        .foregroundColor(.secondary)
                                }
                                Spacer()
                                if let success = item.succeeded {
                                    Image(systemName: success ? "checkmark.circle" : "xmark.circle")
                                        .foregroundColor(success ? .green : .red)
                                        .font(.caption)
                                }
                            }
                            .id(item.id)
                            .accessibilityElement(children: .combine)
                            .accessibilityLabel(
                                "\(item.icon) \(item.text). \(item.succeeded == true ? "Succeeded" : item.succeeded == false ? "Failed" : "")"
                            )
                        }
                    }
                    .padding(.horizontal, 8)
                }
                .frame(maxHeight: 200)
                .background(Color.black.opacity(0.05))
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .onChange(of: yolo.actionsFeed.count) {
                    if let last = yolo.actionsFeed.last {
                        withAnimation {
                            proxy.scrollTo(last.id, anchor: .bottom)
                        }
                    }
                }
            }
        }
    }

    private func colorFor(_ item: YoloMode.ActionFeedItem) -> Color {
        switch item.type {
        case .action: return .primary
        case .system: return .blue
        case .info:   return .secondary
        case .undo:   return .orange
        case .error:  return .red
        }
    }
}
