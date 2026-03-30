// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "KarenApp",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "KarenApp", targets: ["KarenApp"])
    ],
    targets: [
        .executableTarget(
            name: "KarenApp",
            path: "Sources/KarenApp"
        )
    ]
)
