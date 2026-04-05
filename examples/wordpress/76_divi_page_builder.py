#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Divi Page Builder Assistant - Agentic Brain Example #76

An intelligent assistant for building pages with Divi Theme Builder:
- Divi module suggestions based on content type
- Layout recommendations
- Section templates (hero, features, testimonials, CTA)
- Color scheme management
- Typography suggestions
- Mobile responsiveness checks
- A/B testing setup
- Page speed optimization tips

Perfect for building an electronics store with Divi.

Usage:
    python 76_divi_page_builder.py --demo
    python 76_divi_page_builder.py --page product --product "Wireless Earbuds"
"""

import asyncio
import colorsys
import json
import logging
import os
import random
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================


class PageType(Enum):
    """Types of pages for electronics store."""

    HOME = "home"
    PRODUCT = "product"
    CATEGORY = "category"
    ABOUT = "about"
    CONTACT = "contact"
    BLOG = "blog"
    LANDING = "landing"
    CHECKOUT = "checkout"
    CART = "cart"
    FAQ = "faq"
    COMPARISON = "comparison"
    DEALS = "deals"


class DiviModule(Enum):
    """Divi Builder modules."""

    TEXT = "et_pb_text"
    IMAGE = "et_pb_image"
    BUTTON = "et_pb_button"
    BLURB = "et_pb_blurb"
    CTA = "et_pb_cta"
    SLIDER = "et_pb_slider"
    FULLWIDTH_SLIDER = "et_pb_fullwidth_slider"
    GALLERY = "et_pb_gallery"
    VIDEO = "et_pb_video"
    VIDEO_SLIDER = "et_pb_video_slider"
    TESTIMONIAL = "et_pb_testimonial"
    PRICING_TABLE = "et_pb_pricing_table"
    TABS = "et_pb_tabs"
    ACCORDION = "et_pb_accordion"
    TOGGLE = "et_pb_toggle"
    COUNTER = "et_pb_number_counter"
    COUNTDOWN = "et_pb_countdown_timer"
    BAR_COUNTER = "et_pb_bar_counters"
    CIRCLE_COUNTER = "et_pb_circle_counter"
    DIVIDER = "et_pb_divider"
    SIDEBAR = "et_pb_sidebar"
    BLOG = "et_pb_blog"
    SHOP = "et_pb_shop"
    MAP = "et_pb_map"
    CONTACT_FORM = "et_pb_contact_form"
    SOCIAL_FOLLOW = "et_pb_social_media_follow"
    CODE = "et_pb_code"
    FULLWIDTH_HEADER = "et_pb_fullwidth_header"
    FULLWIDTH_IMAGE = "et_pb_fullwidth_image"
    FULLWIDTH_CODE = "et_pb_fullwidth_code"
    FULLWIDTH_MENU = "et_pb_fullwidth_menu"
    WOOCOMMERCE_PRODUCT = "et_pb_wc_images"
    WOOCOMMERCE_TITLE = "et_pb_wc_title"
    WOOCOMMERCE_PRICE = "et_pb_wc_price"
    WOOCOMMERCE_CART = "et_pb_wc_add_to_cart"
    WOOCOMMERCE_RELATED = "et_pb_wc_related_products"


class SectionType(Enum):
    """Types of page sections."""

    HERO = "hero"
    FEATURES = "features"
    PRODUCTS = "products"
    TESTIMONIALS = "testimonials"
    CTA = "cta"
    FAQ = "faq"
    PRICING = "pricing"
    TEAM = "team"
    GALLERY = "gallery"
    CONTACT = "contact"
    NEWSLETTER = "newsletter"
    COMPARISON = "comparison"
    STATS = "stats"
    BRANDS = "brands"
    FOOTER = "footer"


class ColorSchemeType(Enum):
    """Color scheme types."""

    PROFESSIONAL = "professional"
    MODERN = "modern"
    TECH = "tech"
    MINIMAL = "minimal"
    BOLD = "bold"
    ELEGANT = "elegant"
    PLAYFUL = "playful"
    DARK = "dark"
    LIGHT = "light"


class DeviceType(Enum):
    """Device types for responsive design."""

    DESKTOP = "desktop"
    TABLET = "tablet"
    PHONE = "phone"


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class ColorPalette:
    """Color palette for a page or site."""

    primary: str = "#2563eb"  # Blue
    secondary: str = "#7c3aed"  # Purple
    accent: str = "#f59e0b"  # Amber
    text_dark: str = "#1f2937"  # Gray 800
    text_light: str = "#6b7280"  # Gray 500
    background: str = "#ffffff"
    background_alt: str = "#f3f4f6"  # Gray 100
    success: str = "#10b981"  # Green
    warning: str = "#f59e0b"  # Amber
    error: str = "#ef4444"  # Red

    def to_css_variables(self) -> str:
        """Generate CSS custom properties."""
        return f"""
:root {{
    --color-primary: {self.primary};
    --color-secondary: {self.secondary};
    --color-accent: {self.accent};
    --color-text-dark: {self.text_dark};
    --color-text-light: {self.text_light};
    --color-background: {self.background};
    --color-background-alt: {self.background_alt};
    --color-success: {self.success};
    --color-warning: {self.warning};
    --color-error: {self.error};
}}
"""

    def get_contrast_color(self, bg_color: str) -> str:
        """Get appropriate text color for background."""
        # Simple luminance check
        hex_color = bg_color.lstrip("#")
        r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return self.text_dark if luminance > 0.5 else "#ffffff"

    def generate_gradient(self, direction: str = "to right") -> str:
        """Generate CSS gradient from primary to secondary."""
        return f"linear-gradient({direction}, {self.primary}, {self.secondary})"


@dataclass
class Typography:
    """Typography settings."""

    heading_font: str = "Montserrat"
    body_font: str = "Open Sans"
    heading_weight: int = 700
    body_weight: int = 400
    base_size: int = 16
    line_height: float = 1.6
    heading_line_height: float = 1.2

    # Size scale (based on perfect fourth - 1.333)
    scale_ratio: float = 1.333

    def get_size(self, level: int) -> int:
        """Get font size for heading level."""
        # h1 = level 1, h2 = level 2, etc.
        multiplier = self.scale_ratio ** (6 - level)
        return round(self.base_size * multiplier)

    def to_css(self) -> str:
        """Generate CSS for typography."""
        return f"""
body {{
    font-family: '{self.body_font}', sans-serif;
    font-size: {self.base_size}px;
    font-weight: {self.body_weight};
    line-height: {self.line_height};
}}

h1, h2, h3, h4, h5, h6 {{
    font-family: '{self.heading_font}', sans-serif;
    font-weight: {self.heading_weight};
    line-height: {self.heading_line_height};
}}

h1 {{ font-size: {self.get_size(1)}px; }}
h2 {{ font-size: {self.get_size(2)}px; }}
h3 {{ font-size: {self.get_size(3)}px; }}
h4 {{ font-size: {self.get_size(4)}px; }}
h5 {{ font-size: {self.get_size(5)}px; }}
h6 {{ font-size: {self.get_size(6)}px; }}
"""

    def to_divi_settings(self) -> Dict[str, Any]:
        """Convert to Divi theme options format."""
        return {
            "et_header_font": self.heading_font,
            "et_body_font": self.body_font,
            "et_header_font_style": f"{self.heading_weight}",
            "et_body_font_style": f"{self.body_weight}",
            "et_body_font_size": f"{self.base_size}px",
            "et_section_padding": "4%",
        }


@dataclass
class ResponsiveSettings:
    """Responsive design settings."""

    desktop_width: int = 1200
    tablet_width: int = 980
    phone_width: int = 767

    # Visibility settings
    show_on_desktop: bool = True
    show_on_tablet: bool = True
    show_on_phone: bool = True

    # Spacing multipliers
    tablet_spacing: float = 0.8
    phone_spacing: float = 0.6

    # Font size multipliers
    tablet_font_scale: float = 0.9
    phone_font_scale: float = 0.85

    def get_media_queries(self) -> str:
        """Generate responsive media queries."""
        return f"""
/* Desktop */
@media (min-width: {self.tablet_width + 1}px) {{
    .section-padding {{ padding: 80px 0; }}
}}

/* Tablet */
@media (max-width: {self.tablet_width}px) {{
    .section-padding {{ padding: {int(80 * self.tablet_spacing)}px 0; }}
    body {{ font-size: {int(16 * self.tablet_font_scale)}px; }}
}}

/* Phone */
@media (max-width: {self.phone_width}px) {{
    .section-padding {{ padding: {int(80 * self.phone_spacing)}px 0; }}
    body {{ font-size: {int(16 * self.phone_font_scale)}px; }}
}}
"""


@dataclass
class DiviModuleConfig:
    """Configuration for a Divi module."""

    module_type: DiviModule
    title: str = ""
    content: str = ""
    settings: Dict[str, Any] = field(default_factory=dict)
    responsive: ResponsiveSettings = field(default_factory=ResponsiveSettings)
    custom_css: str = ""
    animation: str = ""

    def to_shortcode(self) -> str:
        """Generate Divi shortcode."""
        attrs = []

        for key, value in self.settings.items():
            if isinstance(value, bool):
                attrs.append(f'{key}="{str(value).lower()}"')
            elif isinstance(value, (int, float)):
                attrs.append(f'{key}="{value}"')
            else:
                attrs.append(f'{key}="{value}"')

        if self.animation:
            attrs.append(f'animation_style="{self.animation}"')

        attrs_str = " ".join(attrs)

        if self.content:
            return f"[{self.module_type.value} {attrs_str}]{self.content}[/{self.module_type.value}]"
        else:
            return f"[{self.module_type.value} {attrs_str} /]"


@dataclass
class SectionTemplate:
    """Template for a page section."""

    section_type: SectionType
    title: str
    modules: List[DiviModuleConfig] = field(default_factory=list)
    background_color: str = ""
    background_image: str = ""
    background_gradient: str = ""
    padding_top: int = 80
    padding_bottom: int = 80
    columns: int = 1
    column_layout: str = "1_1"  # e.g., "1_2,1_2" for two equal columns

    def to_divi_section(self) -> str:
        """Generate Divi section shortcode."""
        section_attrs = []

        if self.background_color:
            section_attrs.append(f'background_color="{self.background_color}"')
        if self.background_image:
            section_attrs.append(f'background_image="{self.background_image}"')

        section_attrs.append(
            f'custom_padding="{self.padding_top}px||{self.padding_bottom}px|"'
        )

        attrs_str = " ".join(section_attrs)

        # Build row and columns
        modules_content = "\n".join(m.to_shortcode() for m in self.modules)

        return f"""
[et_pb_section {attrs_str}]
    [et_pb_row column_structure="{self.column_layout}"]
        [et_pb_column type="{self.column_layout.split(',')[0] if ',' in self.column_layout else '4_4'}"]
            {modules_content}
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""


@dataclass
class ABTestVariant:
    """A/B test variant."""

    variant_id: str
    name: str
    description: str
    section: SectionTemplate
    weight: float = 0.5  # Traffic allocation

    def to_config(self) -> Dict[str, Any]:
        """Convert to A/B test configuration."""
        return {
            "id": self.variant_id,
            "name": self.name,
            "description": self.description,
            "weight": self.weight,
            "section_type": self.section.section_type.value,
        }


@dataclass
class ABTest:
    """A/B test configuration."""

    test_id: str
    name: str
    description: str
    page_type: PageType
    section_type: SectionType
    variants: List[ABTestVariant] = field(default_factory=list)
    goal: str = "conversion"  # conversion, engagement, revenue
    status: str = "draft"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    def add_variant(self, variant: ABTestVariant):
        """Add a variant to the test."""
        self.variants.append(variant)
        self._normalize_weights()

    def _normalize_weights(self):
        """Ensure weights sum to 1.0."""
        total = sum(v.weight for v in self.variants)
        if total > 0:
            for v in self.variants:
                v.weight = v.weight / total


@dataclass
class PageSpeedIssue:
    """Page speed optimization issue."""

    severity: str  # critical, warning, info
    category: str  # images, css, js, fonts, server
    title: str
    description: str
    recommendation: str
    impact: str  # high, medium, low
    divi_specific: bool = False


@dataclass
class PageLayout:
    """Complete page layout configuration."""

    page_type: PageType
    title: str
    sections: List[SectionTemplate] = field(default_factory=list)
    colors: ColorPalette = field(default_factory=ColorPalette)
    typography: Typography = field(default_factory=Typography)
    responsive: ResponsiveSettings = field(default_factory=ResponsiveSettings)
    custom_css: str = ""
    ab_tests: List[ABTest] = field(default_factory=list)

    def to_divi_layout(self) -> str:
        """Generate complete Divi layout code."""
        sections_code = "\n".join(s.to_divi_section() for s in self.sections)
        return sections_code


# ============================================================================
# COLOR SCHEME MANAGER
# ============================================================================


class ColorSchemeManager:
    """Manages color schemes and palettes."""

    PRESET_SCHEMES = {
        ColorSchemeType.PROFESSIONAL: ColorPalette(
            primary="#2563eb",
            secondary="#1e40af",
            accent="#f59e0b",
            text_dark="#1f2937",
            background="#ffffff",
        ),
        ColorSchemeType.MODERN: ColorPalette(
            primary="#8b5cf6",
            secondary="#6366f1",
            accent="#ec4899",
            text_dark="#111827",
            background="#ffffff",
        ),
        ColorSchemeType.TECH: ColorPalette(
            primary="#06b6d4",
            secondary="#0891b2",
            accent="#22c55e",
            text_dark="#0f172a",
            background="#f8fafc",
        ),
        ColorSchemeType.MINIMAL: ColorPalette(
            primary="#171717",
            secondary="#404040",
            accent="#3b82f6",
            text_dark="#171717",
            background="#ffffff",
        ),
        ColorSchemeType.BOLD: ColorPalette(
            primary="#dc2626",
            secondary="#b91c1c",
            accent="#fbbf24",
            text_dark="#1f2937",
            background="#ffffff",
        ),
        ColorSchemeType.DARK: ColorPalette(
            primary="#3b82f6",
            secondary="#60a5fa",
            accent="#fbbf24",
            text_dark="#f9fafb",
            text_light="#9ca3af",
            background="#111827",
            background_alt="#1f2937",
        ),
    }

    @classmethod
    def get_scheme(cls, scheme_type: ColorSchemeType) -> ColorPalette:
        """Get a preset color scheme."""
        return cls.PRESET_SCHEMES.get(
            scheme_type, cls.PRESET_SCHEMES[ColorSchemeType.PROFESSIONAL]
        )

    @classmethod
    def suggest_scheme_for_industry(cls, industry: str) -> ColorSchemeType:
        """Suggest color scheme based on industry."""
        industry_schemes = {
            "electronics": ColorSchemeType.TECH,
            "technology": ColorSchemeType.TECH,
            "fashion": ColorSchemeType.MODERN,
            "finance": ColorSchemeType.PROFESSIONAL,
            "healthcare": ColorSchemeType.MINIMAL,
            "food": ColorSchemeType.BOLD,
            "gaming": ColorSchemeType.DARK,
            "luxury": ColorSchemeType.ELEGANT,
        }
        return industry_schemes.get(industry.lower(), ColorSchemeType.PROFESSIONAL)

    @staticmethod
    def generate_complementary(base_color: str) -> str:
        """Generate complementary color."""
        hex_color = base_color.lstrip("#")
        r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

        # Convert to HSL
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)

        # Complementary = opposite hue
        h_comp = (h + 0.5) % 1.0

        # Convert back to RGB
        r, g, b = colorsys.hls_to_rgb(h_comp, l, s)

        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

    @staticmethod
    def generate_triadic(base_color: str) -> Tuple[str, str]:
        """Generate triadic colors."""
        hex_color = base_color.lstrip("#")
        r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)

        # Triadic = 120 degrees apart
        h1 = (h + 1 / 3) % 1.0
        h2 = (h + 2 / 3) % 1.0

        r1, g1, b1 = colorsys.hls_to_rgb(h1, l, s)
        r2, g2, b2 = colorsys.hls_to_rgb(h2, l, s)

        color1 = f"#{int(r1*255):02x}{int(g1*255):02x}{int(b1*255):02x}"
        color2 = f"#{int(r2*255):02x}{int(g2*255):02x}{int(b2*255):02x}"

        return color1, color2

    @staticmethod
    def adjust_brightness(color: str, factor: float) -> str:
        """Adjust color brightness."""
        hex_color = color.lstrip("#")
        r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)

        # Adjust lightness
        l = max(0, min(1, l * factor))

        r, g, b = colorsys.hls_to_rgb(h, l, s)

        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


# ============================================================================
# MODULE SUGGESTER
# ============================================================================


class ModuleSuggester:
    """Suggests Divi modules based on content and context."""

    # Module suggestions by section type
    SECTION_MODULES = {
        SectionType.HERO: [
            DiviModule.FULLWIDTH_HEADER,
            DiviModule.FULLWIDTH_SLIDER,
            DiviModule.TEXT,
            DiviModule.BUTTON,
        ],
        SectionType.FEATURES: [
            DiviModule.BLURB,
            DiviModule.TEXT,
            DiviModule.IMAGE,
        ],
        SectionType.PRODUCTS: [
            DiviModule.SHOP,
            DiviModule.WOOCOMMERCE_PRODUCT,
            DiviModule.IMAGE,
            DiviModule.BUTTON,
        ],
        SectionType.TESTIMONIALS: [
            DiviModule.TESTIMONIAL,
            DiviModule.SLIDER,
            DiviModule.TEXT,
        ],
        SectionType.CTA: [
            DiviModule.CTA,
            DiviModule.BUTTON,
            DiviModule.COUNTDOWN,
        ],
        SectionType.FAQ: [
            DiviModule.ACCORDION,
            DiviModule.TOGGLE,
            DiviModule.TEXT,
        ],
        SectionType.PRICING: [
            DiviModule.PRICING_TABLE,
            DiviModule.TEXT,
            DiviModule.BUTTON,
        ],
        SectionType.GALLERY: [
            DiviModule.GALLERY,
            DiviModule.IMAGE,
            DiviModule.VIDEO,
        ],
        SectionType.CONTACT: [
            DiviModule.CONTACT_FORM,
            DiviModule.MAP,
            DiviModule.BLURB,
            DiviModule.SOCIAL_FOLLOW,
        ],
        SectionType.STATS: [
            DiviModule.COUNTER,
            DiviModule.BAR_COUNTER,
            DiviModule.CIRCLE_COUNTER,
        ],
        SectionType.NEWSLETTER: [
            DiviModule.TEXT,
            DiviModule.CODE,  # For email form embed
            DiviModule.BUTTON,
        ],
    }

    # Module suggestions by page type
    PAGE_MODULES = {
        PageType.HOME: [
            DiviModule.FULLWIDTH_SLIDER,
            DiviModule.SHOP,
            DiviModule.BLURB,
            DiviModule.TESTIMONIAL,
            DiviModule.CTA,
        ],
        PageType.PRODUCT: [
            DiviModule.WOOCOMMERCE_PRODUCT,
            DiviModule.WOOCOMMERCE_TITLE,
            DiviModule.WOOCOMMERCE_PRICE,
            DiviModule.WOOCOMMERCE_CART,
            DiviModule.WOOCOMMERCE_RELATED,
            DiviModule.TABS,
            DiviModule.ACCORDION,
        ],
        PageType.CATEGORY: [
            DiviModule.SHOP,
            DiviModule.SIDEBAR,
            DiviModule.TEXT,
        ],
        PageType.BLOG: [
            DiviModule.BLOG,
            DiviModule.SIDEBAR,
            DiviModule.SOCIAL_FOLLOW,
        ],
        PageType.CONTACT: [
            DiviModule.CONTACT_FORM,
            DiviModule.MAP,
            DiviModule.BLURB,
            DiviModule.SOCIAL_FOLLOW,
        ],
        PageType.LANDING: [
            DiviModule.FULLWIDTH_HEADER,
            DiviModule.BLURB,
            DiviModule.TESTIMONIAL,
            DiviModule.CTA,
            DiviModule.COUNTDOWN,
            DiviModule.PRICING_TABLE,
        ],
    }

    @classmethod
    def suggest_for_section(cls, section_type: SectionType) -> List[DiviModule]:
        """Suggest modules for a section type."""
        return cls.SECTION_MODULES.get(section_type, [DiviModule.TEXT])

    @classmethod
    def suggest_for_page(cls, page_type: PageType) -> List[DiviModule]:
        """Suggest modules for a page type."""
        return cls.PAGE_MODULES.get(page_type, [DiviModule.TEXT])

    @classmethod
    def suggest_for_content(cls, content: str) -> List[DiviModule]:
        """Suggest modules based on content analysis."""
        content_lower = content.lower()
        suggestions = []

        # Analyze content for patterns
        if any(word in content_lower for word in ["buy", "price", "shop", "cart"]):
            suggestions.extend(
                [DiviModule.SHOP, DiviModule.BUTTON, DiviModule.PRICING_TABLE]
            )

        if any(
            word in content_lower for word in ["review", "rating", "star", "feedback"]
        ):
            suggestions.append(DiviModule.TESTIMONIAL)

        if any(word in content_lower for word in ["feature", "benefit", "advantage"]):
            suggestions.append(DiviModule.BLURB)

        if any(
            word in content_lower for word in ["compare", "vs", "versus", "difference"]
        ):
            suggestions.append(DiviModule.TABS)

        if any(word in content_lower for word in ["question", "faq", "answer", "help"]):
            suggestions.extend([DiviModule.ACCORDION, DiviModule.TOGGLE])

        if any(
            word in content_lower for word in ["video", "watch", "tutorial", "demo"]
        ):
            suggestions.append(DiviModule.VIDEO)

        if any(
            word in content_lower for word in ["gallery", "photo", "image", "picture"]
        ):
            suggestions.append(DiviModule.GALLERY)

        if any(
            word in content_lower for word in ["contact", "email", "phone", "reach"]
        ):
            suggestions.extend([DiviModule.CONTACT_FORM, DiviModule.MAP])

        if any(
            word in content_lower
            for word in ["limited", "offer", "sale", "discount", "hurry"]
        ):
            suggestions.extend([DiviModule.COUNTDOWN, DiviModule.CTA])

        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for module in suggestions:
            if module not in seen:
                seen.add(module)
                unique.append(module)

        return unique if unique else [DiviModule.TEXT]


# ============================================================================
# SECTION TEMPLATE BUILDER
# ============================================================================


class SectionTemplateBuilder:
    """Builds section templates for common use cases."""

    @staticmethod
    def build_hero_section(
        headline: str,
        subheadline: str,
        cta_text: str = "Shop Now",
        cta_url: str = "/shop",
        background_image: str = "",
        colors: ColorPalette = None,
    ) -> SectionTemplate:
        """Build a hero section."""
        colors = colors or ColorPalette()

        header_module = DiviModuleConfig(
            module_type=DiviModule.FULLWIDTH_HEADER,
            title=headline,
            content=subheadline,
            settings={
                "title": headline,
                "subhead": subheadline,
                "button_one_text": cta_text,
                "button_one_url": cta_url,
                "background_overlay_color": "rgba(0,0,0,0.5)",
                "title_font_size": "60px",
                "title_text_color": "#ffffff",
                "content_font_size": "20px",
                "content_text_color": "#ffffff",
                "button_one_bg_color": colors.accent,
            },
            animation="fade",
        )

        return SectionTemplate(
            section_type=SectionType.HERO,
            title="Hero Section",
            modules=[header_module],
            background_image=background_image,
            padding_top=0,
            padding_bottom=0,
        )

    @staticmethod
    def build_features_section(
        title: str,
        features: List[
            Dict[str, str]
        ],  # [{"title": "", "description": "", "icon": ""}]
        colors: ColorPalette = None,
    ) -> SectionTemplate:
        """Build a features section with blurbs."""
        colors = colors or ColorPalette()

        # Title module
        title_module = DiviModuleConfig(
            module_type=DiviModule.TEXT,
            content=f"<h2 style='text-align: center;'>{title}</h2>",
            settings={
                "text_orientation": "center",
            },
        )

        # Feature blurbs
        modules = [title_module]

        for feature in features:
            blurb = DiviModuleConfig(
                module_type=DiviModule.BLURB,
                title=feature.get("title", ""),
                content=feature.get("description", ""),
                settings={
                    "title": feature.get("title", ""),
                    "use_icon": "on",
                    "font_icon": feature.get("icon", "%%45%%"),
                    "icon_color": colors.primary,
                    "icon_placement": "top",
                    "text_orientation": "center",
                },
                animation="fadeInUp",
            )
            modules.append(blurb)

        return SectionTemplate(
            section_type=SectionType.FEATURES,
            title="Features Section",
            modules=modules,
            background_color=colors.background_alt,
            columns=len(features) if len(features) <= 4 else 3,
            column_layout=",".join(["1_3"] * min(len(features), 3)),
        )

    @staticmethod
    def build_products_section(
        title: str,
        product_count: int = 4,
        category: str = "",
        colors: ColorPalette = None,
    ) -> SectionTemplate:
        """Build a products showcase section."""
        colors = colors or ColorPalette()

        title_module = DiviModuleConfig(
            module_type=DiviModule.TEXT,
            content=f"<h2 style='text-align: center;'>{title}</h2>",
            settings={"text_orientation": "center"},
        )

        shop_module = DiviModuleConfig(
            module_type=DiviModule.SHOP,
            settings={
                "type": "latest",
                "posts_number": str(product_count),
                "columns_number": "4",
                "orderby": "date",
                "include_categories": category,
                "show_pagination": "off",
            },
        )

        cta_module = DiviModuleConfig(
            module_type=DiviModule.BUTTON,
            settings={
                "button_text": "View All Products",
                "button_url": "/shop",
                "button_alignment": "center",
                "custom_button": "on",
                "button_bg_color": colors.primary,
                "button_border_radius": "30px",
            },
        )

        return SectionTemplate(
            section_type=SectionType.PRODUCTS,
            title="Products Section",
            modules=[title_module, shop_module, cta_module],
            background_color=colors.background,
        )

    @staticmethod
    def build_testimonials_section(
        title: str,
        testimonials: List[
            Dict[str, str]
        ],  # [{"quote": "", "author": "", "company": "", "image": ""}]
        colors: ColorPalette = None,
    ) -> SectionTemplate:
        """Build a testimonials section."""
        colors = colors or ColorPalette()

        title_module = DiviModuleConfig(
            module_type=DiviModule.TEXT,
            content=f"<h2 style='text-align: center;'>{title}</h2>",
            settings={"text_orientation": "center"},
        )

        modules = [title_module]

        for testimonial in testimonials:
            test_module = DiviModuleConfig(
                module_type=DiviModule.TESTIMONIAL,
                content=testimonial.get("quote", ""),
                settings={
                    "author": testimonial.get("author", "Customer"),
                    "company_name": testimonial.get("company", ""),
                    "portrait_url": testimonial.get("image", ""),
                    "quote_icon_color": colors.primary,
                    "quote_icon_background_color": colors.background_alt,
                },
                animation="fadeIn",
            )
            modules.append(test_module)

        return SectionTemplate(
            section_type=SectionType.TESTIMONIALS,
            title="Testimonials Section",
            modules=modules,
            background_color=colors.background_alt,
            columns=min(len(testimonials), 3),
        )

    @staticmethod
    def build_cta_section(
        headline: str,
        description: str,
        button_text: str = "Get Started",
        button_url: str = "/shop",
        colors: ColorPalette = None,
    ) -> SectionTemplate:
        """Build a call-to-action section."""
        colors = colors or ColorPalette()

        cta_module = DiviModuleConfig(
            module_type=DiviModule.CTA,
            title=headline,
            content=description,
            settings={
                "title": headline,
                "button_text": button_text,
                "button_url": button_url,
                "use_background_color": "on",
                "background_color": colors.primary,
                "title_font_size": "36px",
                "custom_button": "on",
                "button_bg_color": colors.accent,
                "button_border_radius": "30px",
            },
            animation="fadeInUp",
        )

        return SectionTemplate(
            section_type=SectionType.CTA,
            title="CTA Section",
            modules=[cta_module],
            background_color=colors.primary,
        )

    @staticmethod
    def build_faq_section(
        title: str,
        faqs: List[Dict[str, str]],  # [{"question": "", "answer": ""}]
        colors: ColorPalette = None,
    ) -> SectionTemplate:
        """Build an FAQ section with accordion."""
        colors = colors or ColorPalette()

        title_module = DiviModuleConfig(
            module_type=DiviModule.TEXT,
            content=f"<h2 style='text-align: center;'>{title}</h2>",
            settings={"text_orientation": "center"},
        )

        # Build accordion content
        accordion_items = []
        for faq in faqs:
            accordion_items.append(
                f'[et_pb_accordion_item title="{faq["question"]}"]{faq["answer"]}[/et_pb_accordion_item]'
            )

        accordion_module = DiviModuleConfig(
            module_type=DiviModule.ACCORDION,
            content="\n".join(accordion_items),
            settings={
                "open_toggle_text_color": colors.primary,
                "closed_toggle_text_color": colors.text_dark,
                "icon_color": colors.primary,
            },
        )

        return SectionTemplate(
            section_type=SectionType.FAQ,
            title="FAQ Section",
            modules=[title_module, accordion_module],
            background_color=colors.background,
        )

    @staticmethod
    def build_stats_section(
        stats: List[
            Dict[str, Any]
        ],  # [{"number": 1000, "title": "Happy Customers", "suffix": "+"}]
        colors: ColorPalette = None,
    ) -> SectionTemplate:
        """Build a statistics counter section."""
        colors = colors or ColorPalette()

        modules = []

        for stat in stats:
            counter_module = DiviModuleConfig(
                module_type=DiviModule.COUNTER,
                settings={
                    "title": stat.get("title", ""),
                    "number": str(stat.get("number", 0)),
                    "percent_sign": "off",
                    "counter_suffix": stat.get("suffix", ""),
                    "title_font_size": "18px",
                    "number_font_size": "60px",
                    "number_text_color": colors.primary,
                },
                animation="fadeInUp",
            )
            modules.append(counter_module)

        return SectionTemplate(
            section_type=SectionType.STATS,
            title="Stats Section",
            modules=modules,
            background_color=colors.background_alt,
            columns=len(stats),
        )

    @staticmethod
    def build_newsletter_section(
        headline: str, description: str, colors: ColorPalette = None
    ) -> SectionTemplate:
        """Build a newsletter signup section."""
        colors = colors or ColorPalette()

        text_module = DiviModuleConfig(
            module_type=DiviModule.TEXT,
            content=f"""
                <h2 style='text-align: center; color: #ffffff;'>{headline}</h2>
                <p style='text-align: center; color: #ffffff;'>{description}</p>
            """,
            settings={"text_orientation": "center"},
        )

        # Placeholder for email form - typically added via plugin
        form_module = DiviModuleConfig(
            module_type=DiviModule.CODE,
            content="<!-- Add your email subscription form shortcode here -->",
            settings={},
        )

        return SectionTemplate(
            section_type=SectionType.NEWSLETTER,
            title="Newsletter Section",
            modules=[text_module, form_module],
            background_color=colors.secondary,
        )


# ============================================================================
# RESPONSIVE CHECKER
# ============================================================================


class ResponsiveChecker:
    """Checks and suggests responsive design improvements."""

    @staticmethod
    def check_section(section: SectionTemplate) -> List[Dict[str, Any]]:
        """Check a section for responsive issues."""
        issues = []

        # Check padding
        if section.padding_top > 100:
            issues.append(
                {
                    "type": "warning",
                    "element": "section",
                    "issue": "Large padding may cause issues on mobile",
                    "suggestion": "Consider reducing padding to 60px or less for mobile",
                }
            )

        # Check column count
        if section.columns > 3:
            issues.append(
                {
                    "type": "info",
                    "element": "columns",
                    "issue": f"{section.columns} columns may not display well on tablets",
                    "suggestion": "Consider using 2 columns on tablet and 1 on mobile",
                }
            )

        # Check modules for responsive issues
        for module in section.modules:
            module_issues = ResponsiveChecker.check_module(module)
            issues.extend(module_issues)

        return issues

    @staticmethod
    def check_module(module: DiviModuleConfig) -> List[Dict[str, Any]]:
        """Check a module for responsive issues."""
        issues = []
        settings = module.settings

        # Check font sizes
        for key in ["title_font_size", "content_font_size", "number_font_size"]:
            if key in settings:
                size_str = str(settings[key]).replace("px", "")
                try:
                    size = int(size_str)
                    if size > 48:
                        issues.append(
                            {
                                "type": "warning",
                                "element": module.module_type.value,
                                "issue": f"Font size {size}px may be too large on mobile",
                                "suggestion": "Use responsive font sizing or reduce to max 48px on mobile",
                            }
                        )
                except ValueError:
                    pass

        # Check fixed widths
        if "width" in settings:
            width = str(settings["width"])
            if "px" in width:
                issues.append(
                    {
                        "type": "warning",
                        "element": module.module_type.value,
                        "issue": "Fixed pixel width may cause horizontal scroll on mobile",
                        "suggestion": "Use percentage widths or max-width for responsive design",
                    }
                )

        # Check visibility settings
        if not module.responsive.show_on_phone:
            issues.append(
                {
                    "type": "info",
                    "element": module.module_type.value,
                    "issue": "Module hidden on phone devices",
                    "suggestion": "Ensure important content has a mobile alternative",
                }
            )

        return issues

    @staticmethod
    def generate_responsive_css(module: DiviModuleConfig) -> str:
        """Generate responsive CSS for a module."""
        css_parts = []

        module_selector = f".{module.module_type.value}"

        # Tablet styles
        css_parts.append(
            f"""
@media (max-width: 980px) {{
    {module_selector} {{
        padding-left: 20px;
        padding-right: 20px;
    }}
    {module_selector} h1,
    {module_selector} h2 {{
        font-size: 90%;
    }}
}}
"""
        )

        # Phone styles
        css_parts.append(
            f"""
@media (max-width: 767px) {{
    {module_selector} {{
        padding-left: 15px;
        padding-right: 15px;
    }}
    {module_selector} h1,
    {module_selector} h2 {{
        font-size: 80%;
    }}
}}
"""
        )

        return "\n".join(css_parts)

    @staticmethod
    def get_breakpoint_preview(device: DeviceType) -> Dict[str, int]:
        """Get preview dimensions for a device type."""
        dimensions = {
            DeviceType.DESKTOP: {"width": 1200, "height": 800},
            DeviceType.TABLET: {"width": 768, "height": 1024},
            DeviceType.PHONE: {"width": 375, "height": 667},
        }
        return dimensions.get(device, dimensions[DeviceType.DESKTOP])


# ============================================================================
# A/B TESTING MANAGER
# ============================================================================


class ABTestManager:
    """Manages A/B tests for Divi pages."""

    def __init__(self):
        self.tests: Dict[str, ABTest] = {}

    def create_test(
        self,
        name: str,
        page_type: PageType,
        section_type: SectionType,
        description: str = "",
    ) -> ABTest:
        """Create a new A/B test."""
        test_id = f"test_{len(self.tests) + 1}"

        test = ABTest(
            test_id=test_id,
            name=name,
            description=description,
            page_type=page_type,
            section_type=section_type,
        )

        self.tests[test_id] = test
        return test

    def add_variant(
        self, test_id: str, name: str, section: SectionTemplate, description: str = ""
    ) -> ABTestVariant:
        """Add a variant to an existing test."""
        test = self.tests.get(test_id)
        if not test:
            raise ValueError(f"Test {test_id} not found")

        variant = ABTestVariant(
            variant_id=f"{test_id}_v{len(test.variants) + 1}",
            name=name,
            description=description,
            section=section,
        )

        test.add_variant(variant)
        return variant

    def generate_hero_ab_test(
        self,
        headline_a: str,
        headline_b: str,
        subheadline: str,
        colors: ColorPalette = None,
    ) -> ABTest:
        """Generate an A/B test for hero headlines."""
        test = self.create_test(
            name="Hero Headline Test",
            page_type=PageType.HOME,
            section_type=SectionType.HERO,
            description="Testing different headline variations",
        )

        # Variant A
        section_a = SectionTemplateBuilder.build_hero_section(
            headline=headline_a,
            subheadline=subheadline,
            colors=colors,
        )
        self.add_variant(test.test_id, "Control", section_a, "Original headline")

        # Variant B
        section_b = SectionTemplateBuilder.build_hero_section(
            headline=headline_b,
            subheadline=subheadline,
            colors=colors,
        )
        self.add_variant(
            test.test_id, "Challenger", section_b, "New headline variation"
        )

        return test

    def generate_cta_ab_test(
        self,
        button_texts: List[str],
        headline: str,
        description: str,
        colors: ColorPalette = None,
    ) -> ABTest:
        """Generate an A/B test for CTA button text."""
        test = self.create_test(
            name="CTA Button Test",
            page_type=PageType.LANDING,
            section_type=SectionType.CTA,
            description="Testing different CTA button text variations",
        )

        for i, button_text in enumerate(button_texts):
            section = SectionTemplateBuilder.build_cta_section(
                headline=headline,
                description=description,
                button_text=button_text,
                colors=colors,
            )
            name = "Control" if i == 0 else f"Variant {chr(65 + i)}"
            self.add_variant(test.test_id, name, section, f"Button: {button_text}")

        return test

    def get_variant_code(self, test_id: str) -> str:
        """Generate JavaScript code for A/B test variant selection."""
        test = self.tests.get(test_id)
        if not test:
            return ""

        variants_json = json.dumps([v.to_config() for v in test.variants])

        return f"""
<script>
(function() {{
    var testId = '{test_id}';
    var variants = {variants_json};

    // Get or create visitor ID
    var visitorId = localStorage.getItem('ab_visitor') ||
                    Math.random().toString(36).substring(2);
    localStorage.setItem('ab_visitor', visitorId);

    // Deterministic variant selection based on visitor ID
    var hash = 0;
    for (var i = 0; i < visitorId.length; i++) {{
        hash = ((hash << 5) - hash) + visitorId.charCodeAt(i);
        hash |= 0;
    }}
    var bucket = Math.abs(hash) % 100 / 100;

    // Select variant based on weights
    var cumulative = 0;
    var selectedVariant = variants[0];
    for (var i = 0; i < variants.length; i++) {{
        cumulative += variants[i].weight;
        if (bucket <= cumulative) {{
            selectedVariant = variants[i];
            break;
        }}
    }}

    // Store selected variant
    localStorage.setItem(testId + '_variant', selectedVariant.id);

    // Apply variant (show/hide sections)
    document.addEventListener('DOMContentLoaded', function() {{
        variants.forEach(function(v) {{
            var el = document.querySelector('[data-variant="' + v.id + '"]');
            if (el) {{
                el.style.display = v.id === selectedVariant.id ? 'block' : 'none';
            }}
        }});
    }});
}})();
</script>
"""


# ============================================================================
# PAGE SPEED OPTIMIZER
# ============================================================================


class PageSpeedOptimizer:
    """Analyzes and suggests page speed optimizations."""

    @staticmethod
    def analyze_layout(layout: PageLayout) -> List[PageSpeedIssue]:
        """Analyze a layout for speed issues."""
        issues = []

        # Check number of sections
        if len(layout.sections) > 10:
            issues.append(
                PageSpeedIssue(
                    severity="warning",
                    category="layout",
                    title="High section count",
                    description=f"Page has {len(layout.sections)} sections which may impact load time",
                    recommendation="Consider combining related sections or lazy loading below-fold content",
                    impact="medium",
                    divi_specific=True,
                )
            )

        # Count modules
        total_modules = sum(len(s.modules) for s in layout.sections)
        if total_modules > 30:
            issues.append(
                PageSpeedIssue(
                    severity="warning",
                    category="layout",
                    title="High module count",
                    description=f"Page uses {total_modules} modules which increases DOM complexity",
                    recommendation="Simplify design or use Divi's Performance features to defer module loading",
                    impact="high",
                    divi_specific=True,
                )
            )

        # Check for heavy modules
        heavy_modules = [
            DiviModule.GALLERY,
            DiviModule.VIDEO_SLIDER,
            DiviModule.FULLWIDTH_SLIDER,
            DiviModule.MAP,
        ]

        for section in layout.sections:
            for module in section.modules:
                if module.module_type in heavy_modules:
                    issues.append(
                        PageSpeedIssue(
                            severity="info",
                            category="modules",
                            title=f"Resource-heavy module: {module.module_type.value}",
                            description=f"The {module.module_type.name} module requires additional resources",
                            recommendation="Consider lazy loading or reducing items in this module",
                            impact="medium",
                            divi_specific=True,
                        )
                    )

        # Check background images
        for section in layout.sections:
            if section.background_image:
                issues.append(
                    PageSpeedIssue(
                        severity="info",
                        category="images",
                        title="Background image detected",
                        description=f"Section '{section.title}' uses a background image",
                        recommendation="Ensure image is optimized (WebP format, compressed, appropriately sized)",
                        impact="medium",
                        divi_specific=False,
                    )
                )

        # Check custom CSS
        if layout.custom_css and len(layout.custom_css) > 5000:
            issues.append(
                PageSpeedIssue(
                    severity="warning",
                    category="css",
                    title="Large custom CSS",
                    description=f"Custom CSS is {len(layout.custom_css)} characters",
                    recommendation="Consider moving styles to a separate stylesheet for caching",
                    impact="low",
                    divi_specific=False,
                )
            )

        return issues

    @staticmethod
    def get_divi_performance_settings() -> Dict[str, Any]:
        """Get recommended Divi performance settings."""
        return {
            "et_enable_dynamic_css": "on",
            "et_enable_dynamic_icons": "on",
            "et_critical_css": "on",
            "et_defer_all_js": "on",
            "et_defer_google_maps": "on",
            "et_improve_google_fonts": "on",
            "et_limit_google_fonts_support_for_legacy": "on",
            "et_disable_emojis": "on",
            "et_minify_combine_js": "on",
            "et_minify_combine_css": "on",
        }

    @staticmethod
    def get_image_optimization_tips() -> List[str]:
        """Get image optimization tips for Divi."""
        return [
            "Use WebP format for all images when browser support allows",
            "Set featured images to max 1200px width for full-width layouts",
            "Use Divi's built-in responsive images or a plugin like ShortPixel",
            "Enable lazy loading in Divi Theme Options > Performance",
            "Use srcset for responsive images in custom code",
            "Compress images before upload - aim for < 100KB for most images",
            "Use SVG for icons and simple graphics",
            "Consider using a CDN for image delivery",
            "Set proper image dimensions in Divi to avoid layout shifts",
            "Use placeholder/blur-up technique for hero images",
        ]

    @staticmethod
    def get_caching_recommendations() -> Dict[str, str]:
        """Get caching recommendations for Divi sites."""
        return {
            "WP Super Cache": "Free, simple setup, good for most sites",
            "W3 Total Cache": "Powerful but complex, good for advanced users",
            "WP Rocket": "Premium, best compatibility with Divi",
            "LiteSpeed Cache": "Best for LiteSpeed hosting",
            "SG Optimizer": "Best for SiteGround hosting",
            "Cloudflare": "Free CDN + caching, excellent for global audience",
        }

    @staticmethod
    def generate_htaccess_rules() -> str:
        """Generate .htaccess rules for performance."""
        return """
# Enable compression
<IfModule mod_deflate.c>
    AddOutputFilterByType DEFLATE text/html
    AddOutputFilterByType DEFLATE text/css
    AddOutputFilterByType DEFLATE text/javascript
    AddOutputFilterByType DEFLATE application/javascript
    AddOutputFilterByType DEFLATE application/x-javascript
    AddOutputFilterByType DEFLATE application/json
    AddOutputFilterByType DEFLATE application/xml
    AddOutputFilterByType DEFLATE image/svg+xml
</IfModule>

# Browser caching
<IfModule mod_expires.c>
    ExpiresActive On
    ExpiresByType image/jpg "access plus 1 year"
    ExpiresByType image/jpeg "access plus 1 year"
    ExpiresByType image/gif "access plus 1 year"
    ExpiresByType image/png "access plus 1 year"
    ExpiresByType image/webp "access plus 1 year"
    ExpiresByType image/svg+xml "access plus 1 year"
    ExpiresByType text/css "access plus 1 month"
    ExpiresByType application/javascript "access plus 1 month"
    ExpiresByType application/x-javascript "access plus 1 month"
</IfModule>

# Keep-Alive
<IfModule mod_headers.c>
    Header set Connection keep-alive
</IfModule>
"""


# ============================================================================
# LAYOUT RECOMMENDATIONS
# ============================================================================


class LayoutRecommender:
    """Recommends layouts based on page type and content."""

    @staticmethod
    def get_recommended_sections(page_type: PageType) -> List[SectionType]:
        """Get recommended sections for a page type."""
        recommendations = {
            PageType.HOME: [
                SectionType.HERO,
                SectionType.FEATURES,
                SectionType.PRODUCTS,
                SectionType.TESTIMONIALS,
                SectionType.CTA,
                SectionType.NEWSLETTER,
            ],
            PageType.PRODUCT: [
                SectionType.GALLERY,
                SectionType.FEATURES,
                SectionType.TESTIMONIALS,
                SectionType.FAQ,
                SectionType.CTA,
            ],
            PageType.CATEGORY: [
                SectionType.HERO,
                SectionType.PRODUCTS,
                SectionType.FAQ,
            ],
            PageType.LANDING: [
                SectionType.HERO,
                SectionType.FEATURES,
                SectionType.STATS,
                SectionType.TESTIMONIALS,
                SectionType.PRICING,
                SectionType.FAQ,
                SectionType.CTA,
            ],
            PageType.ABOUT: [
                SectionType.HERO,
                SectionType.FEATURES,
                SectionType.TEAM,
                SectionType.STATS,
                SectionType.TESTIMONIALS,
            ],
            PageType.CONTACT: [
                SectionType.HERO,
                SectionType.CONTACT,
                SectionType.FAQ,
            ],
            PageType.FAQ: [
                SectionType.HERO,
                SectionType.FAQ,
                SectionType.CTA,
            ],
            PageType.DEALS: [
                SectionType.HERO,
                SectionType.PRODUCTS,
                SectionType.CTA,
                SectionType.NEWSLETTER,
            ],
        }
        return recommendations.get(page_type, [SectionType.HERO, SectionType.CTA])

    @staticmethod
    def get_section_order_tips() -> List[str]:
        """Get tips for section ordering."""
        return [
            "Hero section should always be first - it sets the page tone",
            "Place most important content (features/products) above the fold",
            "Social proof (testimonials/stats) works best after showing value",
            "CTA sections should appear after building value, not immediately",
            "FAQ sections help address objections before final CTA",
            "Newsletter signup works well as a secondary conversion point",
            "Footer should contain navigation, contact info, and trust signals",
        ]

    @staticmethod
    def suggest_column_layouts(section_type: SectionType) -> List[str]:
        """Suggest column layouts for a section type."""
        layouts = {
            SectionType.HERO: ["4_4"],  # Full width
            SectionType.FEATURES: ["1_3,1_3,1_3", "1_4,1_4,1_4,1_4", "1_2,1_2"],
            SectionType.PRODUCTS: ["1_4,1_4,1_4,1_4", "1_3,1_3,1_3"],
            SectionType.TESTIMONIALS: ["1_3,1_3,1_3", "1_2,1_2", "4_4"],
            SectionType.CTA: ["4_4", "2_3,1_3"],
            SectionType.FAQ: ["4_4", "1_2,1_2"],
            SectionType.STATS: ["1_4,1_4,1_4,1_4", "1_3,1_3,1_3"],
            SectionType.CONTACT: ["1_2,1_2", "2_3,1_3"],
            SectionType.PRICING: ["1_3,1_3,1_3", "1_4,1_4,1_4,1_4"],
        }
        return layouts.get(section_type, ["4_4"])


# ============================================================================
# MAIN DIVI PAGE BUILDER AGENT
# ============================================================================


class DiviPageBuilderAgent:
    """Main Divi page builder agent."""

    def __init__(self, demo_mode: bool = True):
        self.demo_mode = demo_mode
        self.color_manager = ColorSchemeManager()
        self.ab_manager = ABTestManager()
        self.speed_optimizer = PageSpeedOptimizer()
        self.layout_recommender = LayoutRecommender()
        self.section_builder = SectionTemplateBuilder()
        self.module_suggester = ModuleSuggester()
        self.responsive_checker = ResponsiveChecker()

    def build_page(
        self,
        page_type: PageType,
        title: str,
        color_scheme: ColorSchemeType = ColorSchemeType.TECH,
        product_name: str = "",
    ) -> PageLayout:
        """Build a complete page layout."""
        colors = self.color_manager.get_scheme(color_scheme)
        typography = Typography()

        # Get recommended sections
        section_types = self.layout_recommender.get_recommended_sections(page_type)

        # Build sections
        sections = []

        for section_type in section_types:
            section = self._build_section(
                section_type,
                page_type,
                colors,
                title,
                product_name,
            )
            if section:
                sections.append(section)

        layout = PageLayout(
            page_type=page_type,
            title=title,
            sections=sections,
            colors=colors,
            typography=typography,
        )

        return layout

    def _build_section(
        self,
        section_type: SectionType,
        page_type: PageType,
        colors: ColorPalette,
        page_title: str,
        product_name: str = "",
    ) -> Optional[SectionTemplate]:
        """Build a specific section."""

        if section_type == SectionType.HERO:
            return self.section_builder.build_hero_section(
                headline=(
                    f"Discover the Best {product_name or 'Electronics'}"
                    if page_type == PageType.HOME
                    else f"{product_name or page_title}"
                ),
                subheadline="Premium quality electronics at unbeatable prices",
                cta_text="Shop Now" if page_type == PageType.HOME else "Learn More",
                colors=colors,
            )

        elif section_type == SectionType.FEATURES:
            features = [
                {
                    "title": "Fast Shipping",
                    "description": "Free next-day delivery on orders over $50",
                    "icon": "%%47%%",  # Truck icon
                },
                {
                    "title": "Expert Support",
                    "description": "24/7 customer service from tech experts",
                    "icon": "%%51%%",  # Phone icon
                },
                {
                    "title": "Best Prices",
                    "description": "Price match guarantee on all products",
                    "icon": "%%87%%",  # Tag icon
                },
            ]
            return self.section_builder.build_features_section(
                title="Why Shop With Us",
                features=features,
                colors=colors,
            )

        elif section_type == SectionType.PRODUCTS:
            return self.section_builder.build_products_section(
                title=(
                    "Featured Products"
                    if page_type == PageType.HOME
                    else "Related Products"
                ),
                product_count=4,
                colors=colors,
            )

        elif section_type == SectionType.TESTIMONIALS:
            testimonials = [
                {
                    "quote": "Amazing selection and fast delivery. My go-to store for all electronics!",
                    "author": "Sarah M.",
                    "company": "Verified Buyer",
                },
                {
                    "quote": "The customer service team helped me find exactly what I needed.",
                    "author": "James L.",
                    "company": "Verified Buyer",
                },
                {
                    "quote": "Best prices online and the products are always top quality.",
                    "author": "Emily R.",
                    "company": "Verified Buyer",
                },
            ]
            return self.section_builder.build_testimonials_section(
                title="What Our Customers Say",
                testimonials=testimonials,
                colors=colors,
            )

        elif section_type == SectionType.CTA:
            return self.section_builder.build_cta_section(
                headline="Ready to Upgrade Your Tech?",
                description="Join thousands of happy customers. Shop now and get 10% off your first order!",
                button_text="Shop Now",
                colors=colors,
            )

        elif section_type == SectionType.FAQ:
            faqs = [
                {
                    "question": "What is your return policy?",
                    "answer": "We offer a 30-day hassle-free return policy on all products.",
                },
                {
                    "question": "Do you offer international shipping?",
                    "answer": "Yes! We ship to over 50 countries worldwide.",
                },
                {
                    "question": "How can I track my order?",
                    "answer": "Once shipped, you'll receive a tracking number via email.",
                },
            ]
            return self.section_builder.build_faq_section(
                title="Frequently Asked Questions",
                faqs=faqs,
                colors=colors,
            )

        elif section_type == SectionType.STATS:
            stats = [
                {"number": 50000, "title": "Happy Customers", "suffix": "+"},
                {"number": 10000, "title": "Products", "suffix": "+"},
                {"number": 99, "title": "Satisfaction Rate", "suffix": "%"},
                {"number": 24, "title": "Support Hours", "suffix": "/7"},
            ]
            return self.section_builder.build_stats_section(
                stats=stats,
                colors=colors,
            )

        elif section_type == SectionType.NEWSLETTER:
            return self.section_builder.build_newsletter_section(
                headline="Stay Updated",
                description="Subscribe to get exclusive deals and product announcements",
                colors=colors,
            )

        return None

    def analyze_page(self, layout: PageLayout) -> Dict[str, Any]:
        """Analyze a page layout and provide recommendations."""
        analysis = {
            "sections": len(layout.sections),
            "total_modules": sum(len(s.modules) for s in layout.sections),
            "speed_issues": [],
            "responsive_issues": [],
            "recommendations": [],
        }

        # Speed analysis
        speed_issues = self.speed_optimizer.analyze_layout(layout)
        analysis["speed_issues"] = [asdict(issue) for issue in speed_issues]

        # Responsive analysis
        for section in layout.sections:
            issues = self.responsive_checker.check_section(section)
            analysis["responsive_issues"].extend(issues)

        # General recommendations
        if len(layout.sections) < 3:
            analysis["recommendations"].append(
                "Consider adding more sections to engage visitors"
            )

        has_cta = any(s.section_type == SectionType.CTA for s in layout.sections)
        if not has_cta:
            analysis["recommendations"].append(
                "Add a call-to-action section to drive conversions"
            )

        has_testimonials = any(
            s.section_type == SectionType.TESTIMONIALS for s in layout.sections
        )
        if not has_testimonials:
            analysis["recommendations"].append(
                "Consider adding testimonials for social proof"
            )

        return analysis

    def demo_run(self):
        """Run demonstration of page builder features."""
        print("\n" + "=" * 70)
        print("  Divi Page Builder Assistant - Demo Mode")
        print("  Electronics Store Page Builder")
        print("=" * 70)

        # Demo 1: Color scheme
        print("\n🎨 Color Schemes:")
        for scheme_type in [
            ColorSchemeType.TECH,
            ColorSchemeType.MODERN,
            ColorSchemeType.DARK,
        ]:
            palette = self.color_manager.get_scheme(scheme_type)
            print(f"   {scheme_type.value}:")
            print(f"     Primary: {palette.primary}, Secondary: {palette.secondary}")

        # Demo 2: Build a home page
        print("\n🏠 Building Home Page...")
        home_layout = self.build_page(
            page_type=PageType.HOME,
            title="Electronics Store Home",
            color_scheme=ColorSchemeType.TECH,
        )
        print(f"   Created {len(home_layout.sections)} sections:")
        for section in home_layout.sections:
            module_count = len(section.modules)
            print(f"     - {section.section_type.value}: {module_count} modules")

        # Demo 3: Module suggestions
        print("\n🧩 Module Suggestions for Product Page:")
        modules = self.module_suggester.suggest_for_page(PageType.PRODUCT)
        for module in modules[:5]:
            print(f"   - {module.value}")

        # Demo 4: Section recommendations
        print("\n📐 Recommended Sections for Landing Page:")
        sections = self.layout_recommender.get_recommended_sections(PageType.LANDING)
        for section in sections:
            print(f"   - {section.value}")

        # Demo 5: A/B Testing
        print("\n🔬 Creating A/B Test:")
        test = self.ab_manager.generate_hero_ab_test(
            headline_a="Discover Premium Electronics",
            headline_b="Save Big on Top Tech Brands",
            subheadline="Shop the best deals on laptops, phones, and more",
        )
        print(f"   Test: {test.name}")
        for variant in test.variants:
            print(f"     - {variant.name}: {variant.weight*100:.0f}% traffic")

        # Demo 6: Page Speed Analysis
        print("\n⚡ Page Speed Analysis:")
        speed_issues = self.speed_optimizer.analyze_layout(home_layout)
        for issue in speed_issues[:3]:
            print(f"   [{issue.severity.upper()}] {issue.title}")
            print(f"      {issue.recommendation}")

        # Demo 7: Responsive Check
        print("\n📱 Responsive Design Check:")
        for section in home_layout.sections[:2]:
            issues = self.responsive_checker.check_section(section)
            if issues:
                print(f"   {section.section_type.value}:")
                for issue in issues[:2]:
                    print(f"     - {issue['issue']}")

        # Demo 8: Typography
        print("\n✏️  Typography Settings:")
        typo = home_layout.typography
        print(f"   Headings: {typo.heading_font} ({typo.heading_weight})")
        print(f"   Body: {typo.body_font} ({typo.body_weight})")
        print(
            f"   Scale: H1={typo.get_size(1)}px, H2={typo.get_size(2)}px, H3={typo.get_size(3)}px"
        )

        # Demo 9: Performance settings
        print("\n🚀 Recommended Divi Performance Settings:")
        settings = self.speed_optimizer.get_divi_performance_settings()
        for key, value in list(settings.items())[:5]:
            setting_name = key.replace("et_", "").replace("_", " ").title()
            print(f"   {setting_name}: {value}")

        # Demo 10: Layout preview
        print("\n📄 Generated Divi Layout Preview:")
        layout_code = home_layout.to_divi_layout()
        lines = layout_code.strip().split("\n")
        preview_lines = lines[:10] if len(lines) > 10 else lines
        for line in preview_lines:
            print(f"   {line[:60]}...")
        if len(lines) > 10:
            print(f"   ... and {len(lines) - 10} more lines")

        print("\n" + "=" * 70)
        print("  Demo Complete! Ready to build your electronics store.")
        print("=" * 70 + "\n")


# ============================================================================
# CLI INTERFACE
# ============================================================================


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Divi Page Builder Assistant for Electronics Store"
    )
    parser.add_argument("--demo", action="store_true", help="Run in demo mode")
    parser.add_argument(
        "--page",
        type=str,
        choices=[pt.value for pt in PageType],
        help="Page type to build",
    )
    parser.add_argument("--product", type=str, help="Product name for product pages")
    parser.add_argument(
        "--scheme",
        type=str,
        choices=[cs.value for cs in ColorSchemeType],
        default="tech",
        help="Color scheme to use",
    )
    parser.add_argument(
        "--analyze", action="store_true", help="Analyze page and show recommendations"
    )
    parser.add_argument("--export", type=str, help="Export layout to file")

    args = parser.parse_args()

    agent = DiviPageBuilderAgent(demo_mode=args.demo)

    if args.demo:
        agent.demo_run()
    elif args.page:
        page_type = PageType(args.page)
        color_scheme = ColorSchemeType(args.scheme)

        layout = agent.build_page(
            page_type=page_type,
            title=f"{args.page.title()} Page",
            color_scheme=color_scheme,
            product_name=args.product or "",
        )

        print(f"\nBuilt {page_type.value} page with {len(layout.sections)} sections")

        if args.analyze:
            analysis = agent.analyze_page(layout)
            print("\nAnalysis:")
            print(f"  Sections: {analysis['sections']}")
            print(f"  Modules: {analysis['total_modules']}")
            print(f"  Speed Issues: {len(analysis['speed_issues'])}")
            print(f"  Responsive Issues: {len(analysis['responsive_issues'])}")

            if analysis["recommendations"]:
                print("\nRecommendations:")
                for rec in analysis["recommendations"]:
                    print(f"  - {rec}")

        if args.export:
            with open(args.export, "w") as f:
                f.write(layout.to_divi_layout())
            print(f"\nExported layout to {args.export}")
    else:
        agent.demo_run()


if __name__ == "__main__":
    main()
