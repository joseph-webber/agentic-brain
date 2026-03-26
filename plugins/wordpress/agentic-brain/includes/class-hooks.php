<?php
/**
 * WooCommerce and customer hooks for Agentic Brain.
 *
 * These hooks send real-time events to the Agentic Brain backend for
 * orders and customer registrations. Product and content sync is
 * handled by Agbrain_RAG_Sync.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class Agentic_Brain_Hooks {

    /**
     * Register action hooks.
     */
    public function init(): void {
        // Order status changes.
        add_action(
            'woocommerce_order_status_changed',
            [ $this, 'handle_order_status_change' ],
            10,
            4
        );

        // New customer registration (works for WooCommerce customers too).
        add_action(
            'user_register',
            [ $this, 'handle_user_register' ],
            10,
            1
        );
    }

    /**
     * Handle WooCommerce order status changes.
     *
     * @param int      $order_id   Order ID.
     * @param string   $old_status Old status slug.
     * @param string   $new_status New status slug.
     * @param WC_Order $order      Order object.
     */
    public function handle_order_status_change( int $order_id, string $old_status, string $new_status, $order = null ): void {
        if ( ! function_exists( 'wc_get_order' ) ) {
            return;
        }

        if ( ! $order instanceof WC_Order ) {
            $order = wc_get_order( $order_id );
        }

        if ( ! $order ) {
            return;
        }

        Agentic_Brain::call_backend(
            '/api/events/order-status',
            [
                'order_id'   => (string) $order->get_id(),
                'status'     => $new_status,
                'old_status' => $old_status,
                'total'      => $order->get_total(),
                'currency'   => $order->get_currency(),
                'site_url'   => home_url(),
            ]
        );
    }

    /**
     * Handle new user registration.
     *
     * When WooCommerce is active this typically corresponds to a new
     * customer account.
     *
     * @param int $user_id User ID.
     */
    public function handle_user_register( int $user_id ): void {
        $user = get_userdata( $user_id );
        if ( ! $user ) {
            return;
        }

        Agentic_Brain::call_backend(
            '/api/events/customer-registered',
            [
                'user_id'  => (string) $user_id,
                'email'    => $user->user_email,
                'name'     => $user->display_name,
                'site_url' => home_url(),
            ]
        );
    }
}
