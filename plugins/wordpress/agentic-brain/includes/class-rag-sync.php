<?php
/**
 * Content sync for posts/pages, plus orchestrated full sync.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class Agbrain_RAG_Sync {

    private const BATCH_SIZE = 50;

    private Agbrain_API_Client $client;
    private Agbrain_Product_Sync $product_sync;

    public function __construct( ?Agbrain_API_Client $client = null, ?Agbrain_Product_Sync $product_sync = null ) {
        $this->client       = $client ?: new Agbrain_API_Client();
        $this->product_sync = $product_sync ?: new Agbrain_Product_Sync( $this->client );
    }

    public function init(): void {
        add_action( 'agbrain_daily_sync', [ $this, 'full_sync' ] );

        if ( 'yes' === get_option( 'agbrain_sync_posts', 'yes' ) ) {
            add_action( 'save_post', [ $this, 'sync_single_post' ], 20, 2 );
            add_action( 'before_delete_post', [ $this, 'delete_document' ] );
        }
    }

    public function full_sync(): array {
        $stats = [
            'products' => 0,
            'posts'    => 0,
            'errors'   => 0,
        ];

        $product_stats      = $this->product_sync->full_sync();
        $stats['products'] += (int) ( $product_stats['products'] ?? 0 );
        $stats['errors']   += (int) ( $product_stats['errors'] ?? 0 );

        if ( 'yes' === get_option( 'agbrain_sync_posts', 'yes' ) ) {
            $page = 1;

            do {
                $query = new WP_Query( [
                    'post_type'      => [ 'post', 'page' ],
                    'post_status'    => 'publish',
                    'posts_per_page' => self::BATCH_SIZE,
                    'paged'          => $page,
                    'fields'         => 'ids',
                ] );

                if ( empty( $query->posts ) ) {
                    break;
                }

                $batch = [];
                foreach ( $query->posts as $post_id ) {
                    $post = get_post( $post_id );
                    if ( $post instanceof WP_Post ) {
                        $batch[] = $this->post_to_document( $post );
                    }
                }

                $result = $this->push_batch( $batch, 'content', 'full' );
                if ( ! empty( $result['error'] ) ) {
                    $stats['errors']++;
                } else {
                    $stats['posts'] += count( $batch );
                }

                $page++;
            } while ( $page <= (int) $query->max_num_pages );

            wp_reset_postdata();
        }

        update_option( 'agbrain_last_sync', current_time( 'mysql' ) );

        return $stats;
    }

    public function sync_single_post( int $post_id, WP_Post $post ): void {
        if ( wp_is_post_revision( $post_id ) || wp_is_post_autosave( $post_id ) ) {
            return;
        }

        if ( ! in_array( $post->post_type, [ 'post', 'page' ], true ) ) {
            return;
        }

        if ( 'publish' !== $post->post_status ) {
            $this->delete_document( $post_id );
            return;
        }

        $result = $this->push_batch( [ $this->post_to_document( $post ) ], 'content', 'incremental' );
        if ( empty( $result['error'] ) ) {
            update_option( 'agbrain_last_sync', current_time( 'mysql' ) );
        }
    }

    public function delete_document( int $post_id ): void {
        $post_type = get_post_type( $post_id );

        if ( 'product' === $post_type ) {
            return;
        }

        if ( ! in_array( $post_type, [ 'post', 'page' ], true ) ) {
            return;
        }

        $this->client->delete_document( (string) $post_id, [
            'content_type' => $post_type,
        ] );
    }

    private function post_to_document( WP_Post $post ): array {
        $categories = wp_get_post_terms( $post->ID, 'category', [ 'fields' => 'names' ] );
        $tags       = wp_get_post_terms( $post->ID, 'post_tag', [ 'fields' => 'names' ] );
        $thumb      = get_post_thumbnail_id( $post->ID );

        return [
            'source_id'  => (string) $post->ID,
            'type'       => $post->post_type,
            'title'      => $post->post_title,
            'content'    => wp_strip_all_tags( $post->post_content ),
            'excerpt'    => wp_strip_all_tags( $post->post_excerpt ),
            'url'        => get_permalink( $post->ID ),
            'image_url'  => $thumb ? wp_get_attachment_url( $thumb ) : '',
            'categories' => is_array( $categories ) ? $categories : [],
            'tags'       => is_array( $tags ) ? $tags : [],
            'author'     => get_the_author_meta( 'display_name', $post->post_author ),
            'updated_at' => get_post_modified_time( 'c', false, $post->ID ),
        ];
    }

    private function push_batch( array $documents, string $type, string $mode ): array {
        if ( empty( $documents ) ) {
            return [ 'success' => true ];
        }

        return $this->client->ingest_documents( $documents, $type, [
            'sync_mode' => $mode,
        ] );
    }
}
