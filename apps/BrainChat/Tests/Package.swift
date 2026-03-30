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
                "PandaproxyClient.swift",
                "RedpandaBridge.swift"
            ]
        ),
        .testTarget(
            name: "BrainChatE2ETests",
            dependencies: ["BrainChatLib"],
            path: ".",
            sources: [
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
                "RedpandaBridgeTests.swift"
            ]
        )
    ]
)
