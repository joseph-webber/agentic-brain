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
                    .foregroundColor(.accentColor)
                    .frame(width: 20)
                    .accessibilityHidden(true)

                Picker(selection: $router.selectedProvider) {
                    ForEach(LLMProvider.allCases) { provider in
                        Text(provider.shortName).tag(provider)
                    }
                } label: {
                    Text("LLM")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .pickerStyle(.menu)
                .accessibilityLabel("Select AI provider")
                .accessibilityHint("Choose which large language model Brain Chat should prefer before the bridge applies routing rules.")
                .accessibilityValue(router.selectedProvider.rawValue)
            }

            if router.yoloMode {
                HStack(spacing: 4) {
                    Image(systemName: "bolt.fill")
                        .font(.system(size: 9))
                        .accessibilityHidden(true)
                    Text("YOLO")
                        .font(.system(size: 9, weight: .heavy))
                }
                .foregroundColor(.white)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Color.orange)
                .clipShape(Capsule())
                .accessibilityLabel("YOLO autonomous mode active")
            }
        }
    }
}
