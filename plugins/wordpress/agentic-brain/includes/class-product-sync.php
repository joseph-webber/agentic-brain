<?php
/**
 * Product sync for WooCommerce → Agentic Brain.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class Agbrain_Product_Sync {

    private const BATCH_SIZE = 50;

    private Agbrain_API_Client $client;
    private array $synced_products = [];

    public function __construct( ?Agbrain_API_Client $client = null ) {
        $this->client = $client ?: new Agbrain_API_Client();
    }

    public function init(): void {
        if ( ! function_exists( 'wc_get_product' ) ) {
            return;
        }

        add_action( 'save_post_product', [ $this, 'handle_product_save' ], 20, 3 );
        add_action( 'woocommerce_update_product', [ $this, 'sync_single_product' ] );
        add_action( 'woocommerce_new_product', [ $this, 'sync_single_product' ] );
        add_action( 'before_delete_post', [ $this, 'handle_delete' ] );
    }

    public function full_sync(): array {
        $stats = [
            'products' => 0,
            'errors'   => 0,
        ];

        if ( ! function_exists( 'wc_get_products' ) ) {
            return $stats;
        }

        $page = 1;

        do {
            $products = wc_get_products( [
                'status' => [ 'publish' ],
                'limit'  => self::BATCH_SIZE,
                'page'   => $page,
                'return' => 'objects',
            ] );

            if ( empty( $products ) ) {
                break;
            }

            $documents = array_values( array_filter( array_map( [ $this, 'product_to_document' ], $products ) ) );
            $result    = $this->push_documents( $documents, 'full' );

            if ( ! empty( $result['error'] ) ) {
                $stats['errors']++;
            } else {
                $stats['products'] += count( $documents );
            }

            $page++;
        } while ( count( $products ) === self::BATCH_SIZE );

        update_option( 'agbrain_last_product_sync', current_time( 'mysql' ) );

        return $stats;
    }

    public function handle_product_save( int $post_id, WP_Post $post, bool $update ): void {
        if ( 'yes' !== get_option( 'agbrain_woo_auto_sync', 'yes' ) ) {
            return;
        }

        if ( wp_is_post_revision( $post_id ) || wp_is_post_autosave( $post_id ) ) {
            return;
        }

        if ( 'product' !== $post->post_type ) {
            return;
        }

        if ( 'publish' !== $post->post_status ) {
            $this->delete_product( $post_id, 'unpublished' );
            return;
        }

        $this->sync_single_product( $post_id, $update ? 'update' : 'create' );
    }

    public function sync_single_product( int $product_id, string $reason = 'update' ): array {
        if ( isset( $this->synced_products[ $product_id ] ) ) {
            return [ 'success' => true, 'message' => 'Already synced in this request.' ];
        }

        if ( 'yes' !== get_option( 'agbrain_woo_auto_sync', 'yes' ) ) {
            return [ 'success' => false, 'message' => 'Auto sync disabled.' ];
        }

        $product = wc_get_product( $product_id );

        if ( ! $product || 'publish' !== $product->get_status() ) {
            return [ 'success' => false, 'message' => 'Product not publishable.' ];
        }

        $document = $this->product_to_document( $product );
        $result   = $this->push_documents( [ $document ], $reason );

        if ( empty( $result['error'] ) ) {
            $this->synced_products[ $product_id ] = true;
            update_option( 'agbrain_last_product_sync', current_time( 'mysql' ) );
            update_post_meta( $product_id, '_agbrain_last_synced', current_time( 'mysql' ) );
        }

        return $result;
    }

    public function handle_delete( int $post_id ): void {
        if ( 'product' !== get_post_type( $post_id ) ) {
            return;
        }

        $this->delete_product( $post_id, 'delete' );
    }

    public function delete_product( int $product_id, string $reason = 'delete' ): array {
        return $this->client->delete_document( (string) $product_id, [
            'content_type' => 'product',
            'reason'       => $reason,
        ] );
    }

    private function push_documents( array $documents, string $mode ): array {
        if ( empty( $documents ) ) {
            return [ 'success' => true ];
        }

        return $this->client->ingest_documents( $documents, 'product', [
            'sync_mode' => $mode,
        ] );
    }

    private function product_to_document( WC_Product $product ): array {
        $categories = wp_get_post_terms( $product->get_id(), 'product_cat', [ 'fields' => 'names' ] );
        $tags       = wp_get_post_terms( $product->get_id(), 'product_tag', [ 'fields' => 'names' ] );
        $image_id   = $product->get_image_id();
        $permalink  = $product->get_permalink();
        $add_to_cart_url = $product->add_to_cart_url();

        return [
            'source_id'       => (string) $product->get_id(),
            'type'            => 'product',
            'title'           => $product->get_name(),
            'content'         => wp_strip_all_tags( $product->get_description() ),
            'short_desc'      => wp_strip_all_tags( $product->get_short_description() ),
            'url'             => $permalink,
            'permalink'       => $permalink,
            'image_url'       => $image_id ? wp_get_attachment_url( $image_id ) : '',
            'price'           => $product->get_price(),
            'regular_price'   => $product->get_regular_price(),
            'sale_price'      => $product->get_sale_price(),
            'currency'        => function_exists( 'get_woocommerce_currency_symbol' ) ? get_woocommerce_currency_symbol() : '$',
            'in_stock'        => $product->is_in_stock(),
            'stock_status'    => $product->get_stock_status(),
            'sku'             => $product->get_sku(),
            'categories'      => is_array( $categories ) ? $categories : [],
            'tags'            => is_array( $tags ) ? $tags : [],
            'attributes'      => $this->flatten_attributes( $product ),
            'updated_at'      => $product->get_date_modified() ? $product->get_date_modified()->format( 'c' ) : current_time( 'c' ),
            'add_to_cart_url' => $add_to_cart_url,
            'cart_supported'  => $product->is_purchasable() && $product->is_in_stock() && $product->supports( 'ajax_add_to_cart' ),
        ];
    }

    private function flatten_attributes( WC_Product $product ): array {
        $out = [];

        foreach ( $product->get_attributes() as $attribute ) {
            if ( ! is_a( $attribute, 'WC_Product_Attribute' ) ) {
                continue;
            }

            $label = wc_attribute_label( $attribute->get_name() );
            $value = [];

            if ( $attribute->is_taxonomy() ) {
                $terms = wc_get_product_terms( $product->get_id(), $attribute->get_name(), [ 'fields' => 'names' ] );
                $value = is_array( $terms ) ? $terms : [];
            } else {
                $value = $attribute->get_options();
            }

            $out[ $label ] = implode( ', ', array_map( 'strval', $value ) );
        }

        return $out;
    }
}
