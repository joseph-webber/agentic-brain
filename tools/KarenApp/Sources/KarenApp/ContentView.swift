import SwiftUI

struct ContentView: View {
    @ObservedObject var manager: VoiceChatManager

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            header
            statusCard
            waveformCard
            controls
            accessibilitySummary
        }
        .padding(28)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Color(nsColor: .windowBackgroundColor))
        .onAppear {
            manager.refreshAuthorizationState()
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Karen Voice Chat")
                .font(.system(size: 30, weight: .bold))
                .accessibilityAddTraits(.isHeader)

            Text("A native macOS app for starting Karen's Python voice chat with clear microphone permission handling.")
                .font(.title3)
                .foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Karen Voice Chat. Native Mac application for starting Karen voice chat with microphone access.")
    }

    private var statusCard: some View {
        VStack(alignment: .leading, spacing: 18) {
            Label("Current Status", systemImage: "waveform.circle.fill")
                .font(.headline)
                .accessibilityAddTraits(.isHeader)

            HStack(alignment: .center, spacing: 16) {
                Circle()
                    .fill(manager.status.color)
                    .frame(width: 18, height: 18)
                    .overlay(Circle().stroke(Color.primary.opacity(0.15), lineWidth: 1))
                    .accessibilityHidden(true)

                VStack(alignment: .leading, spacing: 4) {
                    Text(manager.status.title)
                        .font(.title2.weight(.semibold))
                    Text(manager.detailText)
                        .font(.body)
                        .foregroundStyle(.secondary)
                    Text("Microphone permission: \(manager.permissionSummary)")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Spacer(minLength: 0)
            }
        }
        .padding(20)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(manager.status.color.opacity(0.35), lineWidth: 1)
        )
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Status")
        .accessibilityValue("\(manager.status.title). \(manager.detailText). Microphone permission is \(manager.permissionSummary).")
    }

    private var waveformCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            Label("Activity", systemImage: "chart.bar.fill")
                .font(.headline)
                .accessibilityAddTraits(.isHeader)

            HStack(alignment: .bottom, spacing: 10) {
                ForEach(Array(manager.status.waveHeights.enumerated()), id: \.offset) { index, height in
                    RoundedRectangle(cornerRadius: 6, style: .continuous)
                        .fill(manager.status.color.opacity(index.isMultiple(of: 2) ? 0.85 : 0.55))
                        .frame(width: 28, height: height)
                        .animation(.easeInOut(duration: 0.35), value: manager.status)
                        .accessibilityHidden(true)
                }
            }
            .frame(maxWidth: .infinity, minHeight: 120, alignment: .center)
            .padding(.vertical, 12)
            .background(Color.primary.opacity(0.04), in: RoundedRectangle(cornerRadius: 16, style: .continuous))

            Text(manager.status.accessibilityDescription)
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding(20)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Voice activity visualisation")
        .accessibilityValue(manager.status.accessibilityDescription)
    }

    private var controls: some View {
        VStack(alignment: .leading, spacing: 14) {
            Button(action: {
                manager.primaryAction()
            }) {
                HStack {
                    Image(systemName: manager.isRunning ? "stop.circle.fill" : "mic.circle.fill")
                        .font(.system(size: 24, weight: .bold))
                    Text(manager.isRunning ? "Stop Chat" : "Start Chat")
                        .font(.system(size: 24, weight: .bold))
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 18)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .keyboardShortcut(.defaultAction)
            .accessibilityLabel(manager.isRunning ? "Stop chat" : "Start chat")
            .accessibilityHint(manager.isRunning ? "Stops Karen's background voice chat process." : "Requests microphone access if needed, then starts Karen's Python voice chat in the background.")

            HStack(spacing: 12) {
                Button("Open Microphone Settings") {
                    manager.openMicrophoneSettings()
                }
                .buttonStyle(.bordered)
                .accessibilityHint("Opens System Settings to the microphone privacy section.")

                if manager.isRunning {
                    Text("Background process is running.")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .accessibilityLabel("Background process is running")
                }
            }
        }
    }

    private var accessibilitySummary: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Latest Event")
                .font(.headline)
                .accessibilityAddTraits(.isHeader)
            Text(manager.latestEvent)
                .font(.body.monospaced())
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(14)
                .background(Color.primary.opacity(0.05), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                .accessibilityLabel("Latest event log")
                .accessibilityValue(manager.latestEvent)
        }
    }
}
