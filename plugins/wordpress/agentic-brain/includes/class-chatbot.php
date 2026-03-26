<?php
/**
 * Front-end chatbot: floating bubble + chat window.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class Agbrain_Chatbot {

    public function init(): void {
        add_action( 'wp_enqueue_scripts', [ $this, 'enqueue_assets' ] );
        add_action( 'wp_footer', [ $this, 'render_widget' ] );
    }

    public function enqueue_assets(): void {
        if ( ! $this->is_enabled() ) {
            return;
        }

        wp_enqueue_style(
            'agbrain-chatbot',
            AGBRAIN_PLUGIN_URL . 'public/css/chatbot.css',
            [],
            AGBRAIN_VERSION
        );

        wp_enqueue_script(
            'agbrain-chatbot',
            AGBRAIN_PLUGIN_URL . 'public/js/chatbot.js',
            [],
            AGBRAIN_VERSION,
            true
        );

        $primary = sanitize_hex_color( get_option( 'agbrain_primary_color', '#6C63FF' ) );
        $user_type = 'guest';

        if ( current_user_can( 'manage_options' ) ) {
            $user_type = 'admin';
        } elseif ( is_user_logged_in() ) {
            $user_type = 'customer';
        }

        $cart_url = function_exists( 'wc_get_cart_url' ) ? wc_get_cart_url() : '';
        $wc_ajax  = class_exists( 'WC_AJAX' ) ? WC_AJAX::get_endpoint( 'add_to_cart' ) : '';

        wp_localize_script( 'agbrain-chatbot', 'agbrainChat', [
            'restUrl'        => esc_url_raw( rest_url( 'agentic-brain/v1' ) ),
            'nonce'          => wp_create_nonce( 'wp_rest' ),
            'position'       => get_option( 'agbrain_widget_position', 'bottom-right' ),
            'primaryColor'   => $primary ?: '#6C63FF',
            'welcomeMessage' => get_option( 'agbrain_welcome_message', 'Hi! How can I help you today?' ),
            'siteUrl'        => home_url(),
            'cartUrl'        => $cart_url,
            'wcAjaxUrl'      => $wc_ajax,
            'userType'       => $user_type,
            'isLoggedIn'     => is_user_logged_in(),
            'i18n'           => [
                'placeholder'   => __( 'Type a message…', 'agentic-brain' ),
                'send'          => __( 'Send', 'agentic-brain' ),
                'close'         => __( 'Close chat', 'agentic-brain' ),
                'open'          => __( 'Open chat assistant', 'agentic-brain' ),
                'thinking'      => __( 'Thinking…', 'agentic-brain' ),
                'error'         => __( 'Something went wrong. Please try again.', 'agentic-brain' ),
                'poweredBy'     => __( 'Powered by Agentic Brain', 'agentic-brain' ),
                'searching'     => __( 'Searching…', 'agentic-brain' ),
                'viewProduct'   => __( 'View product', 'agentic-brain' ),
                'addToCart'     => __( 'Add to cart', 'agentic-brain' ),
                'addedToCart'   => __( 'Added to cart.', 'agentic-brain' ),
                'cartFailed'    => __( 'Could not add this item to the cart.', 'agentic-brain' ),
                'guestLabel'    => __( 'Guest visitor', 'agentic-brain' ),
                'customerLabel' => __( 'Customer', 'agentic-brain' ),
                'adminLabel'    => __( 'Store admin', 'agentic-brain' ),
                'noResults'     => __( 'No results found.', 'agentic-brain' ),
                'syncing'       => __( 'Syncing…', 'agentic-brain' ),
            ],
        ] );

        wp_add_inline_style( 'agbrain-chatbot', sprintf(
            ':root{--agbrain-primary:%s;--agbrain-primary-hover:%s;}',
            esc_attr( $primary ?: '#6C63FF' ),
            esc_attr( $this->darken( $primary ?: '#6C63FF', 15 ) )
        ) );
    }

    public function render_widget(): void {
        if ( ! $this->is_enabled() ) {
            return;
        }

        include AGBRAIN_PLUGIN_DIR . 'public/chatbot-widget.php';
    }

    private function is_enabled(): bool {
        $enabled = get_option( 'agbrain_enabled_on', 'all' );

        if ( 'none' === $enabled ) {
            return false;
        }

        if ( 'products' === $enabled ) {
            return function_exists( 'is_product' ) && is_product();
        }

        return true;
    }

    private function darken( string $hex, int $percent ): string {
        $hex = ltrim( $hex, '#' );
        $r   = max( 0, (int) hexdec( substr( $hex, 0, 2 ) ) - (int) ( 255 * $percent / 100 ) );
        $g   = max( 0, (int) hexdec( substr( $hex, 2, 2 ) ) - (int) ( 255 * $percent / 100 ) );
        $b   = max( 0, (int) hexdec( substr( $hex, 4, 2 ) ) - (int) ( 255 * $percent / 100 ) );

        return sprintf( '#%02x%02x%02x', $r, $g, $b );
    }
}
