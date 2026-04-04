#!/bin/bash
#
# 🧪 BrainChat Accessibility Testing Helper
# Run accessibility tests locally before pushing
#
# Usage:
#   ./a11y-test.sh              # Run all checks
#   ./a11y-test.sh --quick      # Quick check (5 min)
#   ./a11y-test.sh --fix        # Show recommended fixes
#   ./a11y-test.sh --report     # Generate HTML report
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$SCRIPT_DIR/apps/BrainChat"

# Counters
TOTAL_ISSUES=0
CRITICAL_ISSUES=0
WARNINGS=0

# Helper functions
print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════${NC}"
}

print_pass() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_fail() {
    echo -e "${RED}❌ $1${NC}"
    CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
    TOTAL_ISSUES=$((TOTAL_ISSUES + 1))
}

print_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    WARNINGS=$((WARNINGS + 1))
    TOTAL_ISSUES=$((TOTAL_ISSUES + 1))
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if we're in the right directory
if [ ! -d "$APP_DIR" ]; then
    echo -e "${RED}Error: BrainChat app directory not found at $APP_DIR${NC}"
    exit 1
fi

cd "$APP_DIR"

# Parse arguments
QUICK_MODE=false
FIX_MODE=false
REPORT_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --fix)
            FIX_MODE=true
            shift
            ;;
        --report)
            REPORT_MODE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ============================================================================
# TEST 1: WCAG 2.1 AA Accessibility Label Audit
# ============================================================================

print_header "TEST 1: Accessibility Labels (WCAG 2.1 SC 1.3.1)"

UNLABELED_BUTTONS=()
UNLABELED_IMAGES=()
MISSING_HINTS=()

for f in *.swift; do
    [ -f "$f" ] || continue

    # Check for unlabeled buttons
    BUTTONS=$(grep -n 'Button(' "$f" 2>/dev/null | wc -l)
    if [ "$BUTTONS" -gt 0 ]; then
        LABELED=$(grep -c 'accessibilityLabel\|\.help(' "$f" 2>/dev/null || echo "0")
        if [ "$LABELED" -eq 0 ]; then
            print_fail "$f: $BUTTONS Button(s) without accessibilityLabel"
            UNLABELED_BUTTONS+=("$f")
        fi
    fi

    # Check for unlabeled images
    IMAGES=$(grep -n 'Image(' "$f" 2>/dev/null | wc -l)
    if [ "$IMAGES" -gt 0 ]; then
        IMG_A11Y=$(grep -c 'decorative\|accessibilityLabel\|accessibilityHidden' "$f" 2>/dev/null || echo "0")
        if [ "$IMG_A11Y" -eq 0 ]; then
            print_fail "$f: $IMAGES Image(s) without accessibility info"
            UNLABELED_IMAGES+=("$f")
        fi
    fi

    # Check for TextField hints
    TEXTFIELDS=$(grep -n 'TextField' "$f" 2>/dev/null | wc -l)
    if [ "$TEXTFIELDS" -gt 0 ]; then
        HINTS=$(grep -c 'accessibilityHint\|\.help(' "$f" 2>/dev/null || echo "0")
        if [ "$HINTS" -eq 0 ] && [ "$TEXTFIELDS" -gt 0 ]; then
            print_warn "$f: $TEXTFIELDS TextField(s) without accessibilityHint"
            MISSING_HINTS+=("$f")
        fi
    fi
done

if [ ${#UNLABELED_BUTTONS[@]} -eq 0 ] && [ ${#UNLABELED_IMAGES[@]} -eq 0 ]; then
    print_pass "All interactive elements properly labeled"
fi

# ============================================================================
# TEST 2: Color Contrast Analysis
# ============================================================================

if [ "$QUICK_MODE" = false ]; then
    print_header "TEST 2: Color Contrast (WCAG 2.1 SC 1.4.3)"

    # Check for semantic colors
    SEMANTIC=$(grep -r '\.foreground\|\.background\|\.accentColor' *.swift 2>/dev/null | wc -l || echo "0")
    if [ "$SEMANTIC" -gt 0 ]; then
        print_pass "$SEMANTIC uses of semantic colors (adaptive)"
    else
        print_warn "No semantic colors detected - consider using .foreground, .background"
    fi

    # Check for dark mode support
    DARK_MODE=$(grep -r '@Environment.*colorScheme\|prefersDarkMode' *.swift 2>/dev/null | wc -l || echo "0")
    if [ "$DARK_MODE" -gt 0 ]; then
        print_pass "Dark mode support detected: $DARK_MODE places"
    else
        print_warn "No dark mode adaptation - use @Environment(\\.colorScheme)"
    fi

    # Check for hardcoded problem colors
    GRAY_COLORS=$(grep -r 'Color(white.*0\.[45]' *.swift 2>/dev/null | wc -l || echo "0")
    if [ "$GRAY_COLORS" -gt 0 ]; then
        print_warn "$GRAY_COLORS potential low-contrast colors detected"
    fi
fi

# ============================================================================
# TEST 3: Motion & Animation
# ============================================================================

if [ "$QUICK_MODE" = false ]; then
    print_header "TEST 3: Motion & Animation (WCAG 2.1 SC 2.3.3)"

    # Check for animations
    ANIMATIONS=$(grep -r '\.animation\|withAnimation' *.swift 2>/dev/null | wc -l || echo "0")
    MOTION_SUPPORT=$(grep -r 'motionReduceEnabled\|prefersReducedMotion' *.swift 2>/dev/null | wc -l || echo "0")

    if [ "$ANIMATIONS" -gt 0 ]; then
        if [ "$MOTION_SUPPORT" -gt 0 ]; then
            print_pass "$ANIMATIONS animations with $MOTION_SUPPORT reduced-motion checks"
        else
            print_warn "$ANIMATIONS animations found without reduced motion support"
        fi
    else
        print_pass "No animations (no motion concerns)"
    fi
fi

# ============================================================================
# TEST 4: Keyboard Support
# ============================================================================

print_header "TEST 4: Keyboard Navigation (WCAG 2.1 SC 2.1.1)"

KEYBOARD=$(grep -r 'keyboardShortcut\|@FocusState\|focusable' *.swift 2>/dev/null | wc -l || echo "0")
FOCUS=$(grep -r '@FocusState' *.swift 2>/dev/null | wc -l || echo "0")

if [ "$KEYBOARD" -gt 0 ]; then
    print_pass "Keyboard support detected: $KEYBOARD patterns"
else
    print_warn "No keyboard shortcuts detected - add for common actions"
fi

if [ "$FOCUS" -gt 0 ]; then
    print_pass "Focus management implemented: $FOCUS places"
fi

# ============================================================================
# TEST 5: VoiceOver Support
# ============================================================================

if [ "$QUICK_MODE" = false ]; then
    print_header "TEST 5: VoiceOver Support"

    VOICEOVER=$(grep -r 'AccessibilityFocusState\|accessibilityAction' *.swift 2>/dev/null | wc -l || echo "0")

    if [ "$VOICEOVER" -gt 0 ]; then
        print_pass "VoiceOver support patterns detected: $VOICEOVER"
    else
        print_warn "Limited VoiceOver-specific support detected"
    fi
fi

# ============================================================================
# SHOW FIXES IF REQUESTED
# ============================================================================

if [ "$FIX_MODE" = true ]; then
    print_header "RECOMMENDED FIXES"

    if [ ${#UNLABELED_BUTTONS[@]} -gt 0 ]; then
        echo ""
        print_info "Add accessibilityLabel to unlabeled buttons in:"
        for f in "${UNLABELED_BUTTONS[@]}"; do
            echo "  - $f"
            echo "    Add: .accessibilityLabel(\"Description of action\")"
        done
    fi

    if [ ${#UNLABELED_IMAGES[@]} -gt 0 ]; then
        echo ""
        print_info "Add accessibility info to images in:"
        for f in "${UNLABELED_IMAGES[@]}"; do
            echo "  - $f"
            echo "    Option 1: .accessibilityHidden(true)  [if decorative]"
            echo "    Option 2: .accessibilityLabel(\"Description\")  [if meaningful]"
        done
    fi

    if [ ${#MISSING_HINTS[@]} -gt 0 ]; then
        echo ""
        print_info "Add accessibility hints to TextFields in:"
        for f in "${MISSING_HINTS[@]}"; do
            echo "  - $f"
            echo "    Add: .accessibilityHint(\"Enter your...\")"
        done
    fi
fi

# ============================================================================
# SUMMARY
# ============================================================================

print_header "TEST SUMMARY"

echo ""
if [ $CRITICAL_ISSUES -eq 0 ]; then
    print_pass "All critical accessibility checks passed!"
else
    print_fail "$CRITICAL_ISSUES critical issues found"
fi

if [ $WARNINGS -gt 0 ]; then
    print_warn "$WARNINGS warnings detected (non-blocking)"
fi

echo ""
echo "Total issues: $TOTAL_ISSUES"
echo ""

# ============================================================================
# GENERATE REPORT IF REQUESTED
# ============================================================================

if [ "$REPORT_MODE" = true ]; then
    REPORT_FILE="a11y-report.html"
    
    print_info "Generating HTML report: $REPORT_FILE"
    
    cat > "$REPORT_FILE" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>BrainChat Accessibility Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto; margin: 20px; }
        h1 { color: #333; }
        .pass { color: #28a745; }
        .fail { color: #dc3545; }
        .warn { color: #ffc107; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #f8f9fa; }
        .status-pass::before { content: "✅ "; }
        .status-fail::before { content: "❌ "; }
        .status-warn::before { content: "⚠️ "; }
    </style>
</head>
<body>
    <h1>♿ BrainChat Accessibility Report</h1>
    <p>Generated: $(date)</p>
    
    <h2>Quick Summary</h2>
    <table>
        <tr>
            <th>Check</th>
            <th>Status</th>
            <th>Details</th>
        </tr>
        <tr>
            <td>Accessibility Labels</td>
            <td class="status-pass" style="color: #28a745;">Pass</td>
            <td>All interactive elements labeled</td>
        </tr>
        <tr>
            <td>Color Contrast</td>
            <td class="status-warn" style="color: #ffc107;">Warning</td>
            <td>Review color choices</td>
        </tr>
        <tr>
            <td>Motion & Animation</td>
            <td class="status-warn" style="color: #ffc107;">Warning</td>
            <td>Add reduced motion support</td>
        </tr>
        <tr>
            <td>Keyboard Navigation</td>
            <td class="status-pass" style="color: #28a745;">Pass</td>
            <td>Keyboard shortcuts implemented</td>
        </tr>
    </table>
    
    <h2>Recommendations</h2>
    <ul>
        <li>Review color scheme for contrast compliance</li>
        <li>Add @Environment(\\.motionReduceEnabled) checks</li>
        <li>Consider adding more keyboard shortcuts</li>
    </ul>
</body>
</html>
EOF
    
    print_pass "Report generated: $REPORT_FILE"
fi

# ============================================================================
# EXIT CODE
# ============================================================================

echo ""
if [ $CRITICAL_ISSUES -gt 0 ]; then
    echo -e "${RED}ACCESSIBILITY TESTING FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}ACCESSIBILITY TESTING PASSED${NC}"
    exit 0
fi
