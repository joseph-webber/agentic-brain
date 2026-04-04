// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "BrainChat",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "BrainChat", targets: ["BrainChatLib"])
    ],
    targets: [
        .executableTarget(
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
                "VoiceTests",
                "__pycache__",
                "runtime",
                "bridge-daemon.log",
                "build-output.log"
            ],
            sources: [
                "AIManager.swift",
                "APIKeyManager.swift",
                "AirPodsManager.swift",
                "AppTypes.swift",
                "AudioPlayer.swift",
                "AudioSession.swift",
                "BrainChat.swift",
                "BrainChatCoordinator.swift",
                "BridgeDaemon.swift",
                "CartesiaVoice.swift",
                "ClaudeAPI.swift",
                "CodeAssistant.swift",
                "ContentView.swift",
                "ConversationView.swift",
                "CopilotBridge.swift",
                "CopilotClient.swift",
                "CopilotVoiceRouter.swift",
                "EventTypes.swift",
                "FasterWhisperBridge.swift",
                "GeminiClient.swift",
                "GroqClient.swift",
                "GrokClient.swift",
                "LayeredResponseManager.swift",
                "LayeredResponseView.swift",
                "LLMRouter.swift",
                "LLMSelector.swift",
                "Models.swift",
                "OllamaAPI.swift",
                "OpenAIAPI.swift",
                "PandaproxyClient.swift",
                "RedpandaBridge.swift",
                "ResponseWeavingCoordinator.swift",
                "ResponseWeavingTypes.swift",
                "ResponseWeavingView.swift",
                "SSEStreamParser.swift",
                "SafetyGuard.swift",
                "SettingsView.swift",
                "SpatialAudio.swift",
                "SpeechEngineSelector.swift",
                "SpeechManager.swift",
                "SystemCommands.swift",
                "VoiceBridge.swift",
                "VoiceManager.swift",
                "VoiceOutputSelector.swift",
                "VoiceSelector.swift",
                "WhisperEngines.swift",
                "YoloExecutor.swift",
                "YoloMode.swift",
                "YoloSession.swift"
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
                // Use stub AppSettings.defaults — only valid in E2E sub-package
                "VoiceOutputTests.swift",
                "SpeechEngineTests.swift",
                "AccessibilityTests.swift",
                "Package.swift",
                "Sources",
                "Tests"
            ],
            sources: [
                // LLM client tests (use real app types via @testable import BrainChatLib)
                "ClaudeTests.swift",
                "CopilotTests.swift",
                "GeminiTests.swift",
                "GPTTests.swift",
                "GroqTests.swift",
                "GrokTests.swift",
                "LLMRouterTests.swift",
                "LLMTestSupport.swift",
                "OllamaTests.swift",
                // Layered multi-LLM orchestration (uses real LayeredResponseManager types)
                "LayeredResponseTests.swift",
                // Redpanda / Pandaproxy event bus (uses real PandaproxyClient types)
                "RedpandaIntegrationTests.swift"
            ]
        )
    ]
)
