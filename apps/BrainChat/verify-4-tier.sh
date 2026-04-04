#!/bin/bash
# Verify 4-Tier Security Model Implementation

echo "🔒 Verifying 4-Tier Security Model..."
echo ""

# Check for the 4 security roles
echo "✓ Checking SecurityRole enum..."
grep -q "case fullAdmin" Sources/BrainChat/Security/SecurityRole.swift && echo "  ✅ FULL_ADMIN exists"
grep -q "case safeAdmin" Sources/BrainChat/Security/SecurityRole.swift && echo "  ✅ SAFE_ADMIN exists"
grep -q "case user" Sources/BrainChat/Security/SecurityRole.swift && echo "  ✅ USER exists"
grep -q "case guest" Sources/BrainChat/Security/SecurityRole.swift && echo "  ✅ GUEST exists"

# Check for YOLO confirmation logic
echo ""
echo "✓ Checking YOLO confirmation logic..."
grep -q "yoloRequiresConfirmation" Sources/BrainChat/Security/SecurityRole.swift && echo "  ✅ yoloRequiresConfirmation property exists"
grep -q "isDangerousOperation" YoloExecutor.swift && echo "  ✅ Dangerous operation detection exists"

# Check for updated tests
echo ""
echo "✓ Checking tests..."
grep -q "testCanYolo" Tests/Security/SecurityRoleTests.swift && echo "  ✅ YOLO permission tests exist"
grep -q "testCanAccessFilesystem" Tests/Security/SecurityRoleTests.swift && echo "  ✅ Filesystem permission tests exist"
grep -q "testCanAccessAPIs" Tests/Security/SecurityRoleTests.swift && echo "  ✅ API permission tests exist"

# Check default role
echo ""
echo "✓ Checking default configuration..."
grep -q "defaultRoleForJoseph: SecurityRole = .fullAdmin" Sources/BrainChat/Security/SecurityManager.swift && echo "  ✅ Joseph defaults to FULL_ADMIN"

echo ""
echo "🎉 4-Tier Security Model verification complete!"
