<?php
/**
 * Main orchestrator — wires admin, front-end, and sync together.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

final class Agentic_Brain {

    private static ?self $instance = null;

    private Agbrain_API_Client $api_client;
    private Agbrain_Product_Sync $product_sync;
    private Agbrain_RAG_Sync $content_sync;

    public static function instance(): self {
        if ( null === self::$instance ) {
            self::$instance = new self();
        }

        return self::$instance;
    }

    private function __construct() {
        $this->api_client   = new Agbrain_API_Client();
        $this->product_sync = new Agbrain_Product_Sync( $this->api_client );
        $this->content_sync = new Agbrain_RAG_Sync( $this->api_client, $this->product_sync );

        if ( is_admin() ) {
            new Agentic_Brain_Admin();
        }

        $chatbot = new Agbrain_Chatbot();
        $chatbot->init();

        $this->product_sync->init();
        $this->content_sync->init();

        $hooks = new Agentic_Brain_Hooks();
        $hooks->init();

        add_shortcode( 'agentic_chat', [ $this, 'shortcode_chat' ] );
        add_shortcode( 'agentic_product_search', [ $this, 'shortcode_product_search' ] );

        add_action( 'init', [ $this, 'register_blocks' ] );
        add_filter( 'plugin_action_links_' . AGBRAIN_PLUGIN_BASENAME, [ $this, 'settings_link' ] );
        add_action( 'rest_api_init', [ $this, 'register_rest_routes' ] );

        new Agentic_Brain_REST_API();
    }

    public function shortcode_chat( array $atts = [] ): string {
        $atts = shortcode_atts( [
            'welcome' => get_option( 'agbrain_welcome_message', 'Hi! How can I help you today?' ),
            'height'  => '500px',
        ], $atts, 'agentic_chat' );

        ob_start();
        include AGBRAIN_PLUGIN_DIR . 'public/chatbot-widget.php';

        return ob_get_clean();
    }

    public function shortcode_product_search( array $atts = [] ): string {
        $atts = shortcode_atts( [
            'placeholder' => __( 'Search products with AI…', 'agentic-brain' ),
            'limit'       => 6,
        ], $atts, 'agentic_product_search' );

        $id = 'agbrain-search-' . wp_unique_id();

        return sprintf(
            '<div id="%1$s" class="agbrain-product-search" data-limit="%2$d">
                <input type="text" class="agbrain-search-input" placeholder="%3$s"
                       aria-label="%3$s" />
                <div class="agbrain-search-results" role="region"
                     aria-live="polite" aria-label="%4$s"></div>
            </div>',
            esc_attr( $id ),
            (int) $atts['limit'],
            esc_attr( $atts['placeholder'] ),
            esc_attr__( 'Search results', 'agentic-brain' )
        );
    }

    public function register_blocks(): void {
        if ( ! function_exists( 'register_block_type' ) ) {
            return;
        }

        register_block_type( 'agentic-brain/chat', [
            'render_callback' => [ $this, 'shortcode_chat' ],
            'attributes'      => [
                'welcome' => [ 'type' => 'string', 'default' => '' ],
                'height'  => [ 'type' => 'string', 'default' => '500px' ],
            ],
        ] );

        register_block_type( 'agentic-brain/product-search', [
            'render_callback' => [ $this, 'shortcode_product_search' ],
            'attributes'      => [
                'placeholder' => [ 'type' => 'string', 'default' => '' ],
                'limit'       => [ 'type' => 'number', 'default' => 6 ],
            ],
        ] );
    }

    public function register_rest_routes(): void {
        register_rest_route( 'agentic-brain/v1', '/chat', [
            'methods'             => 'POST',
            'callback'            => [ $this, 'rest_chat' ],
            'permission_callback' => '__return_true',
        ] );

        register_rest_route( 'agentic-brain/v1', '/search', [
            'methods'             => 'POST',
            'callback'            => [ $this, 'rest_search' ],
            'permission_callback' => '__return_true',
        ] );

        register_rest_route( 'agentic-brain/v1', '/sync', [
            'methods'             => 'POST',
            'callback'            => [ $this, 'rest_trigger_sync' ],
            'permission_callback' => function () {
                return current_user_can( 'manage_options' );
            },
        ] );

        register_rest_route( 'agentic-brain/v1', '/connection-test', [
            'methods'             => 'POST',
            'callback'            => [ $this, 'rest_test_connection' ],
            'permission_callback' => function () {
                return current_user_can( 'manage_options' );
            },
        ] );
    }

    public function rest_chat( WP_REST_Request $request ): WP_REST_Response {
        $message    = sanitize_text_field( (string) ( $request->get_param( 'message' ) ?? '' ) );
        $session_id = sanitize_text_field( (string) ( $request->get_param( 'session_id' ) ?? '' ) );
        $context    = $request->get_param( 'context' );
        $context    = is_array( $context ) ? $context : [];

        if ( '' === $message ) {
            return new WP_REST_Response( [ 'success' => false, 'error' => 'Message is required.' ], 400 );
        }

        $response = $this->api_client->send_chat_message( $message, $session_id, array_merge(
            $this->get_request_context(),
            $context
        ) );

        $status = ! empty( $response['error'] ) ? 502 : 200;

        return new WP_REST_Response( $this->normalize_chat_response( $response ), $status );
    }

    public function rest_search( WP_REST_Request $request ): WP_REST_Response {
        $query = sanitize_text_field( (string) ( $request->get_param( 'query' ) ?? '' ) );
        $limit = (int) ( $request->get_param( 'limit' ) ?? 6 );

        if ( '' === $query ) {
            return new WP_REST_Response( [ 'success' => false, 'error' => 'Query is required.' ], 400 );
        }

        $response = $this->api_client->search_products( $query, $limit, $this->get_request_context() );
        $status   = ! empty( $response['error'] ) ? 502 : 200;

        return new WP_REST_Response( $this->normalize_product_payload( $response ), $status );
    }

    public function rest_trigger_sync( WP_REST_Request $request ): WP_REST_Response {
        $stats = $this->content_sync->full_sync();

        return new WP_REST_Response( [
            'success' => true,
            'stats'   => $stats,
            'message' => __( 'Sync completed.', 'agentic-brain' ),
        ] );
    }

    public function rest_test_connection( WP_REST_Request $request ): WP_REST_Response {
        $api_url = esc_url_raw( (string) ( $request->get_param( 'api_url' ) ?? '' ) );
        $api_key = sanitize_text_field( (string) ( $request->get_param( 'api_key' ) ?? '' ) );

        $client = new Agbrain_API_Client( $api_url, $api_key );
        $result = $client->test_connection();
        $status = ! empty( $result['success'] ) ? 200 : 400;

        return new WP_REST_Response( $result, $status );
    }

    public static function call_backend( string $endpoint, array $body ): array {
        return ( new Agbrain_API_Client() )->post( $endpoint, $body );
    }

    public function settings_link( array $links ): array {
        $url  = admin_url( 'options-general.php?page=agentic-brain' );
        $link = '<a href="' . esc_url( $url ) . '">' . esc_html__( 'Settings', 'agentic-brain' ) . '</a>';
        array_unshift( $links, $link );

        return $links;
    }

    private function get_request_context(): array {
        $user_type = 'guest';

        if ( current_user_can( 'manage_options' ) ) {
            $user_type = 'admin';
        } elseif ( is_user_logged_in() ) {
            $user_type = 'customer';
        }

        $context = [
            'source'      => 'wordpress',
            'site_url'    => home_url(),
            'current_url' => home_url( add_query_arg( [] ) ),
            'user_type'   => $user_type,
            'locale'      => determine_locale(),
        ];

        if ( function_exists( 'is_product' ) && is_product() ) {
            $product = wc_get_product( get_the_ID() );
            if ( $product ) {
                $context['current_product'] = [
                    'id'    => $product->get_id(),
                    'name'  => $product->get_name(),
                    'price' => $product->get_price(),
                    'url'   => $product->get_permalink(),
                ];
            }
        }

        return $context;
    }

    private function normalize_chat_response( array $response ): array {
        if ( ! empty( $response['products'] ) && is_array( $response['products'] ) ) {
            $response['products'] = array_map( [ $this, 'prepare_product_payload' ], $response['products'] );
        }

        if ( empty( $response['reply'] ) && ! empty( $response['text'] ) ) {
            $response['reply'] = $response['text'];
        }

        if ( empty( $response['reply'] ) && empty( $response['error'] ) ) {
            $response['reply'] = __( 'I found that, but the server returned an empty response.', 'agentic-brain' );
        }

        return $response;
    }

    private function normalize_product_payload( array $response ): array {
        if ( ! empty( $response['products'] ) && is_array( $response['products'] ) ) {
            $response['products'] = array_map( [ $this, 'prepare_product_payload' ], $response['products'] );
        }

        return $response;
    }

    private function prepare_product_payload( array $product ): array {
        $product_id = isset( $product['id'] ) ? (int) $product['id'] : ( isset( $product['source_id'] ) ? (int) $product['source_id'] : 0 );

        if ( $product_id > 0 && function_exists( 'wc_get_product' ) ) {
            $wc_product = wc_get_product( $product_id );

            if ( $wc_product ) {
                $product['id']              = $wc_product->get_id();
                $product['title']           = $product['title'] ?? $wc_product->get_name();
                $product['url']             = $product['url'] ?? $wc_product->get_permalink();
                $product['permalink']       = $product['permalink'] ?? $wc_product->get_permalink();
                $product['price']           = $product['price'] ?? $wc_product->get_price();
                $product['currency']        = $product['currency'] ?? get_woocommerce_currency_symbol();
                $product['in_stock']        = isset( $product['in_stock'] ) ? (bool) $product['in_stock'] : $wc_product->is_in_stock();
                $product['add_to_cart_url'] = $product['add_to_cart_url'] ?? $wc_product->add_to_cart_url();
                $product['cart_supported']  = isset( $product['cart_supported'] )
                    ? (bool) $product['cart_supported']
                    : ( $wc_product->is_purchasable() && $wc_product->is_in_stock() && $wc_product->supports( 'ajax_add_to_cart' ) );

                if ( empty( $product['image_url'] ) && $wc_product->get_image_id() ) {
                    $product['image_url'] = wp_get_attachment_url( $wc_product->get_image_id() );
                }
            }
        }

        return $product;
    }
}
