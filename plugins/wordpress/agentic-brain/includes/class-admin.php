<?php
/**
 * Admin UI for the Agentic Brain plugin.
 *
 * Provides a top-level menu, settings tabs, sync tools, and
 * a simple analytics dashboard scaffold.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class Agentic_Brain_Admin {

    /**
     * Underlying settings controller.
     *
     * @var Agbrain_Admin_Settings
     */
    private $settings;

    public function __construct() {
        $this->settings = new Agbrain_Admin_Settings();

        add_action( 'admin_menu', [ $this, 'register_menu' ] );
    }

    /**
     * Register the top-level "Agentic Brain" menu and subpages.
     */
    public function register_menu(): void {
        add_menu_page(
            __( 'Agentic Brain', 'agentic-brain' ),
            __( 'Agentic Brain', 'agentic-brain' ),
            'manage_options',
            'agentic-brain-dashboard',
            [ $this, 'render_dashboard' ],
            'dashicons-format-chat',
            56
        );

        // Settings tab \/\u2014 reuses Settings \/\u2192 Agentic Brain page.
        add_submenu_page(
            'agentic-brain-dashboard',
            __( 'Settings', 'agentic-brain' ),
            __( 'Settings', 'agentic-brain' ),
            'manage_options',
            'agentic-brain',
            [ $this->settings, 'render_page' ]
        );

        // Sync tools.
        add_submenu_page(
            'agentic-brain-dashboard',
            __( 'Sync', 'agentic-brain' ),
            __( 'Sync', 'agentic-brain' ),
            'manage_options',
            'agentic-brain-sync',
            [ $this, 'render_sync' ]
        );

        // Simple analytics overview.
        add_submenu_page(
            'agentic-brain-dashboard',
            __( 'Analytics', 'agentic-brain' ),
            __( 'Analytics', 'agentic-brain' ),
            'manage_options',
            'agentic-brain-analytics',
            [ $this, 'render_analytics' ]
        );

        // Also expose the settings screen under Settings for familiarity.
        if ( method_exists( $this->settings, 'add_menu' ) ) {
            $this->settings->add_menu();
        }
    }

    /**
     * Overview dashboard \/\u2014 high-level status and quick links.
     */
    public function render_dashboard(): void {
        if ( ! current_user_can( 'manage_options' ) ) {
            return;
        }

        $request = new WP_REST_Request( 'GET', '/agentic-brain/v1/status' );
        $status  = rest_do_request( $request );

        $data = $status instanceof WP_Error || $status->is_error() ? [] : $status->get_data();
        ?>
        <div class="wrap agbrain-dashboard">
            <h1>
                <span class="agbrain-logo" aria-hidden="true">🧠</span>
                <?php esc_html_e( 'Agentic Brain', 'agentic-brain' ); ?>
            </h1>

            <p class="description">
                <?php esc_html_e( 'Configure the AI chatbot, sync content, and view basic analytics.', 'agentic-brain' ); ?>
            </p>

            <h2><?php esc_html_e( 'Connection Status', 'agentic-brain' ); ?></h2>
            <ul>
                <li>
                    <strong><?php esc_html_e( 'API configured:', 'agentic-brain' ); ?></strong>
                    <?php echo ! empty( $data['api_configured'] ) ? esc_html__( 'Yes', 'agentic-brain' ) : esc_html__( 'No', 'agentic-brain' ); ?>
                </li>
                <li>
                    <strong><?php esc_html_e( 'WooCommerce active:', 'agentic-brain' ); ?></strong>
                    <?php echo ! empty( $data['has_woocommerce'] ) ? esc_html__( 'Yes', 'agentic-brain' ) : esc_html__( 'No', 'agentic-brain' ); ?>
                </li>
                <li>
                    <strong><?php esc_html_e( 'Last sync:', 'agentic-brain' ); ?></strong>
                    <?php echo ! empty( $data['last_sync'] ) ? esc_html( $data['last_sync'] ) : esc_html__( 'Never', 'agentic-brain' ); ?>
                </li>
            </ul>
        </div>
        <?php
    }

    /**
     * Wrapper around settings sync section for a dedicated submenu.
     */
    public function render_sync(): void {
        if ( ! current_user_can( 'manage_options' ) ) {
            return;
        }

        // Reuse the existing settings template, which already contains manual sync UI.
        $this->settings->render_page();
    }

    /**
     * Placeholder analytics dashboard.
     *
     * Can be extended later to pull real conversation stats from the backend.
     */
    public function render_analytics(): void {
        if ( ! current_user_can( 'manage_options' ) ) {
            return;
        }
        ?>
        <div class="wrap agbrain-analytics">
            <h1><?php esc_html_e( 'Agentic Brain Analytics', 'agentic-brain' ); ?></h1>
            <p class="description">
                <?php esc_html_e( 'This dashboard will show chat volume, popular intents, and conversion impact once connected to an Agentic Brain backend.', 'agentic-brain' ); ?>
            </p>
        </div>
        <?php
    }
}
