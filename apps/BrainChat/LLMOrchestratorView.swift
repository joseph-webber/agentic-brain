import SwiftUI

/// A SwiftUI view for LLM orchestration settings.
/// Fully keyboard accessible for VoiceOver users.
struct LLMOrchestratorView: View {
    @ObservedObject var orchestrator = LLMOrchestrator.shared
    
    var body: some View {
        Form {
            // MARK: - Mode Selection
            Section {
                Picker("Orchestration Mode", selection: $orchestrator.mode) {
                    ForEach(LLMMode.allCases) { mode in
                        Label(mode.displayName, systemImage: mode.iconName)
                            .tag(mode)
                    }
                }
                .pickerStyle(.segmented)
                .accessibilityLabel("LLM Orchestration Mode")
                .accessibilityHint("Choose single LLM, multi-bot, or consensus mode")
                
                Text(orchestrator.mode.accessibilityDescription)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .accessibilityHidden(true)
            } header: {
                Text("Mode")
            }
            
            // MARK: - Primary LLM
            Section {
                Picker("Primary LLM", selection: $orchestrator.primaryLLM) {
                    ForEach(LLMProvider.allCases) { provider in
                        HStack {
                            Image(systemName: provider.iconName)
                            Text(provider.rawValue)
                            if provider.isFree {
                                Text("Free")
                                    .font(.caption2)
                                    .foregroundColor(.green)
                            }
                        }
                        .tag(provider)
                    }
                }
                .accessibilityLabel("Primary LLM Provider")
                .accessibilityHint("The main LLM that handles queries or orchestrates others")
            } header: {
                Text("Primary Provider")
            } footer: {
                Text("In single mode, all queries go to this provider. In multi-bot mode, this provider decides which secondary LLM to use.")
            }
            
            // MARK: - Secondary LLMs (only shown in multi-bot/consensus mode)
            if orchestrator.mode != .single {
                Section {
                    ForEach(LLMProvider.allCases) { provider in
                        if provider != orchestrator.primaryLLM {
                            Toggle(isOn: Binding(
                                get: { orchestrator.secondaryLLMs.contains(provider) },
                                set: { enabled in
                                    if enabled {
                                        _ = orchestrator.addSecondaryLLM(provider.rawValue)
                                    } else {
                                        _ = orchestrator.removeSecondaryLLM(provider.rawValue)
                                    }
                                }
                            )) {
                                HStack {
                                    Image(systemName: provider.iconName)
                                    Text(provider.rawValue)
                                    Spacer()
                                    if provider.isFree {
                                        Text("Free")
                                            .font(.caption2)
                                            .foregroundColor(.green)
                                    } else {
                                        Text(provider.displayPricing)
                                            .font(.caption2)
                                            .foregroundColor(.secondary)
                                    }
                                }
                            }
                            .accessibilityLabel("Enable \(provider.shortName) as secondary")
                            .accessibilityHint(provider.isFree ? "This provider is free" : "This provider costs money")
                        }
                    }
                } header: {
                    Text("Secondary Providers")
                } footer: {
                    if orchestrator.mode == .multiBot {
                        Text("The primary LLM can delegate tasks to these providers based on the request type.")
                    } else {
                        Text("All enabled providers will be queried and their responses synthesized into a consensus.")
                    }
                }
            }
            
            // MARK: - Status
            Section {
                HStack {
                    Text("Status")
                    Spacer()
                    Text(orchestrator.statusMessage)
                        .foregroundColor(.secondary)
                }
                .accessibilityElement(children: .combine)
                .accessibilityLabel("Status: \(orchestrator.statusMessage)")
                
                HStack {
                    Text("Configuration")
                    Spacer()
                    Text(orchestrator.getStatus())
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .accessibilityElement(children: .combine)
            } header: {
                Text("Current State")
            }
        }
        .formStyle(.grouped)
    }
}

/// A compact inline view for LLM mode selection.
/// Can be embedded in other views like SettingsView.
struct LLMModeSelector: View {
    @ObservedObject var orchestrator = LLMOrchestrator.shared
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Picker("Mode", selection: $orchestrator.mode) {
                    ForEach(LLMMode.allCases) { mode in
                        Text(mode.displayName).tag(mode)
                    }
                }
                .pickerStyle(.segmented)
                .accessibilityLabel("LLM mode")
                
                Picker("Primary", selection: $orchestrator.primaryLLM) {
                    ForEach(LLMProvider.allCases) { provider in
                        Text(provider.shortName).tag(provider)
                    }
                }
                .frame(maxWidth: 150)
                .accessibilityLabel("Primary LLM provider")
            }
            
            if orchestrator.mode != .single {
                HStack(spacing: 4) {
                    Text("Secondary:")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    ForEach(LLMProvider.allCases.filter { $0 != orchestrator.primaryLLM }) { provider in
                        Toggle(isOn: Binding(
                            get: { orchestrator.secondaryLLMs.contains(provider) },
                            set: { enabled in
                                if enabled {
                                    _ = orchestrator.addSecondaryLLM(provider.rawValue)
                                } else {
                                    _ = orchestrator.removeSecondaryLLM(provider.rawValue)
                                }
                            }
                        )) {
                            Text(provider.shortName)
                                .font(.caption)
                        }
                        .toggleStyle(.button)
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                        .accessibilityLabel("Toggle \(provider.shortName)")
                    }
                }
            }
        }
    }
}

#Preview("LLM Orchestrator Settings") {
    LLMOrchestratorView()
        .frame(width: 450, height: 600)
}

#Preview("LLM Mode Selector") {
    LLMModeSelector()
        .padding()
        .frame(width: 500)
}
