#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Example: API-Based Security Architecture

This demonstrates The key insight: customer chatbots should ONLY
access external APIs, not have direct machine access.
"""

import asyncio

from agentic_brain.integrations import (
    WooCommerceRole,
    WordPressRole,
    create_woocommerce_client,
    create_wordpress_client,
)
from agentic_brain.security.roles import SecurityRole


async def example_wordpress_customer_support():
    """Example: WordPress customer support chatbot."""

    print("\n" + "=" * 60)
    print("EXAMPLE 1: WordPress Customer Support Chatbot")
    print("=" * 60)

    # Create a content contributor chatbot
    # - WordPress role: AUTHOR (can create and publish posts)
    # - Chatbot role: USER (API-only, no machine access)

    wp_client = create_wordpress_client(
        site_url="https://example.com",
        username="content_bot",
        app_password="xxxx xxxx xxxx xxxx",
        wp_role=WordPressRole.AUTHOR,
        chatbot_role=SecurityRole.USER,
    )

    print("\n✅ Created WordPress API client")
    print(f"   - WordPress Role: {WordPressRole.AUTHOR.value}")
    print(f"   - Chatbot Role: {SecurityRole.USER.value} (API-ONLY)")
    print(f"   - Can create posts: {wp_client.capabilities.can_create_posts}")
    print(f"   - Can publish posts: {wp_client.capabilities.can_publish_posts}")
    print(f"   - Can manage users: {wp_client.capabilities.can_create_users}")

    # What the chatbot CAN do:
    print("\n📝 What this chatbot CAN do:")
    print("   ✅ List posts (wp_client.list_posts())")
    print("   ✅ Create drafts (wp_client.create_post())")
    print("   ✅ Publish posts (wp_client.update_post())")
    print("   ✅ Upload media (wp_client.upload_media())")

    # What the chatbot CANNOT do:
    print("\n🚫 What this chatbot CANNOT do:")
    print("   ❌ Access file system (no shell access)")
    print("   ❌ Run shell commands (no YOLO)")
    print("   ❌ Modify WordPress core files")
    print("   ❌ Bypass WordPress permissions")
    print("   ❌ Manage users (not admin)")

    await wp_client.api_controller.close()


async def example_woocommerce_customer():
    """Example: WooCommerce customer order assistant."""

    print("\n" + "=" * 60)
    print("EXAMPLE 2: WooCommerce Customer Order Assistant")
    print("=" * 60)

    # Create a customer order assistant
    # - WooCommerce role: CUSTOMER (can only see own orders)
    # - Chatbot role: USER (API-only, no machine access)
    # - customer_id: CRITICAL - can only see this customer's orders

    wc_client = create_woocommerce_client(
        site_url="https://shop.example.com",
        consumer_key="ck_xxxxx",
        consumer_secret="cs_xxxxx",
        wc_role=WooCommerceRole.CUSTOMER,
        chatbot_role=SecurityRole.USER,
        customer_id=42,  # Can only see customer #42's orders
    )

    print("\n✅ Created WooCommerce API client")
    print(f"   - WooCommerce Role: {WooCommerceRole.CUSTOMER.value}")
    print(f"   - Chatbot Role: {SecurityRole.USER.value} (API-ONLY)")
    print("   - Customer ID: 42 (can only see THIS customer's orders)")
    print(f"   - Can view orders: {wc_client.capabilities.can_view_own_orders}")
    print(f"   - Can edit orders: {wc_client.capabilities.can_edit_orders}")
    print(f"   - Can manage products: {wc_client.capabilities.can_create_products}")

    # What the chatbot CAN do:
    print("\n📦 What this chatbot CAN do:")
    print("   ✅ View customer #42's orders")
    print("   ✅ View products")
    print("   ✅ View customer #42's profile")

    # What the chatbot CANNOT do:
    print("\n🚫 What this chatbot CANNOT do:")
    print("   ❌ View other customers' orders (SecurityViolation)")
    print("   ❌ Edit any orders (customers can't edit)")
    print("   ❌ Create products (not shop manager)")
    print("   ❌ Access database directly")
    print("   ❌ Run shell commands")

    # Security demonstration:
    print("\n🔒 Security Enforcement:")
    print("   - Trying to access customer #99's orders...")
    try:
        # This will raise SecurityViolation
        await wc_client.list_orders(customer=99)
        print("   ❌ SECURITY FAILURE: Should have blocked this!")
    except Exception as e:
        print(f"   ✅ BLOCKED: {e}")

    await wc_client.api_controller.close()


async def example_shop_manager():
    """Example: WooCommerce shop manager assistant."""

    print("\n" + "=" * 60)
    print("EXAMPLE 3: WooCommerce Shop Manager Assistant")
    print("=" * 60)

    # Create a shop manager assistant
    # - WooCommerce role: SHOP_MANAGER (can manage products and all orders)
    # - Chatbot role: USER (API-only, no machine access)

    wc_client = create_woocommerce_client(
        site_url="https://shop.example.com",
        consumer_key="ck_shop_mgr",
        consumer_secret="cs_shop_mgr",
        wc_role=WooCommerceRole.SHOP_MANAGER,
        chatbot_role=SecurityRole.USER,
    )

    print("\n✅ Created WooCommerce API client")
    print(f"   - WooCommerce Role: {WooCommerceRole.SHOP_MANAGER.value}")
    print(f"   - Chatbot Role: {SecurityRole.USER.value} (API-ONLY)")
    print(f"   - Can view all orders: {wc_client.capabilities.can_view_orders}")
    print(f"   - Can edit orders: {wc_client.capabilities.can_edit_orders}")
    print(f"   - Can manage products: {wc_client.capabilities.can_create_products}")
    print(f"   - Can view reports: {wc_client.capabilities.can_view_reports}")

    # What the chatbot CAN do:
    print("\n📊 What this chatbot CAN do:")
    print("   ✅ View ALL orders (any customer)")
    print("   ✅ Edit orders (mark as shipped, etc.)")
    print("   ✅ Create products")
    print("   ✅ Edit products")
    print("   ✅ Delete products")
    print("   ✅ View sales reports")

    # What the chatbot CANNOT do:
    print("\n🚫 What this chatbot STILL CANNOT do:")
    print("   ❌ Access file system (API-only mode)")
    print("   ❌ Run shell commands (API-only mode)")
    print("   ❌ Modify system files (API-only mode)")

    await wc_client.api_controller.close()


async def example_api_access_log():
    """Example: API access logging and auditing."""

    print("\n" + "=" * 60)
    print("EXAMPLE 4: API Access Logging")
    print("=" * 60)

    from agentic_brain.security.api_access import (
        APIAccessController,
        APIEndpoint,
        APIScope,
        AuthType,
    )

    # Create controller
    controller = APIAccessController(SecurityRole.USER)

    # Register API
    endpoint = APIEndpoint(
        name="wordpress",
        base_url="https://example.com/wp-json/wp/v2",
        auth_type=AuthType.BEARER,
        allowed_scopes=[APIScope.READ],
        rate_limit=60,
    )

    controller.register_api(endpoint, {"token": "test_token"})

    print("\n✅ Registered API: wordpress")
    print(f"   - Base URL: {endpoint.base_url}")
    print(f"   - Scopes: {[s.value for s in endpoint.allowed_scopes]}")
    print(f"   - Rate limit: {endpoint.rate_limit} req/min")

    # Simulate API calls (mocked)
    print("\n📊 Access Log (all API calls are logged):")

    # Add some mock log entries
    controller.access_log.extend(
        [
            {
                "timestamp": 1709404800,
                "role": "user",
                "api": "wordpress",
                "method": "GET",
                "path": "/posts",
                "scope": "read",
                "status": 200,
                "success": True,
            },
            {
                "timestamp": 1709404801,
                "role": "user",
                "api": "wordpress",
                "method": "POST",
                "path": "/posts",
                "scope": "write",
                "status": 403,
                "success": False,
                "error": "Access denied to wordpress with scope write",
            },
        ]
    )

    # Get access log
    log = controller.get_access_log()

    for entry in log:
        status_icon = "✅" if entry.get("success") else "❌"
        print(f"\n   {status_icon} {entry['method']} {entry['path']}")
        print(f"      Status: {entry.get('status', 'N/A')}")
        print(f"      Scope: {entry['scope']}")
        if not entry.get("success"):
            print(f"      Error: {entry.get('error')}")

    # Get API info
    print("\n📋 Registered APIs:")
    for api_name in controller.get_registered_apis():
        info = controller.get_api_info(api_name)
        print(f"\n   - {info['name']}")
        print(f"     URL: {info['base_url']}")
        print(f"     Scopes: {info['allowed_scopes']}")
        print(f"     Role: {info.get('api_role', 'N/A')}")


async def main():
    """Run all examples."""

    print("\n" + "=" * 60)
    print("API-BASED SECURITY ARCHITECTURE EXAMPLES")
    print("Key Insight: Customer chatbots = API-only access")
    print("=" * 60)

    # Note: These examples use mock credentials
    # In production, use real WordPress/WooCommerce credentials

    print("\n⚠️  NOTE: Using mock credentials (examples only)")
    print("    In production, use real API keys and passwords")

    await example_wordpress_customer_support()
    await example_woocommerce_customer()
    await example_shop_manager()
    await example_api_access_log()

    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print(
        """
1. USER/CUSTOMER chatbots = API-ONLY (no machine access)
2. Permissions controlled by API's role system (WordPress/WooCommerce)
3. API keys scoped to minimum required access
4. Rate limiting prevents abuse
5. All access logged for auditing
6. Customers can only see their own data
7. No direct database/file system access

ADMIN still has full machine access + API access.
DEVELOPER has machine access with guardrails.
GUEST has read-only API access only.
    """
    )


if __name__ == "__main__":
    asyncio.run(main())
