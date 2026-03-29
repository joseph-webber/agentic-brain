# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""WordPress/WooCommerce hooks integration.

This module generates a small WordPress plugin that attaches to useful actions
and forwards events to an Agentic Brain webhook endpoint.

Why generate code from Python?
- keeps the Brain's integration points versioned alongside the bots
- can be rendered and shipped as part of an installer
- makes it easy to keep hook coverage consistent across themes
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WordPressHookConfig:
    plugin_slug: str = "agentic-brain-hooks"
    plugin_name: str = "Agentic Brain Hooks"
    webhook_url: str = "https://example.com/webhooks/wordpress"
    webhook_secret: str = "change-me"
    include_woocommerce: bool = True


WP_ACTION_HOOKS = [
    "save_post",
    "transition_post_status",
    "comment_post",
    "wp_set_comment_status",
    "wp_insert_comment",
]

WOO_ACTION_HOOKS = [
    "woocommerce_new_order",
    "woocommerce_order_status_changed",
    "woocommerce_product_set_stock",
    "woocommerce_checkout_order_processed",
]

THEME_INTEGRATION_HOOKS = [
    "wp_footer",
]


def generate_wp_hooks_plugin(config: WordPressHookConfig) -> dict[str, str]:
    """Generate a WordPress plugin that forwards WP/Woo events to a webhook."""

    return {f"{config.plugin_slug}.php": _generate_php(config)}


def _generate_php(config: WordPressHookConfig) -> str:
    slug = config.plugin_slug.replace("-", "_")
    woo_block = (
        _generate_woocommerce_block(config, slug) if config.include_woocommerce else ""
    )

    return f"""<?php
/**
 * Plugin Name: {config.plugin_name}
 * Description: Forwards WordPress (and optional WooCommerce) events to Agentic Brain.
 * Version: 0.1.0
 */

if (!defined('ABSPATH')) {{ exit; }}

function {slug}_sign($body) {{
    return hash_hmac('sha256', $body, '{config.webhook_secret}');
}}

function {slug}_send_event($event_type, $payload) {{
    $body = wp_json_encode(array(
        'event_type' => $event_type,
        'payload' => $payload,
        'site_url' => get_site_url(),
        'timestamp' => time(),
    ));

    $response = wp_remote_post('{config.webhook_url}', array(
        'timeout' => 10,
        'headers' => array(
            'Content-Type' => 'application/json',
            'X-Agentic-Brain-Signature' => {slug}_sign($body),
        ),
        'body' => $body,
    ));

    return $response;
}}

// Core WP hooks
add_action('save_post', function($post_id, $post, $update) {{
    {slug}_send_event('wp.save_post', array(
        'post_id' => $post_id,
        'post_type' => $post->post_type,
        'status' => $post->post_status,
        'update' => $update,
    ));
}}, 10, 3);

add_action('transition_post_status', function($new_status, $old_status, $post) {{
    {slug}_send_event('wp.transition_post_status', array(
        'post_id' => $post->ID,
        'post_type' => $post->post_type,
        'old_status' => $old_status,
        'new_status' => $new_status,
    ));
}}, 10, 3);

add_action('comment_post', function($comment_id, $comment_approved, $commentdata) {{
    {slug}_send_event('wp.comment_post', array(
        'comment_id' => $comment_id,
        'approved' => $comment_approved,
    ));
}}, 10, 3);

add_action('wp_insert_comment', function($comment_id, $comment) {{
    {slug}_send_event('wp.insert_comment', array(
        'comment_id' => $comment_id,
        'post_id' => $comment->comment_post_ID,
        'author' => $comment->comment_author,
    ));
}}, 10, 2);

// Theme integration point
add_action('wp_footer', function() {{
    // Handy for themes to detect the plugin; no network call.
    echo '<!-- Agentic Brain Hooks active -->';
}});

{woo_block}
"""


def _generate_woocommerce_block(config: WordPressHookConfig, slug: str) -> str:
    return f"""
// WooCommerce hooks (if WooCommerce is installed)
if (class_exists('WooCommerce')) {{
    add_action('woocommerce_new_order', function($order_id) {{
        {slug}_send_event('woo.new_order', array('order_id' => $order_id));
    }}, 10, 1);

    add_action('woocommerce_order_status_changed', function($order_id, $from, $to) {{
        {slug}_send_event('woo.order_status_changed', array(
            'order_id' => $order_id,
            'from' => $from,
            'to' => $to,
        ));
    }}, 10, 3);

    add_action('woocommerce_product_set_stock', function($product) {{
        {slug}_send_event('woo.product_stock_updated', array(
            'product_id' => $product->get_id(),
            'stock_quantity' => $product->get_stock_quantity(),
            'stock_status' => $product->get_stock_status(),
        ));
    }}, 10, 1);

    add_action('woocommerce_checkout_order_processed', function($order_id) {{
        {slug}_send_event('woo.checkout_order_processed', array('order_id' => $order_id));
    }}, 10, 1);
}}
"""


__all__ = [
    "WordPressHookConfig",
    "WP_ACTION_HOOKS",
    "WOO_ACTION_HOOKS",
    "THEME_INTEGRATION_HOOKS",
    "generate_wp_hooks_plugin",
]
