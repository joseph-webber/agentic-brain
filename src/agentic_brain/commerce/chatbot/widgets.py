# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Embeddable widgets for exposing the WooCommerce chatbot inside WordPress."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ChatWidgetConfig:
    """Configuration for the embeddable WooCommerce chat widget."""

    api_endpoint: str
    store_name: str = "Agentic Store"
    welcome_message: str = "Hi! I can help with products, orders, and returns."
    launcher_label: str = "Open shopping assistant"
    accent_color: str = "#6d28d9"
    position: str = "bottom-right"
    shortcode_tag: str = "agentic_brain_chatbot"
    block_name: str = "agentic-brain/woocommerce-chatbot"


def render_chat_widget_html(config: ChatWidgetConfig) -> str:
    """Return accessible HTML, CSS, and JavaScript for a drop-in storefront widget."""
    position_styles = {
        "bottom-right": "right: 24px; bottom: 24px;",
        "bottom-left": "left: 24px; bottom: 24px;",
    }
    dock_position = position_styles.get(
        config.position, position_styles["bottom-right"]
    )
    return f"""
<div class="agentic-brain-chatbot" data-endpoint="{config.api_endpoint}" aria-live="polite">
  <button
    type="button"
    class="agentic-brain-chatbot__launcher"
    aria-expanded="false"
    aria-controls="agentic-brain-chatbot-panel"
    aria-label="{config.launcher_label}"
  >
    Chat with {config.store_name}
  </button>
  <section
    id="agentic-brain-chatbot-panel"
    class="agentic-brain-chatbot__panel"
    hidden
    role="dialog"
    aria-modal="false"
    aria-label="{config.store_name} shopping assistant"
  >
    <header class="agentic-brain-chatbot__header">
      <h2>{config.store_name} assistant</h2>
      <button type="button" class="agentic-brain-chatbot__close" aria-label="Close chat">×</button>
    </header>
    <div class="agentic-brain-chatbot__messages" role="log" aria-live="polite" aria-label="Chat conversation">
      <p class="agentic-brain-chatbot__message agentic-brain-chatbot__message--assistant">{config.welcome_message}</p>
    </div>
    <form class="agentic-brain-chatbot__form">
      <label for="agentic-brain-chatbot-input">Ask a shopping question</label>
      <input id="agentic-brain-chatbot-input" name="message" type="text" autocomplete="off" required />
      <button type="submit">Send</button>
    </form>
  </section>
</div>
<style>
  .agentic-brain-chatbot {{ position: fixed; z-index: 9999; {dock_position} font-family: system-ui, sans-serif; }}
  .agentic-brain-chatbot__launcher,
  .agentic-brain-chatbot__form button,
  .agentic-brain-chatbot__close {{
    background: {config.accent_color};
    color: #fff;
    border: 0;
    border-radius: 999px;
    padding: 0.8rem 1.2rem;
    cursor: pointer;
  }}
  .agentic-brain-chatbot__launcher:focus,
  .agentic-brain-chatbot__form button:focus,
  .agentic-brain-chatbot__close:focus,
  .agentic-brain-chatbot__form input:focus {{ outline: 3px solid rgba(109, 40, 217, 0.35); outline-offset: 2px; }}
  .agentic-brain-chatbot__panel {{ width: min(380px, calc(100vw - 32px)); background: #fff; color: #111827; border-radius: 18px; box-shadow: 0 12px 28px rgba(0,0,0,0.18); margin-top: 12px; overflow: hidden; }}
  .agentic-brain-chatbot__header {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 1rem; background: #f9fafb; }}
  .agentic-brain-chatbot__messages {{ max-height: 320px; overflow-y: auto; padding: 1rem; }}
  .agentic-brain-chatbot__message {{ margin: 0 0 0.75rem 0; line-height: 1.5; }}
  .agentic-brain-chatbot__form {{ display: grid; gap: 0.75rem; padding: 1rem; border-top: 1px solid #e5e7eb; }}
  .agentic-brain-chatbot__form input {{ border: 1px solid #cbd5e1; border-radius: 12px; padding: 0.75rem; }}
</style>
<script>
(() => {{
  const root = document.currentScript?.previousElementSibling?.previousElementSibling || document.querySelector('.agentic-brain-chatbot');
  if (!root) return;
  const launcher = root.querySelector('.agentic-brain-chatbot__launcher');
  const panel = root.querySelector('.agentic-brain-chatbot__panel');
  const closeButton = root.querySelector('.agentic-brain-chatbot__close');
  const form = root.querySelector('.agentic-brain-chatbot__form');
  const input = root.querySelector('#agentic-brain-chatbot-input');
  const log = root.querySelector('.agentic-brain-chatbot__messages');
  const endpoint = root.dataset.endpoint;

  const toggle = (open) => {{
    panel.hidden = !open;
    launcher.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) input.focus();
  }};

  const appendMessage = (role, text) => {{
    const node = document.createElement('p');
    node.className = `agentic-brain-chatbot__message agentic-brain-chatbot__message--${{role}}`;
    node.textContent = text;
    log.appendChild(node);
    log.scrollTop = log.scrollHeight;
  }};

  launcher.addEventListener('click', () => toggle(panel.hidden));
  closeButton.addEventListener('click', () => toggle(false));
  form.addEventListener('submit', async (event) => {{
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    appendMessage('user', message);
    input.value = '';
    try {{
      const response = await fetch(endpoint, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ message }})
      }});
      const payload = await response.json();
      appendMessage('assistant', payload.message || 'I am here to help.');
    }} catch (error) {{
      appendMessage('assistant', 'Sorry, the chat service is temporarily unavailable.');
    }}
  }});
}})();
</script>
""".strip()


def render_wordpress_shortcode(config: ChatWidgetConfig) -> str:
    """Return a WordPress shortcode registration snippet."""
    html = render_chat_widget_html(config).replace("'''", "\\'\\'\\'")
    return f"""
<?php
add_shortcode('{config.shortcode_tag}', function () {{
    ob_start();
    ?>
    {html}
    <?php
    return ob_get_clean();
}});
?>
""".strip()


def render_woocommerce_block(config: ChatWidgetConfig) -> str:
    """Return a JavaScript snippet that registers a WooCommerce block wrapper."""
    return f"""
wp.blocks.registerBlockType('{config.block_name}', {{
  title: 'WooCommerce Chatbot',
  icon: 'format-chat',
  category: 'widgets',
  attributes: {{}},
  edit: function() {{
    return wp.element.createElement('div', {{ className: 'agentic-brain-chatbot-block', role: 'note', 'aria-label': '{config.store_name} chatbot preview' }}, 'WooCommerce chatbot preview');
  }},
  save: function() {{
    return wp.element.RawHTML({{ children: `{render_chat_widget_html(config)}` }});
  }}
}});
""".strip()


__all__ = [
    "ChatWidgetConfig",
    "render_chat_widget_html",
    "render_woocommerce_block",
    "render_wordpress_shortcode",
]
