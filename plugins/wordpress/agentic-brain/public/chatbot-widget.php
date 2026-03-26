<?php
/**
 * Chatbot floating widget markup.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

$position   = get_option( 'agbrain_widget_position', 'bottom-right' );
$instance   = wp_unique_id( 'agbrain-chat-' );
$storage_key = 'agbrain-' . $position;
$window_id  = $instance . '-window';
$input_id   = $instance . '-input';
$title_id   = $instance . '-title';
$user_type  = 'guest';
$user_label = __( 'Guest visitor', 'agentic-brain' );

if ( current_user_can( 'manage_options' ) ) {
    $user_type  = 'admin';
    $user_label = __( 'Store admin', 'agentic-brain' );
} elseif ( is_user_logged_in() ) {
    $user_type  = 'customer';
    $user_label = __( 'Customer', 'agentic-brain' );
}
?>
<div class="agbrain-chat agbrain-chat--<?php echo esc_attr( $position ); ?>"
     data-agbrain-widget
     data-instance-id="<?php echo esc_attr( $instance ); ?>"
     data-storage-key="<?php echo esc_attr( $storage_key ); ?>"
     data-user-type="<?php echo esc_attr( $user_type ); ?>"
     aria-label="<?php esc_attr_e( 'AI Chat Assistant', 'agentic-brain' ); ?>"
     role="complementary">

    <button class="agbrain-toggle"
            type="button"
            aria-label="<?php esc_attr_e( 'Open chat assistant', 'agentic-brain' ); ?>"
            aria-expanded="false"
            aria-controls="<?php echo esc_attr( $window_id ); ?>">
        <svg class="agbrain-icon-chat" aria-hidden="true" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <svg class="agbrain-icon-close" aria-hidden="true" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
    </button>

    <div id="<?php echo esc_attr( $window_id ); ?>"
         class="agbrain-window"
         role="dialog"
         aria-labelledby="<?php echo esc_attr( $title_id ); ?>"
         aria-hidden="true">
        <div class="agbrain-header">
            <div class="agbrain-header__content">
                <span class="agbrain-header__title" id="<?php echo esc_attr( $title_id ); ?>">
                    <?php esc_html_e( 'Agentic Brain', 'agentic-brain' ); ?>
                </span>
                <span class="agbrain-header__subtitle"><?php echo esc_html( $user_label ); ?></span>
            </div>
            <button class="agbrain-header__close"
                    aria-label="<?php esc_attr_e( 'Close chat', 'agentic-brain' ); ?>"
                    type="button">
                &times;
            </button>
        </div>

        <div class="agbrain-messages"
             role="log"
             aria-live="polite"
             aria-label="<?php esc_attr_e( 'Chat messages', 'agentic-brain' ); ?>">
        </div>

        <div class="agbrain-statusline" aria-live="polite"></div>

        <form class="agbrain-input" autocomplete="off">
            <label for="<?php echo esc_attr( $input_id ); ?>" class="screen-reader-text">
                <?php esc_html_e( 'Type a message', 'agentic-brain' ); ?>
            </label>
            <input id="<?php echo esc_attr( $input_id ); ?>"
                   class="agbrain-input__field"
                   type="text"
                   placeholder="<?php esc_attr_e( 'Type a message…', 'agentic-brain' ); ?>"
                   aria-label="<?php esc_attr_e( 'Type a message', 'agentic-brain' ); ?>" />
            <button class="agbrain-input__send"
                    type="submit"
                    aria-label="<?php esc_attr_e( 'Send message', 'agentic-brain' ); ?>">
                <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13"/>
                    <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                </svg>
            </button>
        </form>

        <div class="agbrain-footer">
            <?php esc_html_e( 'Powered by Agentic Brain', 'agentic-brain' ); ?>
        </div>
    </div>
</div>
