<?php
/**
 * WordPress configuration for Docker demo.
 *
 * This file is used as a template by the official wordpress docker entrypoint.
 */

if (!function_exists('getenv_docker')) {
    // phpcs:ignore WordPress.PHP.DiscouragedPHPFunctions.runtime_configuration_putenv
    function getenv_docker($env, $default = '') {
        if ($fileEnv = getenv($env . '_FILE')) {
            return rtrim(file_get_contents($fileEnv), "\r\n");
        }

        $val = getenv($env);
        return $val !== false ? $val : $default;
    }
}

define('DB_NAME', getenv_docker('WORDPRESS_DB_NAME', 'wordpress_demo'));
define('DB_USER', getenv_docker('WORDPRESS_DB_USER', 'wp_demo'));
define('DB_PASSWORD', getenv_docker('WORDPRESS_DB_PASSWORD', 'demo_wp_pass_2026'));
define('DB_HOST', getenv_docker('WORDPRESS_DB_HOST', 'mariadb:3306'));
define('DB_CHARSET', 'utf8');
define('DB_COLLATE', '');

// Demo-friendly debugging
define('WP_DEBUG', true);
define('WP_DEBUG_LOG', true);
define('WP_DEBUG_DISPLAY', true);
define('SCRIPT_DEBUG', true);
define('WP_ENVIRONMENT_TYPE', 'development');

// Used by demo/entrypoint.sh
define('WP_AGENTIC_BRAIN_AUTO_PLUGINS', getenv_docker('WP_AGENTIC_BRAIN_AUTO_PLUGINS', 'woocommerce agentic-brain'));

$table_prefix = getenv_docker('WORDPRESS_TABLE_PREFIX', 'wp_');

// Absolute path to the WordPress directory.
if (!defined('ABSPATH')) {
    define('ABSPATH', __DIR__ . '/');
}

require_once ABSPATH . 'wp-settings.php';
