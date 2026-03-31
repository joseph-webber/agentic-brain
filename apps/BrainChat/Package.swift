// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "BrainChat",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "BrainChat", targets: ["BrainChat"])
    ],
    targets: [
        .executableTarget(
            name: "BrainChat",
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
                "LLMSelector.swift",
                "VoiceTests",
                "__pycache__",
                "runtime",
                "bridge-daemon.log",
                "build-output.log"
            ],
            sources: [
                "BrainChat.swift",
                "BrainChatCoordinator.swift",
                "AirPodsManager.swift",
                "AudioPlayer.swift",
                "AudioSession.swift",
                "BridgeDaemon.swift",
                "CartesiaVoice.swift",
                "CodeAssistant.swift",
                "ContentView.swift",
                "ConversationView.swift",
                "CopilotVoiceRouter.swift",
                "FasterWhisperBridge.swift",
                "PandaproxyClient.swift",
                "RedpandaBridge.swift",
                "SafetyGuard.swift",
                "SettingsView.swift",
                "SpatialAudio.swift",
                "SpeechManager.swift",
                "SpeechEngineSelector.swift",
                "SystemCommands.swift",
                "VoiceBridge.swift",
                "VoiceManager.swift",
                "VoiceSelector.swift",
                "YoloExecutor.swift",
                "YoloMode.swift",
                "YoloSession.swift",
                "WhisperEngines.swift",
                "AppTypes.swift",
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
                "OpenAIAPI.swift"
            ]
        ),
        .testTarget(
            name: "BrainChatTests",
            dependencies: ["BrainChat"],
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
