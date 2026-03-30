// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "BrainChat",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .library(name: "BrainChatLib", targets: ["BrainChatLib"])
    ],
    targets: [
        .target(
            name: "BrainChatLib",
            path: ".",
            exclude: [
                ".build",
                "build",
                "Tests",
                "Sources",
                "Info.plist",
                "build.sh",
                "install.sh",
                "voice_bridge_daemon.py",
                "AirPodsManager.swift",
                "AudioPlayer.swift",
                "AudioSession.swift",
                "BrainChat.swift",
                "BrainChatCoordinator.swift",
                "BridgeDaemon.swift",
                "CartesiaVoice.swift",
                "CodeAssistant.swift",
                "ContentView.swift",
                "ConversationView.swift",
                "CopilotVoiceRouter.swift",
                "EventTypes.swift",
                "LLMSelector.swift",
                "PandaproxyClient.swift",
                "RedpandaBridge.swift",
                "SafetyGuard.swift",
                "SettingsView.swift",
                "SpatialAudio.swift",
                "SpeechManager.swift",
                "SystemCommands.swift",
                "VoiceBridge.swift",
                "VoiceManager.swift",
                "VoiceSelector.swift",
                "YoloExecutor.swift",
                "YoloMode.swift",
                "YoloSession.swift",
                "VoiceTests",
                "AppTypes.swift",
                "__pycache__",
                "runtime",
                "bridge-daemon.log",
                "build-output.log"
            ],
            sources: [
                "AIManager.swift",
                "APIKeyManager.swift",
                "ClaudeAPI.swift",
                "CopilotBridge.swift",
                "CopilotClient.swift",
                "GeminiClient.swift",
                "GrokClient.swift",
                "LLMRouter.swift",
                "Models.swift",
                "OllamaAPI.swift",
                "OpenAIAPI.swift",
                "Sources/BrainChat/BrainChatLib.swift"
            ]
        ),
        .testTarget(
            name: "BrainChatTests",
            dependencies: ["BrainChatLib"],
            path: "Tests",
            exclude: [
                "AppTests",
                "Comprehensive",
                "AudioDeviceTests.swift",
                "AIManagerTests.swift",
                "CopilotBridgeTests.swift",
                "E2ECodingTests.swift",
                "E2EConversationTests.swift",
                "E2EMultiLLMTests.swift",
                "E2EYoloTests.swift",
                "EndToEndVoiceTests.swift",
                "IntegrationTests.swift",
                "RedpandaBridgeTests.swift",
                "SpeechManagerTests.swift",
                "TestOrchestrator.swift",
                "VoiceIntegrationTests.swift",
                "VoiceManagerTests.swift",
                "VoiceMocks.swift",
                "Package.swift",
                "Sources",
                "Tests"
            ],
            sources: [
                "LLMTestSupport.swift",
                "OllamaTests.swift",
                "ClaudeTests.swift",
                "GPTTests.swift",
                "CopilotTests.swift",
                "GrokTests.swift",
                "GeminiTests.swift",
                "LLMRouterTests.swift"
            ]
        )
    ]
)
