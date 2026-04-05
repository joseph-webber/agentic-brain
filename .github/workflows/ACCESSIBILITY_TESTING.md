# ♿ BrainChat Accessibility Testing Guide

## Overview

BrainChat CI/CD pipelines include comprehensive accessibility testing to ensure compliance with **WCAG 2.1 Level AA** standards. Tests validate accessibility for users with various disabilities including:

- **Vision impairment** (blind, low vision)
- **Motor disabilities** (mobility, dexterity challenges)
- **Auditory disabilities** (deaf, hard of hearing)
- **Vestibular disorders** (motion sensitivity)
- **Cognitive disabilities** (processing, attention)

## CI/CD Pipeline Jobs

### 1. 🔍 Accessibility Compliance (WCAG 2.1 AA)

**File**: `brainchat-test.yml` → `accessibility-compliance` job

#### What it tests:

| Check | WCAG Criterion | Details |
|-------|----------------|---------|
| **Label Coverage** | SC 1.3.1 | All `Button()` elements must have `accessibilityLabel` |
| **Image Alt Text** | SC 1.1.1 | All `Image()` elements must have `.decorative` OR `accessibilityLabel` OR `accessibilityHidden` |
| **TextField Hints** | SC 3.3.2 | Input fields should have `accessibilityHint` for instructions |
| **Semantic Colors** | SC 1.4.3 | Use system colors, not hardcoded values |
| **Focus Management** | SC 2.4.3 | Verify `FocusState` or `@FocusState` patterns |
| **Keyboard Support** | SC 2.1.1 | Check for `keyboardShortcut`, `onKeyPress`, or `keyDown` |
| **VoiceOver Support** | macOS | Detect `AccessibilityFocusState`, `accessibilityAction` patterns |

#### Example Failures:

```swift
// ❌ FAIL: Button without label
Button("Click me") { }

// ✅ PASS: Button with accessibility label
Button("Click me") { }
    .accessibilityLabel("Primary Action")

// ❌ FAIL: Image without accessibility
Image(systemName: "heart.fill")

// ✅ PASS: Decorative image
Image(systemName: "heart.fill")
    .accessibilityHidden(true)

// ✅ PASS: Meaningful image
Image(systemName: "heart.fill")
    .accessibilityLabel("Mark as favorite")
```

**Status**: **FAILS THE PIPELINE** if `FAIL_COUNT > 0`

---

### 2. 🗣️ VoiceOver Interaction Testing

**File**: `brainchat-test.yml` → `voiceover-interaction-test` job

#### What it tests:

- All interactive elements reach VoiceOver users
- Buttons are navigable with Tab/Space
- Focus order is predictable
- Semantic elements are recognized

#### Validation:

```bash
# All Button() must have accessibilityLabel
grep 'Button(' *.swift | grep -v 'accessibilityLabel' → FAIL

# All Image() must have accessibility info
grep 'Image(' *.swift | grep -v 'decorative|accessibilityLabel' → FAIL
```

**Status**: **FAILS THE PIPELINE** if unlabeled interactive elements detected

---

### 3. 🎨 Color Contrast Analysis

**File**: `brainchat-test.yml` → `accessibility-contrast-audit` job

#### What it tests:

| Check | WCAG Criterion | Standard |
|-------|----------------|----------|
| **Text Contrast** | SC 1.4.3 | 4.5:1 for normal text, 3:1 for large text |
| **Semantic Colors** | SC 1.4.11 | Use `.foreground`, `.background` instead of hardcoded RGB |
| **Dark Mode** | SC 1.4.3 | Verify `@Environment(\.colorScheme)` handling |
| **Font Sizes** | SC 1.4.4 | Minimum 12pt body, 18pt headings recommended |
| **Color Dependency** | SC 1.4.1 | Don't use color alone to convey information |

#### Example:

```swift
// ❌ LOW CONTRAST: Hardcoded gray
.foreground(Color(red: 0.8, green: 0.8, blue: 0.8))

// ✅ GOOD: System semantic colors
.foreground(.secondary)  // Automatically adapts contrast

// ✅ GOOD: Dark mode aware
@Environment(\.colorScheme) var colorScheme
Text("Content")
    .foreground(colorScheme == .dark ? .white : .black)
```

**Status**: **WARNING** if multiple issues detected

---

### 4. 🎬 Motion & Animation Testing

**File**: `brainchat-test.yml` → `accessibility-motion-test` job

#### What it tests:

| Check | WCAG Criterion | Details |
|-------|----------------|---------|
| **Reduced Motion** | SC 2.3.3 | Must respect `@Environment(\.motionReduceEnabled)` |
| **Animation Support** | SC 2.3.2 | Animations must not cause seizures (<3 flashes/sec) |
| **Transitions** | SC 2.3.3 | Respect user motion preferences for all transitions |

#### Example:

```swift
// ❌ FAIL: Animation ignores reduced motion
@State var showContent = false

Text("Content")
    .opacity(showContent ? 1 : 0)
    .animation(.easeInOut)

// ✅ PASS: Respects motion preference
@Environment(\.motionReduceEnabled) var motionReduce

Text("Content")
    .opacity(showContent ? 1 : 0)
    .animation(motionReduce ? nil : .easeInOut)
```

**Status**: **FAILS** if animations without reduced motion support

---

### 5. ✅ Accessibility Testing Matrix (A11y Matrix)

**File**: `brainchat-test.yml` → `accessibility-matrix` job

#### 4-Scenario Test Matrix:

| Scenario | Tests | Pass Criteria |
|----------|-------|---------------|
| **VoiceOver Enabled** | VoiceOver-specific labels & focus | `accessibilityLabel` present in files |
| **Increased Contrast** | Semantic colors adapt | Uses `.foreground`, `.background`, not hardcoded |
| **Reduced Motion** | Animations respect preference | `@Environment(\.motionReduceEnabled)` detected |
| **Keyboard Navigation** | All functions via keyboard | `keyboardShortcut` or `@FocusState` present |

#### Pass Rate Calculation:

```bash
Pass Rate = (Passed Scenarios / 4) × 100%

3/4 = 75% ✅ (acceptable)
2/4 = 50% ❌ (fails pipeline)
```

**Status**: **FAILS THE PIPELINE** if Pass Rate < 75% (< 3/4 scenarios)

---

## How to Make Tests Pass

### ✅ Checklist for Developers

#### 1. Label All Interactive Elements

```swift
// Buttons
Button("Submit") { submitForm() }
    .accessibilityLabel("Submit form")
    .accessibilityHint("Sends the form data")

// Toggles
Toggle("Dark Mode", isOn: $isDark)
    .accessibilityLabel("Enable dark mode")

// Pickers
Picker("Choose option", selection: $selected) {
    Text("Option A").tag(1)
    Text("Option B").tag(2)
}
.accessibilityLabel("Select an option")
.accessibilityHint("Choose from the available options")
```

#### 2. Provide Image Accessibility

```swift
// Decorative images (hide from screen readers)
Image(systemName: "star.fill")
    .accessibilityHidden(true)

// Meaningful images (provide label)
Image(systemName: "heart.fill")
    .accessibilityLabel("Add to favorites")

// Images with context (use description)
Image("chart")
    .accessibilityLabel("Sales chart")
    .accessibilityValue("Up 15% this month")
```

#### 3. Support Dark Mode

```swift
@Environment(\.colorScheme) var colorScheme

Text("Content")
    .foreground(colorScheme == .dark ? .white : .black)
    
// OR use semantic colors (preferred)
Text("Content")
    .foreground(.primary)  // Automatically adapts
```

#### 4. Respect Motion Preferences

```swift
@Environment(\.motionReduceEnabled) var motionReduce

ZStack {
    // Animated content
}
.animation(motionReduce ? nil : .easeInOut)
```

#### 5. Implement Focus Management

```swift
@FocusState private var focusedField: Field?

enum Field {
    case name, email, submit
}

VStack {
    TextField("Name", text: $name)
        .focused($focusedField, equals: .name)
    
    TextField("Email", text: $email)
        .focused($focusedField, equals: .email)
    
    Button("Submit") { submit() }
        .focused($focusedField, equals: .submit)
        .keyboardShortcut(.return)
}
```

#### 6. Add Keyboard Shortcuts

```swift
Button("Submit") { submitForm() }
    .keyboardShortcut(.return)  // Enter key

Button("Cancel") { dismiss() }
    .keyboardShortcut(.cancelAction)  // Esc key

Button("Save") { save() }
    .keyboardShortcut("s", modifiers: .command)  // Cmd+S
```

---

## Running Tests Locally

### Run All Accessibility Tests

```bash
cd apps/BrainChat

# Run compliance check
swift build
grep -r "Button(" *.swift | grep -v "accessibilityLabel" && echo "FAIL" || echo "PASS"

# Check contrast
grep -r "Color(white" *.swift

# Check motion support
grep -r "@Environment.*motionReduce\|prefersReducedMotion" *.swift
```

### Validate Your Changes

```bash
# After making changes to UI
cd apps/BrainChat

# Quick smoke test
for f in *.swift; do
  UNLABELED=$(grep 'Button(' "$f" | grep -v 'accessibilityLabel' | wc -l)
  if [ "$UNLABELED" -gt 0 ]; then
    echo "❌ $f: $UNLABELED unlabeled buttons"
  fi
done
```

---

## WCAG 2.1 Compliance Levels

### Level A (Minimum)
- Color not sole means of info
- Keyboard accessible

### Level AA (Recommended) ⭐
- 4.5:1 contrast ratio
- Meaningful labels
- Focus visible
- Motion can be disabled

### Level AAA (Enhanced)
- 7:1 contrast ratio
- Extended audio descriptions
- Sign language interpretation

**BrainChat Target**: WCAG 2.1 Level AA

---

## Accessibility Resources for macOS/SwiftUI

### Official Documentation
- [Apple Accessibility Guide](https://developer.apple.com/accessibility/)
- [SwiftUI Accessibility](https://developer.apple.com/documentation/swiftui/accessibility)
- [WCAG 2.1 Standard](https://www.w3.org/WAI/WCAG21/quickref/)

### SwiftUI Accessibility Modifiers

| Modifier | Purpose |
|----------|---------|
| `.accessibilityLabel()` | Screen reader label |
| `.accessibilityHint()` | Additional context |
| `.accessibilityValue()` | Current state/value |
| `.accessibilityElement()` | Group elements |
| `.accessibilityHidden()` | Hide from screen readers |
| `.accessibilityAction()` | Custom action |
| `.accessibilityIgnoresInvertColors()` | Don't invert images |
| `.accessibilityAddTraits()` | Mark as button, image, etc. |
| `.accessibilityRemoveTraits()` | Remove traits |

---

## Troubleshooting Failed Tests

### ❌ "Missing accessibilityLabel" - Button Failure

**Problem**: Buttons lack labels for screen readers

**Solution**:
```swift
// Add to every Button
.accessibilityLabel("Description of action")
```

### ❌ "Image without accessibility" - Image Failure

**Problem**: Images don't have accessibility info

**Solution**:
```swift
// Option 1: Mark as decorative
.accessibilityHidden(true)

// Option 2: Add meaningful label
.accessibilityLabel("Description of image content")
```

### ⚠️ "Low contrast colors" - Contrast Warning

**Problem**: Text might not be readable

**Solution**:
```swift
// Use system colors instead of hardcoded
.foreground(.primary)  // Instead of Color(red: 0.9, green: 0.9, blue: 0.9)
```

### ⚠️ "No reduced motion support" - Motion Warning

**Problem**: Animations may cause discomfort

**Solution**:
```swift
@Environment(\.motionReduceEnabled) var motionReduce

.animation(motionReduce ? nil : .easeInOut)
```

### ❌ "A11y matrix score too low" - Matrix Failure

**Problem**: Multiple accessibility features missing

**Solution**: Run each test locally to find issues:
1. Check VoiceOver labels
2. Verify semantic colors
3. Add motion preferences
4. Enable keyboard shortcuts

---

## GitHub Actions Status Checks

### In Pull Requests

All accessibility tests must pass before merge:

```
✅ accessibility-compliance
✅ voiceover-interaction-test  
✅ accessibility-contrast-audit
✅ accessibility-motion-test
✅ accessibility-matrix
```

If any fail:
- 🔴 **Red X**: Accessibility broken, BLOCKS MERGE
- 🟡 **Yellow Warning**: Review issue, may suggest improvements

---

## Test Results in GitHub Summary

Each test job posts results to the GitHub Actions summary:

```markdown
## ♿ Accessibility Compliance (WCAG 2.1 AA)

| Category | Count |
|----------|-------|
| ✅ Passed | 42 |
| ⚠️ Warnings | 2 |
| ❌ Failures | 0 |

## VoiceOver Accessibility Testing
✅ Button accessibility verified
✅ Focus order validated
✅ Keyboard navigation checked
```

---

## For Screen Reader Users

BrainChat accessibility is optimized for **VoiceOver** users:

### VoiceOver Features

✅ **All controls are labeled**
- Every button has `accessibilityLabel`
- Text fields have hints describing input

✅ **Logical focus order**
- Tab key navigates in reading order
- Rotor for quick navigation

✅ **Keyboard shortcuts**
- All functions accessible via keyboard
- No mouse required

✅ **Semantic structure**
- VoiceOver announces headings, lists, forms
- Proper document structure

✅ **Status announcements**
- New messages announced
- Connection status spoken
- Loading indicators announced

---

## Continuous Improvement

### Future Enhancements
- [ ] Automated contrast ratio checker (WebAIM WAVE)
- [ ] VoiceOver rotor testing
- [ ] Keyboard navigation replay testing
- [ ] Automated screenshot comparison for contrast
- [ ] Extended audio descriptions
- [ ] Multi-language support testing

---

## Questions or Issues?

For accessibility questions or to report issues:
- 📧 Accessibility: Focus on WCAG compliance
- 🐛 Report bugs: Use GitHub Issues
- 📞 Contact: Specify disability type affected

**All accessibility issues are treated as security-level severity.**

---

**Last Updated**: 2024  
**Standard**: WCAG 2.1 Level AA  
**Testing Framework**: Bash + Static Analysis
