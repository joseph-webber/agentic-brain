import XCTest
@testable import BrainChatLib

// MARK: - Voice Output (TTS) Engine Tests
// user is blind and relies on TTS for ALL output.
// These tests ensure every engine is correctly modelled and
// that accessibility-critical properties are never accidentally changed.

final class VoiceOutputEngineEnumerationTests: XCTestCase {

    func testAllFourEnginesExist() {
        let engines = VoiceOutputEngine.allCases
        XCTAssertEqual(engines.count, 4, "Must have exactly 4 TTS engines")
    }

    func testAllCasesArePresent() {
        let expected: Set<VoiceOutputEngine> = [.macOS, .cartesia, .piper, .elevenLabs]
        XCTAssertEqual(Set(VoiceOutputEngine.allCases), expected)
    }

    func testRawValuesAreHumanReadable() {
        XCTAssertEqual(VoiceOutputEngine.macOS.rawValue,      "macOS Native")
        XCTAssertEqual(VoiceOutputEngine.cartesia.rawValue,   "Cartesia")
        XCTAssertEqual(VoiceOutputEngine.piper.rawValue,      "Piper TTS")
        XCTAssertEqual(VoiceOutputEngine.elevenLabs.rawValue, "ElevenLabs")
    }

    func testIdEqualRawValue() {
        for engine in VoiceOutputEngine.allCases {
            XCTAssertEqual(engine.id, engine.rawValue)
        }
    }
}

// MARK: - API Key Requirements

final class VoiceOutputAPIKeyTests: XCTestCase {

    func testCloudEnginesRequireAPIKey() {
        XCTAssertTrue(VoiceOutputEngine.cartesia.requiresAPIKey,   "Cartesia needs API key")
        XCTAssertTrue(VoiceOutputEngine.elevenLabs.requiresAPIKey, "ElevenLabs needs API key")
    }

    func testLocalEnginesRequireNoAPIKey() {
        XCTAssertFalse(VoiceOutputEngine.macOS.requiresAPIKey,  "macOS TTS is free")
        XCTAssertFalse(VoiceOutputEngine.piper.requiresAPIKey,  "Piper is open-source local")
    }

    func testEnginesWithAPIKeyAreNotOffline() {
        for engine in VoiceOutputEngine.allCases where engine.requiresAPIKey {
            XCTAssertFalse(engine.isOffline,
                           "\(engine.rawValue) requires a key so it must be online")
        }
    }

    func testLocalEnginesAreOffline() {
        XCTAssertTrue(VoiceOutputEngine.macOS.isOffline,  "macOS TTS works without internet")
        XCTAssertTrue(VoiceOutputEngine.piper.isOffline,  "Piper is on-device")
    }
}

// MARK: - Cross-Platform Support

final class VoiceOutputCrossPlatformTests: XCTestCase {

    func testMacOSEngineIsNotCrossPlatform() {
        XCTAssertFalse(VoiceOutputEngine.macOS.crossPlatform,
                       "macOS Native TTS only works on macOS")
    }

    func testCloudEnginesAreCrossPlatform() {
        XCTAssertTrue(VoiceOutputEngine.cartesia.crossPlatform)
        XCTAssertTrue(VoiceOutputEngine.elevenLabs.crossPlatform)
    }

    func testPiperIsCrossPlatform() {
        XCTAssertTrue(VoiceOutputEngine.piper.crossPlatform,
                      "Piper is designed for Linux/macOS/Windows")
    }
}

// MARK: - Platform Default

final class VoiceOutputPlatformDefaultTests: XCTestCase {

    func testPlatformDefaultIsNotNil() {
        let engine = VoiceOutputEngine.platformDefault
        XCTAssertNotNil(engine)
    }

    func testMacOSPlatformDefaultIsNativeEngine() {
        // On macOS, always fall back to the system voice (Karen)
        // This ensures user always has speech even if cloud is down
        XCTAssertEqual(VoiceOutputEngine.platformDefault, .macOS)
    }

    func testDefaultEngineRequiresNoAPIKey() {
        XCTAssertFalse(VoiceOutputEngine.platformDefault.requiresAPIKey,
                       "Default must work without configuration")
    }

    func testDefaultEngineIsOffline() {
        XCTAssertTrue(VoiceOutputEngine.platformDefault.isOffline,
                      "Default must work without internet access")
    }
}

// MARK: - Descriptions (Accessibility)

final class VoiceOutputDescriptionTests: XCTestCase {

    func testAllEnginesHaveNonEmptyDescription() {
        for engine in VoiceOutputEngine.allCases {
            XCTAssertFalse(engine.description.isEmpty,
                           "\(engine.rawValue) needs a description for VoiceOver menu items")
        }
    }

    func testDescriptionsAreHumanReadable() {
        for engine in VoiceOutputEngine.allCases {
            XCTAssertFalse(engine.description.contains("_"),
                           "\(engine.rawValue) description must not contain underscores")
        }
    }

    func testMacOSDescriptionMentionsKaren() {
        // Karen is user's preferred voice
        XCTAssertTrue(VoiceOutputEngine.macOS.description.contains("Karen"),
                      "macOS description must mention Karen voice (user's choice)")
    }

    func testCartesiaDescriptionMentionsLatency() {
        XCTAssertTrue(VoiceOutputEngine.cartesia.description.lowercased().contains("latency") ||
                      VoiceOutputEngine.cartesia.description.lowercased().contains("quality"),
                      "Cartesia description should mention its key advantage")
    }

    func testPiperDescriptionMentionsOffline() {
        XCTAssertTrue(VoiceOutputEngine.piper.description.lowercased().contains("offline") ||
                      VoiceOutputEngine.piper.description.lowercased().contains("local"),
                      "Piper description should mention it works offline")
    }
}

// MARK: - Icons (UI / Accessibility)

final class VoiceOutputIconTests: XCTestCase {

    func testAllEnginesHaveIcon() {
        for engine in VoiceOutputEngine.allCases {
            XCTAssertFalse(engine.icon.isEmpty, "\(engine.rawValue) must have an SF Symbol icon")
        }
    }

    func testIconsDoNotContainSpaces() {
        for engine in VoiceOutputEngine.allCases {
            XCTAssertFalse(engine.icon.contains(" "),
                           "\(engine.rawValue) icon '\(engine.icon)' is not a valid SF Symbol name")
        }
    }
}

// MARK: - Fallback Chain Tests

final class VoiceOutputFallbackChainTests: XCTestCase {

    func testAtLeastOneOfflineEngineAlwaysAvailable() {
        let offlineEngines = VoiceOutputEngine.allCases.filter { $0.isOffline }
        XCTAssertFalse(offlineEngines.isEmpty,
                       "There must always be at least one offline TTS engine for accessibility")
    }

    func testFallbackChainPreservesAccessibility() {
        // If all cloud engines fail, we can still speak to user
        let availableWithoutNetwork = VoiceOutputEngine.allCases.filter { $0.isOffline }
        XCTAssertGreaterThanOrEqual(availableWithoutNetwork.count, 1,
                                    "At least one engine must work offline")
    }

    func testPreferredFallbackOrder() {
        // Ideal fallback: macOS (always works) → Piper (cross-platform) → cloud
        let sorted = VoiceOutputEngine.allCases.sorted {
            let aIsOffline = $0.isOffline
            let bIsOffline = $1.isOffline
            if aIsOffline != bIsOffline { return aIsOffline }
            return !$0.requiresAPIKey && $1.requiresAPIKey
        }
        XCTAssertTrue(sorted.first?.isOffline ?? false,
                      "First fallback must be an offline engine")
    }

    func testKarenVoiceAccessibleViaMacOSEngine() {
        // user's preferred voice (Karen) is only available on macOS engine
        XCTAssertTrue(VoiceOutputEngine.macOS.description.contains("Karen"))
        XCTAssertTrue(VoiceOutputEngine.macOS.isOffline)
    }
}

// MARK: - Settings Persistence

final class VoiceOutputSettingsTests: XCTestCase {

    func testAppSettingsExposesVoiceOutputEngine() {
        var settings = AppSettings.defaults
        // Default voice output is macOS (Karen) to guarantee accessibility on launch
        XCTAssertEqual(settings.voiceOutputEngine, .macOS,
                       "On macOS, default must be .macOS so Karen speaks on first launch")
    }

    func testSettingsCanSwitchToCartesia() {
        var settings = AppSettings.defaults
        settings.voiceOutputEngine = .cartesia
        XCTAssertEqual(settings.voiceOutputEngine, .cartesia)
    }

    func testSettingsCanRoundtripAllEngines() {
        var settings = AppSettings.defaults
        for engine in VoiceOutputEngine.allCases {
            settings.voiceOutputEngine = engine
            XCTAssertEqual(settings.voiceOutputEngine, engine,
                           "Settings must persist \(engine.rawValue)")
        }
    }
}
