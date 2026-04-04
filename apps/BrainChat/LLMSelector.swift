// LLMSelector.swift - Compact provider picker for BrainChat

import SwiftUI

struct LLMSelector: View {
    @EnvironmentObject var router: LLMRouter
    @EnvironmentObject var settings: AppSettings

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                Image(systemName: router.selectedProvider.iconName)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(router.selectedProvider.isFree ? .green : .accentColor)
                    .frame(width: 20)
                    .accessibilityHidden(true)

                Picker(selection: $router.selectedProvider) {
                    ForEach(LLMProvider.allCases) { provider in
                        Label {
                            HStack {
                                Text(provider.shortName)
                                Spacer()
                                Text(provider.displayPricing)
                                    .font(.caption2)
                                    .foregroundColor(provider.isFree ? .green : .secondary)
                            }
                        } icon: {
                            Image(systemName: provider.iconName)
                        }
                        .tag(provider)
                    }
                } label: {
                    Text("LLM")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .pickerStyle(.menu)
                .accessibilityLabel("Select AI provider")
                .accessibilityHint("Choose which large language model Brain Chat should prefer. Free providers are listed first.")
                .accessibilityValue("\(router.selectedProvider.rawValue), \(router.selectedProvider.displayPricing)")
            }

            HStack(spacing: 4) {
                if router.selectedProvider.isFree {
                    Image(systemName: "checkmark.seal.fill")
                        .font(.system(size: 9))
                        .foregroundColor(.green)
                        .accessibilityHidden(true)
                    Text("Free")
                        .font(.system(size: 9, weight: .medium))
                        .foregroundColor(.green)
                        .accessibilityLabel("Free provider")
                }

                if router.yoloMode {
                    Image(systemName: "bolt.fill")
                        .font(.system(size: 9))
                        .accessibilityHidden(true)
                    Text("YOLO")
                        .font(.system(size: 9, weight: .heavy))
                }
            }
            .foregroundColor(router.yoloMode ? .white : .primary)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(router.yoloMode ? Color.orange : Color.clear)
            .clipShape(Capsule())
            .accessibilityLabel(router.yoloMode ? "YOLO autonomous mode active" : "")
        }
    }
}
