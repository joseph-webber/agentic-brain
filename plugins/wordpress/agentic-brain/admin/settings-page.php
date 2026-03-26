<?php
/**
 * Settings → Agentic Brain admin page template.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

$api_url = (string) get_option( 'agbrain_api_url', '' );
$status  = '';

if ( $api_url ) {
    $client = new Agbrain_API_Client();
    $result = $client->test_connection();
    $status = ! empty( $result['success'] ) ? 'connected' : 'disconnected';
}
?>
<div class="wrap agbrain-settings">
    <h1>
        <span class="agbrain-logo" aria-hidden="true">🧠</span>
        <?php esc_html_e( 'Agentic Brain Settings', 'agentic-brain' ); ?>
    </h1>

    <p class="agbrain-intro">
        <?php esc_html_e( 'Install the plugin, paste your Agentic Brain API URL, save, and you are ready to go. Everything else is optional.', 'agentic-brain' ); ?>
    </p>

    <?php settings_errors(); ?>

    <?php if ( 'connected' === $status ) : ?>
        <div class="agbrain-status agbrain-status--ok" role="status" id="agbrain-connection-banner">
            <span aria-hidden="true">✅</span>
            <?php esc_html_e( 'Connected to Agentic Brain backend.', 'agentic-brain' ); ?>
        </div>
    <?php elseif ( 'disconnected' === $status ) : ?>
        <div class="agbrain-status agbrain-status--error" role="alert" id="agbrain-connection-banner">
            <span aria-hidden="true">❌</span>
            <?php esc_html_e( 'Could not reach the Agentic Brain backend. Check the URL and API key.', 'agentic-brain' ); ?>
        </div>
    <?php else : ?>
        <div class="agbrain-status agbrain-status--neutral" role="status" id="agbrain-connection-banner">
            <span aria-hidden="true">ℹ️</span>
            <?php esc_html_e( 'Add your API URL to connect this site to Agentic Brain.', 'agentic-brain' ); ?>
        </div>
    <?php endif; ?>

    <form method="post" action="options.php" id="agbrain-settings-form">
        <?php
        settings_fields( 'agentic-brain' );
        do_settings_sections( 'agentic-brain' );
        ?>

        <p class="submit agbrain-submit-row">
            <?php submit_button( __( 'Save Changes', 'agentic-brain' ), 'primary', 'submit', false ); ?>
            <button type="button" class="button button-secondary" id="agbrain-test-connection">
                <?php esc_html_e( 'Test Connection', 'agentic-brain' ); ?>
            </button>
            <span id="agbrain-connection-status" role="status" aria-live="polite"></span>
        </p>
    </form>

    <hr />

    <h2><?php esc_html_e( 'Sync Status', 'agentic-brain' ); ?></h2>
    <p class="description">
        <?php esc_html_e( 'Products sync automatically when they change. You can also run a full sync at any time.', 'agentic-brain' ); ?>
    </p>

    <div class="agbrain-sync-panel" aria-live="polite">
        <p>
            <strong><?php esc_html_e( 'Last full sync:', 'agentic-brain' ); ?></strong>
            <span id="agbrain-last-sync-value"><?php echo esc_html( (string) get_option( 'agbrain_last_sync', __( 'Never', 'agentic-brain' ) ) ); ?></span>
        </p>
        <p>
            <strong><?php esc_html_e( 'Last product sync:', 'agentic-brain' ); ?></strong>
            <span id="agbrain-last-product-sync-value"><?php echo esc_html( (string) get_option( 'agbrain_last_product_sync', __( 'Never', 'agentic-brain' ) ) ); ?></span>
        </p>
        <button type="button"
                id="agbrain-sync-now"
                class="button button-secondary"
                aria-label="<?php esc_attr_e( 'Sync all products, posts and pages to Agentic Brain now', 'agentic-brain' ); ?>">
            <?php esc_html_e( 'Run Full Sync Now', 'agentic-brain' ); ?>
        </button>
        <span id="agbrain-sync-status" role="status" aria-live="polite"></span>
    </div>

    <hr />

    <h2><?php esc_html_e( 'Shortcodes', 'agentic-brain' ); ?></h2>
    <table class="widefat agbrain-shortcodes" role="table">
        <thead>
            <tr>
                <th scope="col"><?php esc_html_e( 'Shortcode', 'agentic-brain' ); ?></th>
                <th scope="col"><?php esc_html_e( 'Description', 'agentic-brain' ); ?></th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><code>[agentic_chat]</code></td>
                <td><?php esc_html_e( 'Embed the AI chat widget inline on any page or post.', 'agentic-brain' ); ?></td>
            </tr>
            <tr>
                <td><code>[agentic_product_search]</code></td>
                <td><?php esc_html_e( 'Embed an AI-powered product search bar.', 'agentic-brain' ); ?></td>
            </tr>
        </tbody>
    </table>
</div>
