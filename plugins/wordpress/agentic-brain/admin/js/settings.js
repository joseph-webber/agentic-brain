(function () {
    'use strict';

    var config = window.agbrainAdmin || {};
    var restUrl = config.restUrl || '';
    var nonce = config.nonce || '';
    var i18n = config.i18n || {};

    function ready(fn) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', fn);
        } else {
            fn();
        }
    }

    ready(function () {
        var apiUrlInput = document.getElementById('agbrain_api_url');
        var apiKeyInput = document.getElementById('agbrain_api_key');
        var testBtn = document.getElementById('agbrain-test-connection');
        var syncBtn = document.getElementById('agbrain-sync-now');
        var connectionStatus = document.getElementById('agbrain-connection-status');
        var syncStatus = document.getElementById('agbrain-sync-status');
        var lastSync = document.getElementById('agbrain-last-sync-value');
        var lastProductSync = document.getElementById('agbrain-last-product-sync-value');
        var banner = document.getElementById('agbrain-connection-banner');

        if (apiUrlInput) {
            validateUrl(apiUrlInput, connectionStatus);
            apiUrlInput.addEventListener('input', function () {
                validateUrl(apiUrlInput, connectionStatus);
            });
        }

        if (apiKeyInput) {
            apiKeyInput.addEventListener('input', function () {
                if (connectionStatus && !apiKeyInput.value.trim()) {
                    connectionStatus.textContent = '';
                }
            });
        }

        if (testBtn) {
            testBtn.addEventListener('click', function () {
                if (!apiUrlInput || !isValidUrl(apiUrlInput.value)) {
                    if (connectionStatus) {
                        connectionStatus.textContent = i18n.invalidUrl || 'Enter a valid URL.';
                    }
                    apiUrlInput.focus();
                    return;
                }

                testBtn.disabled = true;
                setStatus(connectionStatus, i18n.testing || 'Testing connection…');

                fetch(restUrl + '/connection-test', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-WP-Nonce': nonce
                    },
                    body: JSON.stringify({
                        api_url: apiUrlInput.value.trim(),
                        api_key: apiKeyInput ? apiKeyInput.value.trim() : ''
                    })
                })
                    .then(function (response) { return response.json(); })
                    .then(function (data) {
                        var success = !!data.success;
                        setStatus(connectionStatus, data.message || (success ? i18n.connected : i18n.connectFailed));
                        updateBanner(banner, success, data.message || '');
                    })
                    .catch(function () {
                        setStatus(connectionStatus, i18n.networkError || 'Network error. Please try again.');
                        updateBanner(banner, false, i18n.networkError || 'Network error. Please try again.');
                    })
                    .finally(function () {
                        testBtn.disabled = false;
                    });
            });
        }

        if (syncBtn) {
            syncBtn.addEventListener('click', function () {
                syncBtn.disabled = true;
                setStatus(syncStatus, i18n.syncing || 'Syncing…');

                fetch(restUrl + '/sync', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-WP-Nonce': nonce
                    }
                })
                    .then(function (response) { return response.json(); })
                    .then(function (data) {
                        if (!data.success) {
                            throw new Error(data.error || i18n.connectFailed || 'Sync failed.');
                        }

                        var stats = data.stats || {};
                        var now = new Date().toLocaleString();
                        if (lastSync) {
                            lastSync.textContent = now;
                        }
                        if (lastProductSync && typeof stats.products !== 'undefined') {
                            lastProductSync.textContent = now;
                        }

                        setStatus(syncStatus, '✅ ' + (stats.products || 0) + ' products, ' + (stats.posts || 0) + ' posts/pages synced.');
                    })
                    .catch(function (error) {
                        setStatus(syncStatus, '❌ ' + (error.message || i18n.networkError || 'Network error. Please try again.'));
                    })
                    .finally(function () {
                        syncBtn.disabled = false;
                    });
            });
        }
    });

    function validateUrl(input, output) {
        if (!input || !output) {
            return;
        }

        if (!input.value.trim()) {
            output.textContent = '';
            return;
        }

        output.textContent = isValidUrl(input.value)
            ? (i18n.urlLooksGood || 'URL format looks good.')
            : (i18n.invalidUrl || 'Enter a valid URL that starts with http:// or https://');
    }

    function isValidUrl(value) {
        try {
            var url = new URL(value);
            return url.protocol === 'http:' || url.protocol === 'https:';
        } catch (error) {
            return false;
        }
    }

    function setStatus(element, message) {
        if (element) {
            element.textContent = message || '';
        }
    }

    function updateBanner(banner, success, message) {
        if (!banner) {
            return;
        }

        banner.classList.remove('agbrain-status--ok', 'agbrain-status--error', 'agbrain-status--neutral');
        banner.classList.add(success ? 'agbrain-status--ok' : 'agbrain-status--error');
        banner.textContent = '';
        var icon = document.createElement('span');
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = success ? '✅' : '❌';
        banner.appendChild(icon);
        banner.appendChild(document.createTextNode(message || ''));
    }
})();
