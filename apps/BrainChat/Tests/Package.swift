// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "BrainChatE2E",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .library(name: "BrainChatLib", targets: ["BrainChatLib"])
    ],
    targets: [
        .target(
            name: "BrainChatLib",
            path: "Sources/BrainChatLib",
            sources: [
                "BrainChatLib.swift",
                "EventTypes.swift",
                "MockURLProtocol.swift",
                "PandaproxyClient.swift",
                "RedpandaBridge.swift"
            ]
        ),
        .testTarget(
            name: "BrainChatE2ETests",
            dependencies: ["BrainChatLib"],
            path: ".",
            sources: [
                // LLM client unit tests
                "AIManagerTests.swift",
                "CopilotBridgeTests.swift",
                "IntegrationTests.swift",
                "SpeechManagerTests.swift",
                "VoiceManagerTests.swift",
                "TestOrchestrator.swift",
                "E2EConversationTests.swift",
                "E2ECodingTests.swift",
                "E2EYoloTests.swift",
                "E2EMultiLLMTests.swift",
                // Event bus
                // "RedpandaBridgeTests.swift",  // TODO: needs subscribeToResponses API
                "RedpandaIntegrationTests.swift",
                // Speech input (STT)
                "SpeechEngineTests.swift",
                // Voice output (TTS) — CRITICAL for Joseph (blind)
                "VoiceOutputTests.swift",
                // Layered multi-LLM response orchestration
                "LayeredResponseTests.swift",
                // Accessibility — WCAG 2.1 AA compliance
                "AccessibilityTests.swift",
                "CodeSigningTests.swift"
            ]
        )
    ]
)
