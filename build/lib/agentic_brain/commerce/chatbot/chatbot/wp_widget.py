# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""WordPress plugin integration templates for the Agentic Brain chat widget.

This is *not* a full WordPress plugin build system. Instead it generates the
minimal PHP/JS/CSS artifacts needed to:
- Embed a chat widget on the front-end (shortcode + optional auto-insert)
- Provide a Gutenberg block
- Provide an Elementor widget

These templates are designed to be mobile responsive and accessible:
- Focusable toggle button
- ARIA labels
- Reasonable contrast defaults
- Keyboard navigation (Escape closes the panel)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(slots=True)
class WordPressChatWidgetConfig:
    plugin_slug: str = "agentic-brain-chat"
    plugin_name: str = "Agentic Brain Chat"
    api_url: str = "https://example.com/api/chat"
    primary_color: str = "#0066cc"
    position: str = "bottom-right"  # bottom-right | bottom-left
    greeting: str = "Hi! How can I help?"
    button_label: str = "Open chat"


def generate_wp_widget_plugin(config: WordPressChatWidgetConfig) -> dict[str, str]:
    """Generate WordPress plugin files.

    Returns:
        Mapping of relative file path -> file contents.
    """

    plugin_php = _generate_plugin_php(config)
    frontend_js = _generate_frontend_js(config)
    frontend_css = _generate_frontend_css(config)
    block_js = _generate_gutenberg_block_js(config)
    elementor_php = _generate_elementor_widget_php(config)

    return {
        f"{config.plugin_slug}.php": plugin_php,
        "assets/chat-widget.js": frontend_js,
        "assets/chat-widget.css": frontend_css,
        "assets/gutenberg-block.js": block_js,
        "elementor/widget.php": elementor_php,
    }


def _generate_plugin_php(config: WordPressChatWidgetConfig) -> str:
    slug = config.plugin_slug
    name = config.plugin_name
    return f"""<?php
/**
 * Plugin Name: {name}
 * Description: Adds an accessible chat widget powered by Agentic Brain.
 * Version: 0.1.0
 */

if (!defined('ABSPATH')) {{ exit; }}

function {slug}_enqueue_assets() {{
    wp_enqueue_style('{slug}-css', plugin_dir_url(__FILE__) . 'assets/chat-widget.css', array(), '0.1.0');
    wp_enqueue_script('{slug}-js', plugin_dir_url(__FILE__) . 'assets/chat-widget.js', array(), '0.1.0', true);
    wp_localize_script('{slug}-js', '{slug}_cfg', array(
        'apiUrl' => '{config.api_url}',
        'primaryColor' => '{config.primary_color}',
        'position' => '{config.position}',
        'greeting' => '{config.greeting}',
        'buttonLabel' => '{config.button_label}',
    ));
}}
add_action('wp_enqueue_scripts', '{slug}_enqueue_assets');

function {slug}_shortcode($atts) {{
    return '<div class="ab-chat" data-agentic-brain-chat="1"></div>';
}}
add_shortcode('agentic_brain_chat', '{slug}_shortcode');

// Gutenberg block (front-end only; editor bundle can be added later)
function {slug}_register_block_assets() {{
    wp_register_script('{slug}-block', plugin_dir_url(__FILE__) . 'assets/gutenberg-block.js', array('wp-blocks', 'wp-element', 'wp-editor'), '0.1.0', true);
    if (function_exists('register_block_type')) {{
        register_block_type('agentic-brain/chat', array(
            'editor_script' => '{slug}-block',
            'render_callback' => function() {{
                return do_shortcode('[agentic_brain_chat]');
            }}
        ));
    }}
}}
add_action('init', '{slug}_register_block_assets');

// Elementor widget support
add_action('elementor/widgets/register', function($widgets_manager) {{
    if (!class_exists('\\Elementor\\Widget_Base')) {{ return; }}
    require_once plugin_dir_path(__FILE__) . 'elementor/widget.php';
    $widgets_manager->register(new Agentic_Brain_Chat_Elementor_Widget());
}});
"""


def _generate_frontend_js(config: WordPressChatWidgetConfig) -> str:
    slug = config.plugin_slug.replace("-", "_")
    return f"""(function() {{
  'use strict';

  function el(tag, attrs, children) {{
    var node = document.createElement(tag);
    if (attrs) {{
      Object.keys(attrs).forEach(function(key) {{
        if (key === 'className') node.className = attrs[key];
        else if (key === 'text') node.textContent = attrs[key];
        else node.setAttribute(key, attrs[key]);
      }});
    }}
    (children || []).forEach(function(child) {{ node.appendChild(child); }});
    return node;
  }}

  function init(container, cfg) {{
    if (!cfg || !cfg.apiUrl) return;

    var root = el('div', {{ className: 'ab-chat-root ab-pos-' + (cfg.position || 'bottom-right') }});

    var button = el('button', {{
      className: 'ab-chat-toggle',
      type: 'button',
      'aria-label': cfg.buttonLabel || 'Open chat',
      'aria-expanded': 'false'
    }}, [el('span', {{ text: 'Chat' }})]);

    var panel = el('div', {{ className: 'ab-chat-panel', role: 'dialog', 'aria-label': 'Chat panel' }});
    var header = el('div', {{ className: 'ab-chat-header' }}, [
      el('div', {{ className: 'ab-chat-title', text: 'Chat' }}),
      el('button', {{ className: 'ab-chat-close', type: 'button', 'aria-label': 'Close chat' }}, [el('span', {{ text: '×' }})])
    ]);

    var messages = el('div', {{ className: 'ab-chat-messages', role: 'log', 'aria-live': 'polite' }});
    var form = el('form', {{ className: 'ab-chat-form' }});
    var input = el('input', {{ className: 'ab-chat-input', type: 'text', 'aria-label': 'Message', placeholder: 'Type a message…' }});
    var send = el('button', {{ className: 'ab-chat-send', type: 'submit', 'aria-label': 'Send message' }}, [el('span', {{ text: 'Send' }})]);

    function addMessage(role, text) {{
      var item = el('div', {{ className: 'ab-chat-msg ab-' + role }});
      item.textContent = text;
      messages.appendChild(item);
      messages.scrollTop = messages.scrollHeight;
    }}

    function open() {{
      root.classList.add('ab-open');
      button.setAttribute('aria-expanded', 'true');
      input.focus();
    }}

    function close() {{
      root.classList.remove('ab-open');
      button.setAttribute('aria-expanded', 'false');
      button.focus();
    }}

    button.addEventListener('click', function() {{
      if (root.classList.contains('ab-open')) close(); else open();
    }});

    header.querySelector('.ab-chat-close').addEventListener('click', close);

    document.addEventListener('keydown', function(ev) {{
      if (ev.key === 'Escape' && root.classList.contains('ab-open')) close();
    }});

    form.addEventListener('submit', function(ev) {{
      ev.preventDefault();
      var text = (input.value || '').trim();
      if (!text) return;
      input.value = '';
      addMessage('user', text);

      fetch(cfg.apiUrl, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ message: text }})
      }})
      .then(function(res) {{ return res.json(); }})
      .then(function(data) {{
        addMessage('bot', (data && (data.response || data.message)) || 'No response');
      }})
      .catch(function() {{
        addMessage('bot', 'Sorry, the chat service is unavailable right now.');
      }});
    }});

    panel.appendChild(header);
    panel.appendChild(messages);
    form.appendChild(input);
    form.appendChild(send);
    panel.appendChild(form);

    root.appendChild(button);
    root.appendChild(panel);

    container.appendChild(root);

    addMessage('bot', cfg.greeting || 'Hi!');

    // Apply theme variable
    root.style.setProperty('--ab-primary', cfg.primaryColor || '#0066cc');
  }}

  function boot() {{
    var cfg = window.{slug}_cfg || {{}};
    var containers = document.querySelectorAll('[data-agentic-brain-chat]');
    if (!containers.length) return;
    for (var i = 0; i < containers.length; i++) {{
      init(containers[i], cfg);
    }}
  }}

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
}})();
"""


def _generate_frontend_css(config: WordPressChatWidgetConfig) -> str:
    return f"""/* Accessible, mobile-first chat widget */

.ab-chat-root {{
  --ab-primary: {config.primary_color};
  position: fixed;
  z-index: 99999;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
}}

.ab-pos-bottom-right {{ right: 16px; bottom: 16px; }}
.ab-pos-bottom-left {{ left: 16px; bottom: 16px; }}

.ab-chat-toggle {{
  background: var(--ab-primary);
  color: #fff;
  border: none;
  padding: 12px 14px;
  border-radius: 999px;
  cursor: pointer;
}}

.ab-chat-toggle:focus {{
  outline: 3px solid rgba(0, 102, 204, 0.35);
  outline-offset: 3px;
}}

.ab-chat-panel {{
  display: none;
  width: 360px;
  max-width: calc(100vw - 32px);
  height: 480px;
  max-height: calc(100vh - 120px);
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 12px;
  margin-top: 10px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.18);
  overflow: hidden;
}}

.ab-open .ab-chat-panel {{ display: block; }}

.ab-chat-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: #f6f7f8;
  border-bottom: 1px solid #e6e6e6;
}}

.ab-chat-close {{
  background: transparent;
  border: none;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
}}

.ab-chat-close:focus {{
  outline: 2px solid var(--ab-primary);
  outline-offset: 2px;
}}

.ab-chat-messages {{
  padding: 10px 12px;
  height: calc(100% - 110px);
  overflow-y: auto;
}}

.ab-chat-msg {{
  padding: 8px 10px;
  border-radius: 10px;
  margin-bottom: 8px;
  max-width: 90%;
  word-wrap: break-word;
}}

.ab-user {{
  background: rgba(0, 102, 204, 0.12);
  margin-left: auto;
}}

.ab-bot {{
  background: #f1f1f1;
  margin-right: auto;
}}

.ab-chat-form {{
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  border-top: 1px solid #e6e6e6;
}}

.ab-chat-input {{
  flex: 1;
  border: 1px solid #ccc;
  border-radius: 8px;
  padding: 10px;
}}

.ab-chat-input:focus {{
  outline: 2px solid var(--ab-primary);
  outline-offset: 2px;
}}

.ab-chat-send {{
  background: var(--ab-primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 12px;
}}

.ab-chat-send:focus {{
  outline: 3px solid rgba(0, 102, 204, 0.35);
  outline-offset: 2px;
}}

@media (max-width: 480px) {{
  .ab-chat-panel {{
    width: calc(100vw - 32px);
    height: calc(100vh - 140px);
  }}
}}
"""


def _generate_gutenberg_block_js(config: WordPressChatWidgetConfig) -> str:
    # Minimal front-end block registration.
    return """(function(blocks, element) {
  var el = element.createElement;
  blocks.registerBlockType('agentic-brain/chat', {
    title: 'Agentic Brain Chat',
    icon: 'format-chat',
    category: 'widgets',
    edit: function() {
      return el('p', {}, 'Agentic Brain Chat widget (renders on front-end).');
    },
    save: function() {
      return null; // rendered in PHP
    }
  });
})(window.wp.blocks, window.wp.element);
"""


def _generate_elementor_widget_php(config: WordPressChatWidgetConfig) -> str:
    return """<?php

if (!defined('ABSPATH')) { exit; }

class Agentic_Brain_Chat_Elementor_Widget extends \\Elementor\\Widget_Base {

    public function get_name() { return 'agentic_brain_chat'; }
    public function get_title() { return 'Agentic Brain Chat'; }
    public function get_icon() { return 'eicon-chat'; }
    public function get_categories() { return array('general'); }

    protected function render() {
        echo do_shortcode('[agentic_brain_chat]');
    }
}
"""


__all__ = ["WordPressChatWidgetConfig", "generate_wp_widget_plugin"]
