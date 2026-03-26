<?php
/**
 * Plugin Name:       Agentic Brain AI Chatbot
 * Plugin URI:        https://github.com/ecomlounge/agentic-brain
 * Description:       AI-powered chatbot for WooCommerce stores.
 * Version:           1.0.0
 * Requires at least: 6.0
 * Requires PHP:      8.0
 * Author:            Joseph Webber
 * Author URI:        https://github.com/joseph-webber
 * License:           Apache-2.0
 * Text Domain:       agentic-brain
 * Domain Path:       /languages
 * WC requires at least: 5.0
 * WC tested up to:   8.0
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

define( 'AGBRAIN_VERSION', '1.0.0' );
define( 'AGBRAIN_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );
define( 'AGBRAIN_PLUGIN_URL', plugin_dir_url( __FILE__ ) );
define( 'AGBRAIN_PLUGIN_BASENAME', plugin_basename( __FILE__ ) );

require_once AGBRAIN_PLUGIN_DIR . 'includes/class-api-client.php';
require_once AGBRAIN_PLUGIN_DIR . 'includes/class-product-sync.php';
require_once AGBRAIN_PLUGIN_DIR . 'includes/class-rag-sync.php';
require_once AGBRAIN_PLUGIN_DIR . 'includes/class-chatbot.php';
require_once AGBRAIN_PLUGIN_DIR . 'includes/class-admin-settings.php';
require_once AGBRAIN_PLUGIN_DIR . 'includes/class-admin.php';
require_once AGBRAIN_PLUGIN_DIR . 'includes/class-rest-api.php';
require_once AGBRAIN_PLUGIN_DIR . 'includes/class-hooks.php';
require_once AGBRAIN_PLUGIN_DIR . 'includes/class-agentic-brain.php';

function agbrain_activate(): void {
    $defaults = [
        'api_url'          => '',
        'api_key'          => '',
        'widget_position'  => 'bottom-right',
        'primary_color'    => '#6C63FF',
        'enabled_on'       => 'all',
        'woo_auto_sync'    => 'yes',
        'sync_posts'       => 'yes',
        'welcome_message'  => 'Hi! How can I help you today?',
    ];

    foreach ( $defaults as $key => $value ) {
        if ( false === get_option( "agbrain_{$key}" ) ) {
            add_option( "agbrain_{$key}", $value );
        }
    }

    if ( ! wp_next_scheduled( 'agbrain_daily_sync' ) ) {
        wp_schedule_event( time(), 'daily', 'agbrain_daily_sync' );
    }
}
register_activation_hook( __FILE__, 'agbrain_activate' );

function agbrain_deactivate(): void {
    wp_clear_scheduled_hook( 'agbrain_daily_sync' );
}
register_deactivation_hook( __FILE__, 'agbrain_deactivate' );

/**
 * Check whether WooCommerce is active.
 *
 * Plugin works without WooCommerce, but product sync and
 * AI product search features depend on it.
 *
 * @return bool
 */
function agbrain_has_woocommerce(): bool {
    return class_exists( 'WooCommerce' );
}

/**
 * Display an admin notice when WooCommerce is missing.
 */
function agbrain_woocommerce_admin_notice(): void {
    if ( agbrain_has_woocommerce() || ! current_user_can( 'manage_options' ) ) {
        return;
    }

    if ( function_exists( 'get_current_screen' ) ) {
        $screen = get_current_screen();
        if ( $screen && 'plugins' !== $screen->id ) {
            return;
        }
    }

    echo '<div class="notice notice-warning"><p>';
    echo esc_html__( 'Agentic Brain AI Chatbot: WooCommerce is not active. Product sync and AI product search will be disabled until WooCommerce is installed and activated.', 'agentic-brain' );
    echo '</p></div>';
}
add_action( 'admin_notices', 'agbrain_woocommerce_admin_notice' );

add_action( 'before_woocommerce_init', function () {
    if ( class_exists( \Automattic\WooCommerce\Utilities\FeaturesUtil::class ) ) {
        \Automattic\WooCommerce\Utilities\FeaturesUtil::declare_compatibility(
            'custom_order_tables',
            __FILE__,
            true
        );
    }
} );

add_action( 'plugins_loaded', function () {
    load_plugin_textdomain( 'agentic-brain', false, dirname( AGBRAIN_PLUGIN_BASENAME ) . '/languages' );
    Agentic_Brain::instance();
} );
