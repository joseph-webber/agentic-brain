// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "VoiceTests",
    platforms: [.macOS(.v14)],
    targets: [
        .target(
            name: "VoiceTestLib",
            path: "Sources/VoiceTestLib"
        ),
        .testTarget(
            name: "VoiceTests",
            dependencies: ["VoiceTestLib"],
            path: "Tests/VoiceTests"
        )
    ]
)
