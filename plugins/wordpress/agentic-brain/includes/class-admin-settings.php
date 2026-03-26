<?php
/**
 * Admin settings page under Settings → Agentic Brain.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class Agbrain_Admin_Settings {

    public function __construct() {
        add_action( 'admin_menu', [ $this, 'add_menu' ] );
        add_action( 'admin_init', [ $this, 'register_settings' ] );
        add_action( 'admin_enqueue_scripts', [ $this, 'enqueue_admin_assets' ] );
    }

    public function add_menu(): void {
        add_options_page(
            __( 'Agentic Brain', 'agentic-brain' ),
            __( 'Agentic Brain', 'agentic-brain' ),
            'manage_options',
            'agentic-brain',
            [ $this, 'render_page' ]
        );
    }

    public function register_settings(): void {
        add_settings_section( 'agbrain_connection', __( 'Connection', 'agentic-brain' ), '__return_false', 'agentic-brain' );

        $this->field( 'api_url', __( 'API Endpoint URL', 'agentic-brain' ), 'url', 'agbrain_connection',
            __( 'Paste your Agentic Brain server URL here. For most stores this is the only required setting.', 'agentic-brain' ) );

        $this->field( 'api_key', __( 'API Key (optional)', 'agentic-brain' ), 'password', 'agbrain_connection',
            __( 'Leave blank if your backend does not require a bearer token.', 'agentic-brain' ) );

        add_settings_section( 'agbrain_appearance', __( 'Appearance', 'agentic-brain' ), '__return_false', 'agentic-brain' );

        $this->field( 'widget_position', __( 'Widget Position', 'agentic-brain' ), 'select', 'agbrain_appearance', '', [
            'bottom-right' => __( 'Bottom Right', 'agentic-brain' ),
            'bottom-left'  => __( 'Bottom Left', 'agentic-brain' ),
        ] );

        $this->field( 'primary_color', __( 'Primary Colour', 'agentic-brain' ), 'color', 'agbrain_appearance',
            __( 'Accent colour used for the chat bubble and buttons.', 'agentic-brain' ) );

        $this->field( 'welcome_message', __( 'Welcome Message', 'agentic-brain' ), 'text', 'agbrain_appearance',
            __( 'Greeting shown when the chat window opens.', 'agentic-brain' ) );

        $this->field( 'enabled_on', __( 'Show Widget On', 'agentic-brain' ), 'select', 'agbrain_appearance', '', [
            'all'      => __( 'All Pages', 'agentic-brain' ),
            'products' => __( 'WooCommerce Product Pages Only', 'agentic-brain' ),
            'none'     => __( 'Disabled (shortcode only)', 'agentic-brain' ),
        ] );

        add_settings_section( 'agbrain_sync', __( 'Content Sync', 'agentic-brain' ), '__return_false', 'agentic-brain' );

        $this->field( 'woo_auto_sync', __( 'Auto-Sync Products', 'agentic-brain' ), 'select', 'agbrain_sync',
            __( 'Push product changes to the Agentic Brain automatically.', 'agentic-brain' ), [
                'yes' => __( 'Enabled', 'agentic-brain' ),
                'no'  => __( 'Disabled', 'agentic-brain' ),
            ] );

        $this->field( 'sync_posts', __( 'Sync Posts & Pages', 'agentic-brain' ), 'select', 'agbrain_sync',
            __( 'Include blog posts and pages in the AI knowledge base.', 'agentic-brain' ), [
                'yes' => __( 'Enabled', 'agentic-brain' ),
                'no'  => __( 'Disabled', 'agentic-brain' ),
            ] );
    }

    private function field( string $key, string $label, string $type, string $section, string $desc = '', array $options = [] ): void {
        $option_name = "agbrain_{$key}";

        register_setting( 'agentic-brain', $option_name, [
            'type'              => 'string',
            'sanitize_callback' => [ $this, 'sanitize_field' ],
            'default'           => '',
        ] );

        add_settings_field( $option_name, $label, function () use ( $option_name, $type, $desc, $options ) {
            $value = (string) get_option( $option_name, '' );

            switch ( $type ) {
                case 'select':
                    echo '<select name="' . esc_attr( $option_name ) . '" id="' . esc_attr( $option_name ) . '">';
                    foreach ( $options as $val => $text ) {
                        printf(
                            '<option value="%s" %s>%s</option>',
                            esc_attr( $val ),
                            selected( $value, $val, false ),
                            esc_html( $text )
                        );
                    }
                    echo '</select>';
                    break;

                case 'color':
                    printf(
                        '<input type="color" name="%s" id="%s" value="%s" />',
                        esc_attr( $option_name ),
                        esc_attr( $option_name ),
                        esc_attr( $value ?: '#6C63FF' )
                    );
                    break;

                case 'password':
                    printf(
                        '<input type="password" name="%s" id="%s" value="%s" class="regular-text" autocomplete="off" />',
                        esc_attr( $option_name ),
                        esc_attr( $option_name ),
                        esc_attr( $value )
                    );
                    break;

                default:
                    printf(
                        '<input type="%s" name="%s" id="%s" value="%s" class="regular-text" />',
                        esc_attr( $type ),
                        esc_attr( $option_name ),
                        esc_attr( $option_name ),
                        esc_attr( $value )
                    );
            }

            if ( $desc ) {
                echo '<p class="description">' . esc_html( $desc ) . '</p>';
            }
        }, 'agentic-brain', $section );
    }

    public function sanitize_field( $value ): string {
        if ( ! is_string( $value ) ) {
            return '';
        }

        if ( filter_var( $value, FILTER_VALIDATE_URL ) ) {
            return esc_url_raw( $value );
        }

        if ( preg_match( '/^#[a-f0-9]{6}$/i', $value ) ) {
            return $value;
        }

        return sanitize_text_field( $value );
    }

    public function enqueue_admin_assets( string $hook ): void {
        if ( 'settings_page_agentic-brain' !== $hook ) {
            return;
        }

        wp_enqueue_style(
            'agbrain-admin',
            AGBRAIN_PLUGIN_URL . 'admin/css/admin.css',
            [],
            AGBRAIN_VERSION
        );

        wp_enqueue_script(
            'agbrain-admin-settings',
            AGBRAIN_PLUGIN_URL . 'admin/js/settings.js',
            [],
            AGBRAIN_VERSION,
            true
        );

        wp_localize_script( 'agbrain-admin-settings', 'agbrainAdmin', [
            'restUrl'        => esc_url_raw( rest_url( 'agentic-brain/v1' ) ),
            'nonce'          => wp_create_nonce( 'wp_rest' ),
            'lastSync'       => (string) get_option( 'agbrain_last_sync', '' ),
            'lastProductSync'=> (string) get_option( 'agbrain_last_product_sync', '' ),
            'i18n'           => [
                'testing'        => __( 'Testing connection…', 'agentic-brain' ),
                'connected'      => __( 'Connection successful.', 'agentic-brain' ),
                'connectFailed'  => __( 'Connection failed.', 'agentic-brain' ),
                'syncing'        => __( 'Syncing…', 'agentic-brain' ),
                'syncComplete'   => __( 'Sync complete.', 'agentic-brain' ),
                'networkError'   => __( 'Network error. Please try again.', 'agentic-brain' ),
                'invalidUrl'     => __( 'Enter a valid URL that starts with http:// or https://', 'agentic-brain' ),
                'urlLooksGood'   => __( 'URL format looks good.', 'agentic-brain' ),
            ],
        ] );
    }

    public function render_page(): void {
        include AGBRAIN_PLUGIN_DIR . 'admin/settings-page.php';
    }
}
