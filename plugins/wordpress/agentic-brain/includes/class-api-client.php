<?php
/**
 * API client for communicating with the Agentic Brain backend.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class Agbrain_API_Client {

    private string $api_url;
    private string $api_key;

    public function __construct( string $api_url = '', string $api_key = '' ) {
        $saved_api_url = (string) get_option( 'agbrain_api_url', '' );
        $saved_api_key = (string) get_option( 'agbrain_api_key', '' );

        $this->api_url = rtrim( '' !== $api_url ? $api_url : $saved_api_url, '/' );
        $this->api_key = '' !== $api_key ? $api_key : $saved_api_key;
    }

    public function is_configured(): bool {
        return '' !== $this->api_url;
    }

    public function get_base_url(): string {
        return $this->api_url;
    }

    public function test_connection(): array {
        if ( ! $this->is_configured() ) {
            return [
                'success' => false,
                'message' => __( 'Enter your Agentic Brain API URL first.', 'agentic-brain' ),
            ];
        }

        $health_endpoints = [
            '/api/health',
            '/health',
            '/api/status',
        ];

        foreach ( $health_endpoints as $endpoint ) {
            $response = wp_remote_get( $this->api_url . $endpoint, [
                'timeout' => 10,
                'headers' => $this->build_headers(),
            ] );

            if ( is_wp_error( $response ) ) {
                continue;
            }

            $code = (int) wp_remote_retrieve_response_code( $response );
            $body = json_decode( wp_remote_retrieve_body( $response ), true );

            if ( $code >= 200 && $code < 300 ) {
                return [
                    'success'  => true,
                    'message'  => isset( $body['message'] ) && is_string( $body['message'] )
                        ? $body['message']
                        : __( 'Connection successful.', 'agentic-brain' ),
                    'endpoint' => $endpoint,
                    'data'     => is_array( $body ) ? $body : [],
                ];
            }
        }

        return [
            'success' => false,
            'message' => __( 'Could not connect to the Agentic Brain server. Check the URL and try again.', 'agentic-brain' ),
        ];
    }

    public function send_chat_message( string $message, string $session_id, array $context = [] ): array {
        return $this->post( '/api/chat', [
            'message'    => $message,
            'session_id' => $session_id,
            'context'    => $context,
        ] );
    }

    public function search_products( string $query, int $limit = 6, array $context = [] ): array {
        return $this->post( '/api/search', [
            'query'   => $query,
            'limit'   => max( 1, $limit ),
            'type'    => 'product',
            'context' => $context,
        ] );
    }

    public function ingest_documents( array $documents, string $type = 'content', array $meta = [] ): array {
        return $this->post( '/api/documents/ingest', [
            'source'    => 'wordpress',
            'site_url'  => home_url(),
            'type'      => $type,
            'documents' => array_values( $documents ),
            'meta'      => $meta,
        ] );
    }

    public function delete_document( string $source_id, array $meta = [] ): array {
        return $this->post( '/api/documents/delete', [
            'source'    => 'wordpress',
            'source_id' => $source_id,
            'site_url'  => home_url(),
            'meta'      => $meta,
        ] );
    }

    public function post( string $endpoint, array $body = [] ): array {
        return $this->request( 'POST', $endpoint, $body );
    }

    public function get( string $endpoint, array $query_args = [] ): array {
        if ( ! empty( $query_args ) ) {
            $endpoint = add_query_arg( $query_args, $endpoint );
        }

        return $this->request( 'GET', $endpoint );
    }

    public function request( string $method, string $endpoint, array $body = [] ): array {
        if ( ! $this->is_configured() ) {
            return $this->error_response( __( 'Agentic Brain API URL is not configured yet.', 'agentic-brain' ) );
        }

        $url      = $this->api_url . '/' . ltrim( $endpoint, '/' );
        $response = wp_remote_request( $url, [
            'method'  => strtoupper( $method ),
            'timeout' => 30,
            'headers' => $this->build_headers(),
            'body'    => 'GET' === strtoupper( $method ) ? null : wp_json_encode( $body ),
        ] );

        if ( is_wp_error( $response ) ) {
            return $this->error_response( $response->get_error_message() );
        }

        $code      = (int) wp_remote_retrieve_response_code( $response );
        $raw_body  = wp_remote_retrieve_body( $response );
        $decoded   = json_decode( $raw_body, true );
        $payload   = is_array( $decoded ) ? $decoded : [ 'raw' => $raw_body ];
        $successful = $code >= 200 && $code < 300;

        if ( ! $successful ) {
            $message = isset( $payload['message'] ) && is_string( $payload['message'] )
                ? $payload['message']
                : ( isset( $payload['error'] ) && is_string( $payload['error'] )
                    ? $payload['error']
                    : sprintf( __( 'Request failed with status %d.', 'agentic-brain' ), $code ) );

            $payload['success'] = false;
            $payload['error']   = $message;
            $payload['status']  = $code;

            return $payload;
        }

        if ( ! isset( $payload['success'] ) ) {
            $payload['success'] = true;
        }

        $payload['status'] = $code;

        return $payload;
    }

    private function build_headers(): array {
        $headers = [
            'Accept'       => 'application/json',
            'Content-Type' => 'application/json',
            'X-Source'     => 'wordpress-plugin',
            'X-Site-Url'   => home_url(),
        ];

        if ( '' !== $this->api_key ) {
            $headers['Authorization'] = 'Bearer ' . $this->api_key;
        }

        return $headers;
    }

    private function error_response( string $message ): array {
        return [
            'success' => false,
            'error'   => $message,
            'message' => $message,
        ];
    }
}
