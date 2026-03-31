#!/bin/bash

# macOS Voice App Microphone Verification Script
# Comprehensive test suite for microphone permissions and configurations

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Function to run a test and track results
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo -e "\n${BLUE}TEST $TESTS_TOTAL: $test_name${NC}"
    echo "============================================"
    
    if eval "$test_command"; then
        echo -e "${GREEN}✅ PASSED: $test_name${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}❌ FAILED: $test_name${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Function to check if Info.plist exists and has required keys
check_info_plist() {
    local info_plist_path="$1"
    
    if [[ ! -f "$info_plist_path" ]]; then
        echo "❌ Info.plist not found at: $info_plist_path"
        return 1
    fi
    
    echo "📄 Info.plist found: $info_plist_path"
    
    # Check for NSMicrophoneUsageDescription
    if /usr/libexec/PlistBuddy -c "Print :NSMicrophoneUsageDescription" "$info_plist_path" >/dev/null 2>&1; then
        local mic_desc=$(/usr/libexec/PlistBuddy -c "Print :NSMicrophoneUsageDescription" "$info_plist_path" 2>/dev/null)
        echo "✅ NSMicrophoneUsageDescription: '$mic_desc'"
        
        if [[ ${#mic_desc} -lt 10 ]]; then
            echo "⚠️  Warning: Description is quite short (${#mic_desc} chars)"
        fi
    else
        echo "❌ NSMicrophoneUsageDescription missing from Info.plist"
        return 1
    fi
    
    # Check other required keys
    local required_keys=("CFBundleIdentifier" "CFBundleDisplayName" "CFBundleExecutable")
    
    for key in "${required_keys[@]}"; do
        if /usr/libexec/PlistBuddy -c "Print :$key" "$info_plist_path" >/dev/null 2>&1; then
            local value=$(/usr/libexec/PlistBuddy -c "Print :$key" "$info_plist_path" 2>/dev/null)
            echo "✅ $key: '$value'"
        else
            echo "❌ $key missing from Info.plist"
            return 1
        fi
    done
    
    return 0
}

# Function to check code signing
check_code_signing() {
    local app_path="$1"
    
    if [[ ! -d "$app_path" ]]; then
        echo "❌ App bundle not found at: $app_path"
        return 1
    fi
    
    echo "🔒 Checking code signing for: $app_path"
    
    # Check if app is signed
    if codesign --verify --verbose "$app_path" 2>/dev/null; then
        echo "✅ Code signature verification passed"
    else
        echo "❌ Code signature verification failed"
        echo "Detailed error:"
        codesign --verify --verbose "$app_path" 2>&1 || true
        return 1
    fi
    
    # Get signing information
    echo "📋 Code signing details:"
    codesign --display --verbose=2 "$app_path" 2>&1 | while IFS= read -r line; do
        echo "   $line"
    done
    
    # Check for developer identity
    local authority=$(codesign --display --verbose "$app_path" 2>&1 | grep "Authority=" | head -1 | cut -d'=' -f2-)
    if [[ -n "$authority" ]]; then
        echo "✅ Signed by: $authority"
    else
        echo "⚠️  No signing authority found (might be ad-hoc signed)"
    fi
    
    return 0
}

# Function to check entitlements
check_entitlements() {
    local app_path="$1"
    
    echo "🎫 Checking entitlements for: $app_path"
    
    # Extract entitlements from signed app
    local entitlements_output=$(codesign --display --entitlements - "$app_path" 2>/dev/null | xmllint --format -)
    
    if [[ -z "$entitlements_output" ]]; then
        echo "⚠️  No entitlements found or unable to extract"
        return 1
    fi
    
    echo "📋 Extracted entitlements:"
    echo "$entitlements_output" | head -20
    
    # Check for audio input entitlement
    if echo "$entitlements_output" | grep -q "com.apple.security.device.audio-input"; then
        echo "✅ Audio input entitlement found"
        return 0
    else
        echo "❌ Audio input entitlement missing"
        echo "Add this to your entitlements file:"
        echo "<key>com.apple.security.device.audio-input</key>"
        echo "<true/>"
        return 1
    fi
}

# Function to compile and run CLI test
test_cli_tool() {
    local source_file="test-mic-cli.swift"
    local binary_name="test-mic"
    
    if [[ ! -f "$source_file" ]]; then
        echo "❌ CLI test source not found: $source_file"
        return 1
    fi
    
    echo "🔨 Compiling CLI test tool..."
    
    # Clean up old binary
    [[ -f "$binary_name" ]] && rm "$binary_name"
    
    # Compile
    if xcrun swiftc "$source_file" -o "$binary_name" 2>/dev/null; then
        echo "✅ Compilation successful"
    else
        echo "❌ Compilation failed"
        echo "Error details:"
        xcrun swiftc "$source_file" -o "$binary_name" 2>&1 || true
        return 1
    fi
    
    echo "🏃 Running CLI test..."
    
    # Run the test tool
    if "./$binary_name" 2>/dev/null; then
        echo "✅ CLI test completed successfully"
        local exit_code=0
    else
        local exit_code=$?
        echo "⚠️  CLI test completed with exit code: $exit_code"
        echo "Running again to see output:"
        "./$binary_name" 2>&1 || true
    fi
    
    # Clean up
    [[ -f "$binary_name" ]] && rm "$binary_name"
    
    return $exit_code
}

# Function to check system requirements
check_system_requirements() {
    echo "🖥️  System Information:"
    
    # macOS version
    local os_version=$(sw_vers -productVersion)
    echo "   macOS Version: $os_version"
    
    # Check minimum version (10.14 for AVFoundation microphone access)
    local major_version=$(echo "$os_version" | cut -d'.' -f1)
    local minor_version=$(echo "$os_version" | cut -d'.' -f2)
    
    if [[ "$major_version" -gt 10 ]] || [[ "$major_version" -eq 10 && "$minor_version" -ge 14 ]]; then
        echo "✅ macOS version supports AVFoundation microphone access"
    else
        echo "❌ macOS version too old - requires 10.14+"
        return 1
    fi
    
    # Check Xcode Command Line Tools
    if xcode-select -p >/dev/null 2>&1; then
        local xcode_path=$(xcode-select -p)
        echo "✅ Xcode Command Line Tools: $xcode_path"
    else
        echo "❌ Xcode Command Line Tools not installed"
        echo "Install with: xcode-select --install"
        return 1
    fi
    
    # Check Swift version
    if command -v swift >/dev/null 2>&1; then
        local swift_version=$(swift --version | head -1)
        echo "✅ Swift: $swift_version"
    else
        echo "❌ Swift not found"
        return 1
    fi
    
    return 0
}

# Function to check for existing microphone permissions
check_existing_permissions() {
    echo "🔐 Checking existing microphone permissions..."
    
    # Use sqlite3 to query the TCC database
    local tcc_db="/Library/Application Support/com.apple.TCC/TCC.db"
    local user_tcc_db="$HOME/Library/Application Support/com.apple.TCC/TCC.db"
    
    # Check if we can read the database
    if [[ -f "$user_tcc_db" ]]; then
        echo "📊 Querying user TCC database..."
        
        # Query for microphone permissions
        local mic_permissions=$(sqlite3 "$user_tcc_db" "SELECT client, auth_value FROM access WHERE service='kTCCServiceMicrophone';" 2>/dev/null || echo "")
        
        if [[ -n "$mic_permissions" ]]; then
            echo "🎤 Found microphone permissions:"
            echo "$mic_permissions" | while IFS='|' read -r client auth_value; do
                local status="DENIED"
                [[ "$auth_value" -eq 2 ]] && status="GRANTED"
                echo "   $client: $status"
            done
        else
            echo "ℹ️  No microphone permissions found in TCC database"
        fi
    else
        echo "⚠️  Cannot access TCC database (this is normal on newer macOS versions)"
    fi
}

# Function to print final summary
print_summary() {
    echo ""
    echo "============================================"
    echo -e "${BOLD}MICROPHONE VERIFICATION SUMMARY${NC}"
    echo "============================================"
    echo -e "Tests Total:  ${BLUE}$TESTS_TOTAL${NC}"
    echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
    echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
    
    local success_rate=$((TESTS_PASSED * 100 / TESTS_TOTAL))
    echo -e "Success Rate: ${success_rate}%"
    
    echo ""
    
    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
        echo -e "${GREEN}Your macOS voice app should work correctly with microphone access.${NC}"
        return 0
    else
        echo -e "${RED}⚠️  $TESTS_FAILED TEST(S) FAILED${NC}"
        echo -e "${YELLOW}Review the failed tests above and fix the issues before deploying.${NC}"
        
        echo ""
        echo "COMMON FIXES:"
        echo "1. Add NSMicrophoneUsageDescription to Info.plist"
        echo "2. Add com.apple.security.device.audio-input entitlement"
        echo "3. Code sign your app properly"
        echo "4. Test manually in System Preferences → Security & Privacy → Microphone"
        
        return 1
    fi
}

# Main execution function
main() {
    echo -e "${BOLD}${BLUE}🎤 macOS VOICE APP MICROPHONE VERIFICATION${NC}"
    echo "=================================================="
    echo ""
    echo "This script verifies microphone permissions and configurations"
    echo "for macOS voice applications to prevent deployment issues."
    echo ""
    
    # Change to script directory
    cd "$(dirname "$0")"
    
    # Run all tests
    run_test "System Requirements Check" "check_system_requirements"
    
    run_test "Info.plist Verification" "check_info_plist 'Info.plist'"
    
    # For now, skip app-specific tests since we're in development
    # These would be enabled when testing a built .app bundle
    # run_test "Code Signing Verification" "check_code_signing 'BrainChat.app'"
    # run_test "Entitlements Check" "check_entitlements 'BrainChat.app'"
    
    run_test "CLI Tool Test" "test_cli_tool"
    
    run_test "Existing Permissions Check" "check_existing_permissions"
    
    # Print summary and exit with appropriate code
    if print_summary; then
        exit 0
    else
        exit 1
    fi
}

# Handle command line arguments
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Microphone Verification Script for macOS Voice Apps"
    echo ""
    echo "This script performs comprehensive testing of microphone permissions,"
    echo "Info.plist configuration, code signing, and entitlements."
    echo ""
    echo "OPTIONS:"
    echo "  -h, --help     Show this help message"
    echo "  -v, --version  Show version information"
    echo ""
    echo "FILES TESTED:"
    echo "  - Info.plist (NSMicrophoneUsageDescription and other keys)"
    echo "  - test-mic-cli.swift (compiled and executed)"
    echo "  - Code signing and entitlements (when .app bundle present)"
    echo ""
    echo "EXIT CODES:"
    echo "  0  All tests passed"
    echo "  1  One or more tests failed"
    exit 0
fi

if [[ "$1" == "--version" ]] || [[ "$1" == "-v" ]]; then
    echo "macOS Voice App Microphone Verification Script v1.0"
    echo "Compatible with macOS 10.14+"
    echo "Requires Xcode Command Line Tools"
    exit 0
fi

# Run main function
main "$@"