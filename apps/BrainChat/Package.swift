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
                "Info.plist",
                // Shell scripts
                "build.sh",
                "install.sh",
                "verify-mic.sh",
                "verify-code-signing.sh",
                "test_mic_permission.sh",
                "run-mic-test.sh",
                "apply_fix.sh",
                "verify-4-tier.sh",
                // Python scripts
                "voice_bridge_daemon.py",
                // Markdown files (all)
                "*.md",
                "MICROPHONE-TEST-SUITE-README.md",
                "QUICK_TEST.md",
                "FIX_SUMMARY.md",
                "CHECKLIST.md",
                "MIC_PERMISSION_FIX.md",
                "SSE_REFACTORING_SUMMARY.md",
                "README.md",
                "DEPLOYMENT.md",
                "SECURITY-QUICK-REFERENCE.md",
                "REVIEW_SUMMARY_2026-04-04.md",
                "4-TIER-SECURITY-SUMMARY.md",
                "SECURITY_INTEGRATION_SUMMARY.md",
                // Config files
                "*.json",
                // Text files
                "*.txt",
                // Backup files
                "*.backup",
                // Log files
                "bridge-daemon.log",
                "build-output.log",
                "session-artifacts-build.log",
                // Test files
                "test-mic-cli.swift",
                "test-mic-automation.scpt",
                // Directories
                "VoiceTests",
                "runtime",
                "launchagent",
                "Scripts",
                "docs",
                "session-artifacts",
                "Security",
                "Sources/Terminal",
                "benchmarks",
                "Formula",
                // Benchmark .swift files (root level)
                "FastAcknowledgments.swift",
                "PerformanceProfiler.swift",
                "VoiceEngineBenchmark.swift",
                "BrainChat-Optimized.swift",
                "BenchmarkResults.swift",
                "PerformanceOptimizations.swift",
                "STTBenchmark.swift",
                // Source-specific excludes (use root-level versions in sources list)
                "Sources/BrainChat/BrainChat.sdef",
                "Sources/BrainChat/BrainChatLib.swift",
                "Sources/BrainChat/EventTypes.swift",
                "Sources/BrainChat/PandaproxyClient.swift",
                "Sources/BrainChat/RedpandaBridge.swift",
                // App bundles
                "BrainChat.entitlements",
                "Brain Chat.app",
                "BrainChat.app"
            ],
            sources: [
                "AccessibilityHelpers.swift",
                "AIManager.swift",
                "AgenticBrainIntegration.swift",
                "APIKeyManager.swift",
                "AirPodsManager.swift",
                "AppTypes.swift",
                "AudioPlayer.swift",
                "AudioSession.swift",
                "BrainChatMain.swift",
                "BrainChat.swift",
                "CLIHandler.swift",
                "BrainChatCoordinator.swift",
                "BridgeDaemon.swift",
                "CartesiaVoice.swift",
                "ChatViewModel.swift",
                "ClaudeAPI.swift",
                "CodeAssistant.swift",
                "CodeSpeaker.swift",
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
                "LLMOrchestrator.swift",
                "LLMOrchestratorView.swift",
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
                "Sources/BrainChat/Security/SecurityRole.swift",
                "Sources/BrainChat/Security/SecurityManager.swift",
                "Sources/BrainChat/Security/SecurityGuard.swift",
                "Sources/BrainChat/Security/PermissionChecker.swift",
                "Sources/BrainChat/Security/DangerousCommands.swift",
                "Sources/BrainChat/Security/SecurityModeView.swift",
                "SettingsView.swift",
                "SpatialAudio.swift",
                "SpeechEngineSelector.swift",
                "SpeechManager.swift",
                "SystemCommands.swift",
                "VoiceBridge.swift",
                "VoiceCodingEngine.swift",
                "VoiceManager.swift",
                "VoiceOutputSelector.swift",
                "VoiceSelector.swift",
                "VoiceOutputEngines.swift",
                "WhisperEngines.swift",
                "YoloExecutor.swift",
                "YoloMode.swift",
                "YoloSession.swift",
                "ScriptingSupport.swift"
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
                "CodeSigningTests.swift",
                "MicrophoneTests.swift",
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
                "YoloTests.swift",
                // Use stub AppSettings.defaults — only valid in E2E sub-package
                "VoiceOutputTests.swift",
                "SpeechEngineTests.swift",
                "AccessibilityTests.swift",
                "Package.swift",
                "BrainChatTests/Security",
                "Sources",
                "Tests",
                // Benchmark and documentation files
                "*.md",
                "*.json",
                "Sources/BrainChat/Benchmarks/*.md",
                "Sources/BrainChat/Benchmarks/*.json"
            ],
            sources: [
                // LLM client tests (use real app types via @testable import BrainChatLib)
                "ClaudeTests.swift",
                "BrainChatCLITests.swift",
                "AgenticBrainIntegrationTests.swift",
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
                "RedpandaIntegrationTests.swift",
                // Yolo mode event tests (excluded: YoloCommandEvent type not in SPM target)
                // "YoloTests.swift",
                // Voice coding engine and code speaker tests
                "VoiceCodingTests.swift",
                // Unit tests — polymorphic dispatch, enum coverage, SSE parsing
                "PolymorphicUnitTests.swift",
                "SpeechVoiceEngineRuntimeTests.swift",
                // Integration tests — fallback chains, conversation store, weaving
                "ServiceIntegrationTests.swift",
                // E2E tests — full conversation flows, multi-provider, accessibility
                "FullFlowE2ETests.swift",
                "AppleScriptTests.swift",
                "BrainChatTests/SecurityModeTests.swift",
                "BrainChatTests/SecurityFilterCompatibilityTests.swift",
                "Security/PermissionTests.swift",
                "Security/SecurityRoleTests.swift",
                "Security/YoloSecurityTests.swift"
            ]
        )
    ]
)
