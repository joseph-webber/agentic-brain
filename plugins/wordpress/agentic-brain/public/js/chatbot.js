(function () {
    'use strict';

    var config = window.agbrainChat || {};
    var REST_URL = config.restUrl || '/wp-json/agentic-brain/v1';
    var NONCE = config.nonce || '';
    var WELCOME_MESSAGE = config.welcomeMessage || 'Hi! How can I help you today?';
    var I18N = config.i18n || {};
    var STORAGE_KEY = 'agbrain-chat-state';

    function init() {
        var widgets = document.querySelectorAll('[data-agbrain-widget]');
        widgets.forEach(function (widget) {
            if (!widget.__agbrainReady) {
                widget.__agbrainReady = true;
                createWidgetController(widget);
            }
        });

        initProductSearch();
    }

    function createWidgetController(widget) {
        var toggle = widget.querySelector('.agbrain-toggle');
        var win = widget.querySelector('.agbrain-window');
        var messages = widget.querySelector('.agbrain-messages');
        var form = widget.querySelector('.agbrain-input');
        var input = widget.querySelector('.agbrain-input__field');
        var closeBtn = widget.querySelector('.agbrain-header__close');
        var statusline = widget.querySelector('.agbrain-statusline');
        var instanceId = widget.getAttribute('data-instance-id') || String(Date.now());
        var storageKey = widget.getAttribute('data-storage-key') || ('agbrain-' + (config.siteUrl || window.location.origin) + '-' + (widget.getAttribute('data-user-type') || config.userType || 'guest'));
        var state = loadState(storageKey, widget.getAttribute('data-user-type') || config.userType || 'guest');
        state.instanceId = storageKey;
        var isOpen = false;
        var isSending = false;

        if (!toggle || !win || !messages || !form || !input) {
            return;
        }

        restoreMessages(messages, state.history);

        toggle.addEventListener('click', function () {
            if (isOpen) {
                closeChat();
            } else {
                openChat();
            }
        });

        if (closeBtn) {
            closeBtn.addEventListener('click', closeChat);
        }

        widget.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && isOpen) {
                closeChat();
            }
        });

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            var text = input.value.trim();
            if (!text || isSending) {
                return;
            }

            isSending = true;
            appendMessage(messages, 'user', text);
            saveHistory(state, { role: 'user', text: text });
            input.value = '';
            setStatus(statusline, I18N.thinking || 'Thinking…');
            var thinking = appendThinking(messages);

            fetch(REST_URL + '/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-WP-Nonce': NONCE
                },
                body: JSON.stringify({
                    message: text,
                    session_id: state.sessionId,
                    context: {
                        user_type: state.userType,
                        page_title: document.title,
                        page_url: window.location.href
                    }
                })
            })
                .then(parseJson)
                .then(function (data) {
                    thinking.remove();
                    if (data.error) {
                        appendMessage(messages, 'bot', I18N.error || 'Something went wrong. Please try again.');
                        saveHistory(state, { role: 'bot', text: I18N.error || 'Something went wrong. Please try again.' });
                        setStatus(statusline, data.error);
                        return;
                    }

                    var payload = normalizeChatPayload(data);
                    appendMessage(messages, 'bot', payload);
                    saveHistory(state, { role: 'bot', text: payload.text || '', products: payload.products || [] });
                    setStatus(statusline, '');
                })
                .catch(function () {
                    thinking.remove();
                    appendMessage(messages, 'bot', I18N.error || 'Something went wrong. Please try again.');
                    saveHistory(state, { role: 'bot', text: I18N.error || 'Something went wrong. Please try again.' });
                    setStatus(statusline, I18N.error || 'Something went wrong. Please try again.');
                })
                .finally(function () {
                    isSending = false;
                    input.focus();
                });
        });

        function openChat() {
            isOpen = true;
            widget.classList.add('agbrain-chat--open');
            win.setAttribute('aria-hidden', 'false');
            toggle.setAttribute('aria-expanded', 'true');
            toggle.setAttribute('aria-label', I18N.close || 'Close chat');
            if (!state.history.length && WELCOME_MESSAGE) {
                var welcome = { text: WELCOME_MESSAGE, products: [] };
                appendMessage(messages, 'bot', welcome);
                saveHistory(state, { role: 'bot', text: WELCOME_MESSAGE, products: [] });
            }
            window.setTimeout(function () {
                input.focus();
            }, 50);
        }

        function closeChat() {
            isOpen = false;
            widget.classList.remove('agbrain-chat--open');
            win.setAttribute('aria-hidden', 'true');
            toggle.setAttribute('aria-expanded', 'false');
            toggle.setAttribute('aria-label', I18N.open || 'Open chat assistant');
            toggle.focus();
        }
    }

    function loadState(instanceId, userType) {
        var store = readStore();
        if (!store[instanceId]) {
            store[instanceId] = {
                instanceId: instanceId,
                sessionId: 'wp_' + Math.random().toString(36).slice(2, 12),
                history: [],
                userType: userType
            };
            writeStore(store);
        }
        return store[instanceId];
    }

    function readStore() {
        try {
            return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '{}');
        } catch (error) {
            return {};
        }
    }

    function writeStore(store) {
        try {
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
        } catch (error) {
            return;
        }
    }

    function saveHistory(state, message) {
        var store = readStore();
        state.history.push(message);
        state.history = state.history.slice(-30);
        store[state.instanceId] = state;
        writeStore(store);
    }

    function restoreMessages(messages, history) {
        if (!Array.isArray(history)) {
            return;
        }

        history.forEach(function (message) {
            if (message.role === 'bot') {
                appendMessage(messages, 'bot', {
                    text: message.text || '',
                    products: Array.isArray(message.products) ? message.products : []
                });
            } else {
                appendMessage(messages, 'user', message.text || '');
            }
        });
    }

    function appendMessage(container, role, payload) {
        var bubble = document.createElement('div');
        bubble.className = 'agbrain-msg agbrain-msg--' + role;
        bubble.setAttribute('role', 'listitem');

        if (role === 'bot' && payload && typeof payload === 'object') {
            var text = payload.text || payload.reply || '';
            if (text) {
                var textNode = document.createElement('div');
                textNode.className = 'agbrain-msg__text';
                textNode.innerHTML = formatMarkdown(String(text));
                bubble.appendChild(textNode);
            }
            if (Array.isArray(payload.products) && payload.products.length) {
                bubble.appendChild(renderProductCards(payload.products));
            }
        } else {
            bubble.innerHTML = formatMarkdown(String(payload));
        }

        container.appendChild(bubble);
        container.scrollTop = container.scrollHeight;
        return bubble;
    }

    function appendThinking(container) {
        var el = document.createElement('div');
        el.className = 'agbrain-msg agbrain-msg--bot agbrain-msg--thinking';
        el.setAttribute('role', 'listitem');
        el.setAttribute('aria-label', I18N.thinking || 'Thinking…');
        el.innerHTML = '<span class="agbrain-dot"></span><span class="agbrain-dot"></span><span class="agbrain-dot"></span>';
        container.appendChild(el);
        container.scrollTop = container.scrollHeight;
        return el;
    }

    function renderProductCards(products) {
        var grid = document.createElement('div');
        grid.className = 'agbrain-products';

        products.forEach(function (product) {
            var card = document.createElement('article');
            card.className = 'agbrain-product-card';

            var title = product.title || product.name || 'Product';
            var imageHtml = product.image_url
                ? '<img class="agbrain-product-card__img" src="' + escapeAttr(product.image_url) + '" alt="' + escapeAttr(title) + '" loading="lazy" />'
                : '<div class="agbrain-product-card__img agbrain-product-card__img--placeholder" aria-hidden="true">🛍️</div>';

            var price = '';
            if (product.price) {
                price = '<span class="agbrain-product-card__price">' + escapeHtml(String(product.currency || '')) + escapeHtml(String(product.price)) + '</span>';
            }

            var description = product.short_desc || product.description || '';
            var bodyHtml = '' +
                imageHtml +
                '<div class="agbrain-product-card__body">' +
                    '<strong class="agbrain-product-card__title">' + escapeHtml(title) + '</strong>' +
                    price +
                    (description ? '<p class="agbrain-product-card__desc">' + escapeHtml(String(description).slice(0, 120)) + '</p>' : '') +
                    '<div class="agbrain-product-card__actions"></div>' +
                '</div>';

            card.innerHTML = bodyHtml;

            var actions = card.querySelector('.agbrain-product-card__actions');
            if (product.url) {
                var viewLink = document.createElement('a');
                viewLink.className = 'agbrain-product-card__button agbrain-product-card__button--secondary';
                viewLink.href = product.url;
                viewLink.target = '_blank';
                viewLink.rel = 'noopener';
                viewLink.textContent = I18N.viewProduct || 'View product';
                actions.appendChild(viewLink);
            }

            if (product.cart_supported && product.id) {
                var addButton = document.createElement('button');
                addButton.className = 'agbrain-product-card__button agbrain-product-card__button--primary';
                addButton.type = 'button';
                addButton.textContent = I18N.addToCart || 'Add to cart';
                addButton.addEventListener('click', function () {
                    addToCart(product, addButton);
                });
                actions.appendChild(addButton);
            }

            grid.appendChild(card);
        });

        return grid;
    }

    function addToCart(product, button) {
        if (!product || !product.id || !config.wcAjaxUrl) {
            setButtonState(button, I18N.cartFailed || 'Could not add this item to the cart.', false);
            return;
        }

        button.disabled = true;
        button.textContent = I18N.addToCart || 'Add to cart';

        var body = new window.URLSearchParams();
        body.append('product_id', product.id);
        body.append('quantity', 1);

        fetch(config.wcAjaxUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
            },
            body: body.toString()
        })
            .then(parseJson)
            .then(function (data) {
                if (data && data.error && product.url) {
                    window.location.href = product.url;
                    return;
                }
                setButtonState(button, I18N.addedToCart || 'Added to cart.', true);
                document.body.dispatchEvent(new CustomEvent('agbrain:added-to-cart', { detail: product }));
            })
            .catch(function () {
                setButtonState(button, I18N.cartFailed || 'Could not add this item to the cart.', false);
            })
            .finally(function () {
                window.setTimeout(function () {
                    button.disabled = false;
                    button.textContent = I18N.addToCart || 'Add to cart';
                    button.removeAttribute('data-status');
                }, 2000);
            });
    }

    function setButtonState(button, text, success) {
        button.textContent = text;
        button.setAttribute('data-status', success ? 'success' : 'error');
    }

    function normalizeChatPayload(data) {
        return {
            text: data.reply || data.text || data.message || '',
            products: Array.isArray(data.products) ? data.products : []
        };
    }

    function initProductSearch() {
        document.querySelectorAll('.agbrain-product-search').forEach(function (wrapper) {
            if (wrapper.__agbrainSearchReady) {
                return;
            }
            wrapper.__agbrainSearchReady = true;

            var input = wrapper.querySelector('.agbrain-search-input');
            var results = wrapper.querySelector('.agbrain-search-results');
            var limit = parseInt(wrapper.dataset.limit || '6', 10);
            var debounce;

            if (!input || !results) {
                return;
            }

            input.addEventListener('input', function () {
                clearTimeout(debounce);
                var query = input.value.trim();
                if (query.length < 2) {
                    results.innerHTML = '';
                    return;
                }

                debounce = window.setTimeout(function () {
                    results.innerHTML = '<p class="agbrain-searching">' + escapeHtml(I18N.searching || 'Searching…') + '</p>';

                    fetch(REST_URL + '/search', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-WP-Nonce': NONCE
                        },
                        body: JSON.stringify({ query: query, limit: limit })
                    })
                        .then(parseJson)
                        .then(function (data) {
                            results.innerHTML = '';
                            if (Array.isArray(data.products) && data.products.length) {
                                results.appendChild(renderProductCards(data.products));
                            } else {
                                results.innerHTML = '<p>' + escapeHtml(data.message || I18N.noResults || 'No results found.') + '</p>';
                            }
                        })
                        .catch(function () {
                            results.innerHTML = '<p>' + escapeHtml(I18N.error || 'Something went wrong. Please try again.') + '</p>';
                        });
                }, 300);
            });
        });
    }

    function setStatus(element, message) {
        if (element) {
            element.textContent = message || '';
        }
    }

    function parseJson(response) {
        return response.json();
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    function escapeAttr(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function formatMarkdown(str) {
        return escapeHtml(str)
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/`(.+?)`/g, '<code>$1</code>')
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
            .replace(/\n/g, '<br>');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
