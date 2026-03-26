<?php
/**
 * REST API layer for Agentic Brain.
 *
 * Routes registered by this class:
 * - GET  /wp-json/agentic-brain/v1/status
 *
 * Additional routes (/chat, /search, /sync, /connection-test) are
 * registered by the main Agentic_Brain class.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class Agentic_Brain_REST_API {

    public function __construct() {
        add_action( 'rest_api_init', [ $this, 'register_routes' ] );
    }

    /**
     * Register REST API routes.
     */
    public function register_routes(): void {
        register_rest_route(
            'agentic-brain/v1',
            '/status',
            [
                'methods'             => WP_REST_Server::READABLE,
                'callback'            => [ $this, 'handle_status' ],
                'permission_callback' => '__return_true',
            ]
        );
    }

    /**
     * Proxy chat messages to the Agentic Brain backend.
     */
    public function handle_chat( WP_REST_Request $request ): WP_REST_Response {
        $message    = sanitize_text_field( $request->get_param( 'message' ) ?? '' );
        $session_id = sanitize_text_field( $request->get_param( 'session_id' ) ?? '' );

        if ( '' === $message ) {
            return new WP_REST_Response(
                [ 'error' => __( 'Message is required.', 'agentic-brain' ) ],
                400
            );
        }

        $response = Agentic_Brain::call_backend(
            '/api/chat',
            [
                'message'    => $message,
                'session_id' => $session_id,
                'context'    => [
                    'source' => 'wordpress',
                    'url'    => home_url(),
                ],
            ]
        );

        $status = ( isset( $response['error'] ) && $response['error'] ) ? 502 : 200;

        return new WP_REST_Response( $response, $status );
    }

    /**
     * Proxy product search queries to the backend.
     */
    public function handle_search( WP_REST_Request $request ): WP_REST_Response {
        $query = sanitize_text_field( $request->get_param( 'query' ) ?? '' );
        $limit = (int) ( $request->get_param( 'limit' ) ?? 6 );

        if ( '' === $query ) {
            return new WP_REST_Response(
                [ 'error' => __( 'Query is required.', 'agentic-brain' ) ],
                400
            );
        }

        $response = Agentic_Brain::call_backend(
            '/api/search',
            [
                'query' => $query,
                'limit' => $limit,
                'type'  => 'product',
            ]
        );

        $status = ( isset( $response['error'] ) && $response['error'] ) ? 502 : 200;

        return new WP_REST_Response( $response, $status );
    }

    /**
     * Lightweight plugin status endpoint for the widget to query.
     */
    public function handle_status( WP_REST_Request $request ): WP_REST_Response { // phpcs:ignore VariableAnalysis.CodeAnalysis.UnusedFunctionParameter
        $api_url   = get_option( 'agbrain_api_url', '' );
        $has_wc    = function_exists( 'agbrain_has_woocommerce' ) ? agbrain_has_woocommerce() : class_exists( 'WooCommerce' );
        $last_sync = get_option( 'agbrain_last_sync', '' );

        $data = [
            'version'         => AGBRAIN_VERSION,
            'api_configured'  => '' !== $api_url,
            'has_woocommerce' => (bool) $has_wc,
            'site_url'        => home_url(),
            'last_sync'       => $last_sync,
        ];

        return new WP_REST_Response( $data, 200 );
    }

    /**
     * Trigger a full content sync.
     */
    public function handle_sync( WP_REST_Request $request ): WP_REST_Response { // phpcs:ignore VariableAnalysis.CodeAnalysis.UnusedFunctionParameter
        $sync  = new Agbrain_RAG_Sync();
        $stats = $sync->full_sync();

        return new WP_REST_Response(
            [
                'success' => true,
                'stats'   => $stats,
            ]
        );
    }
}
