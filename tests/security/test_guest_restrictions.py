# SPDX-License-Identifier: Apache-2.0
from agentic_brain.security.roles import SecurityRole
from agentic_brain.security.tool_guard import check_tool_access


def test_guest_cannot_web_search():
    assert not check_tool_access(SecurityRole.GUEST, "web_search")


def test_guest_cannot_use_heavy_llm():
    assert not check_tool_access(SecurityRole.GUEST, "llm_call")


def test_guest_cannot_access_filesystem_tools():
    assert not check_tool_access(SecurityRole.GUEST, "file_read")


def test_guest_cannot_execute_code():
    assert not check_tool_access(SecurityRole.GUEST, "execute_code")


def test_guest_can_view_products():
    assert check_tool_access(SecurityRole.GUEST, "product_view")


def test_admin_can_web_search():
    assert check_tool_access(SecurityRole.FULL_ADMIN, "web_search")
