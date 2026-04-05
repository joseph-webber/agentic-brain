#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Divi E-Commerce Theme Assistant - Agentic Brain Example #78

A comprehensive assistant for building WooCommerce stores with Divi:
- WooCommerce + Divi integration patterns
- Product page layouts
- Shop page customization
- Cart/checkout styling
- Product category templates
- Sale/promotion banners
- Cross-sell/upsell sections
- Mobile commerce optimization

Perfect for building an electronics store with Divi and WooCommerce.

Usage:
    python 78_divi_ecommerce_theme.py --demo
    python 78_divi_ecommerce_theme.py --layout product --category smartphones
"""

import asyncio
import json
import logging
import os
import random
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================


class ProductLayoutType(Enum):
    """Product page layout types."""

    STANDARD = "standard"
    GALLERY_LEFT = "gallery_left"
    GALLERY_RIGHT = "gallery_right"
    FULL_WIDTH = "full_width"
    CENTERED = "centered"
    SPLIT_SCREEN = "split_screen"


class ShopLayoutType(Enum):
    """Shop page layout types."""

    GRID = "grid"
    LIST = "list"
    MASONRY = "masonry"
    FEATURED_FIRST = "featured_first"
    CATEGORY_BOXES = "category_boxes"


class BannerType(Enum):
    """Promotional banner types."""

    HERO = "hero"
    STRIP = "strip"
    COUNTDOWN = "countdown"
    FLOATING = "floating"
    SIDEBAR = "sidebar"
    POPUP = "popup"


class DeviceType(Enum):
    """Device types for responsive design."""

    DESKTOP = "desktop"
    TABLET = "tablet"
    PHONE = "phone"


class CartStyle(Enum):
    """Shopping cart styles."""

    CLASSIC = "classic"
    MODERN = "modern"
    MINIMAL = "minimal"
    SIDEBAR = "sidebar"
    FLOATING = "floating"


class CheckoutStyle(Enum):
    """Checkout page styles."""

    SINGLE_PAGE = "single_page"
    MULTI_STEP = "multi_step"
    ONE_COLUMN = "one_column"
    TWO_COLUMN = "two_column"


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class ColorScheme:
    """E-commerce color scheme."""

    primary: str = "#2563eb"  # Trust blue
    secondary: str = "#10b981"  # Success green
    accent: str = "#f59e0b"  # Warning amber
    sale: str = "#ef4444"  # Sale red
    text_dark: str = "#1f2937"
    text_light: str = "#6b7280"
    background: str = "#ffffff"
    surface: str = "#f3f4f6"
    border: str = "#e5e7eb"

    def to_css_variables(self) -> str:
        """Generate CSS custom properties."""
        return f"""
:root {{
    --ec-primary: {self.primary};
    --ec-secondary: {self.secondary};
    --ec-accent: {self.accent};
    --ec-sale: {self.sale};
    --ec-text-dark: {self.text_dark};
    --ec-text-light: {self.text_light};
    --ec-background: {self.background};
    --ec-surface: {self.surface};
    --ec-border: {self.border};
}}
"""


@dataclass
class ProductData:
    """Product data structure."""

    id: int
    name: str
    slug: str
    price: float
    regular_price: float
    sale_price: Optional[float] = None
    description: str = ""
    short_description: str = ""
    sku: str = ""
    stock_status: str = "instock"
    stock_quantity: int = 0
    categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    gallery_images: List[str] = field(default_factory=list)
    rating: float = 0.0
    review_count: int = 0
    featured: bool = False
    on_sale: bool = False
    attributes: Dict[str, List[str]] = field(default_factory=dict)

    def get_discount_percentage(self) -> int:
        """Calculate discount percentage."""
        if self.sale_price and self.regular_price > 0:
            return int((1 - self.sale_price / self.regular_price) * 100)
        return 0

    def get_price_html(self) -> str:
        """Generate price HTML."""
        if self.on_sale and self.sale_price:
            return f"""
<del class="original-price">${self.regular_price:.2f}</del>
<ins class="sale-price">${self.sale_price:.2f}</ins>
<span class="discount-badge">-{self.get_discount_percentage()}%</span>
"""
        return f'<span class="price">${self.price:.2f}</span>'


@dataclass
class CategoryData:
    """Category data structure."""

    id: int
    name: str
    slug: str
    description: str = ""
    parent_id: Optional[int] = None
    image: str = ""
    product_count: int = 0
    display_type: str = "default"  # default, products, subcategories, both


@dataclass
class PromotionBanner:
    """Promotion banner configuration."""

    banner_type: BannerType
    headline: str
    subheadline: str = ""
    button_text: str = "Shop Now"
    button_url: str = "/shop"
    background_image: str = ""
    background_color: str = ""
    text_color: str = "#ffffff"
    countdown_end: Optional[datetime] = None
    show_on_mobile: bool = True
    position: str = "top"  # top, bottom, left, right
    discount_code: str = ""

    def to_divi_module(self) -> str:
        """Generate Divi shortcode for banner."""
        if self.banner_type == BannerType.HERO:
            return self._generate_hero_banner()
        elif self.banner_type == BannerType.STRIP:
            return self._generate_strip_banner()
        elif self.banner_type == BannerType.COUNTDOWN:
            return self._generate_countdown_banner()
        else:
            return self._generate_default_banner()

    def _generate_hero_banner(self) -> str:
        """Generate hero banner shortcode."""
        return f"""
[et_pb_fullwidth_header
    title="{self.headline}"
    subhead="{self.subheadline}"
    button_one_text="{self.button_text}"
    button_one_url="{self.button_url}"
    background_image="{self.background_image}"
    background_overlay_color="rgba(0,0,0,0.5)"
    title_font_size="60px"
    title_text_color="{self.text_color}"
    content_font_size="20px"
    button_one_bg_color="#ef4444"
    button_one_border_radius="30px"
    custom_padding="120px||120px|"
]
[/et_pb_fullwidth_header]
"""

    def _generate_strip_banner(self) -> str:
        """Generate strip banner shortcode."""
        return f"""
[et_pb_section background_color="#ef4444" custom_padding="15px||15px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_text text_orientation="center" text_text_color="#ffffff"]
                <p style="margin: 0; font-weight: bold;">
                    {self.headline}
                    <a href="{self.button_url}" style="color: #ffffff; text-decoration: underline;">
                        {self.button_text}
                    </a>
                </p>
            [/et_pb_text]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

    def _generate_countdown_banner(self) -> str:
        """Generate countdown banner shortcode."""
        end_date = self.countdown_end or (datetime.now() + timedelta(days=7))
        return f"""
[et_pb_section background_color="#1f2937" custom_padding="40px||40px|"]
    [et_pb_row]
        [et_pb_column type="1_2"]
            [et_pb_text text_text_color="#ffffff"]
                <h2 style="margin-bottom: 10px;">{self.headline}</h2>
                <p>{self.subheadline}</p>
            [/et_pb_text]
        [/et_pb_column]
        [et_pb_column type="1_2"]
            [et_pb_countdown_timer
                title="Sale Ends In"
                date_time="{end_date.strftime('%Y-%m-%d %H:%M')}"
                background_color="transparent"
            /]
            [et_pb_button
                button_text="{self.button_text}"
                button_url="{self.button_url}"
                button_alignment="center"
                custom_button="on"
                button_bg_color="#ef4444"
            /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

    def _generate_default_banner(self) -> str:
        """Generate default banner shortcode."""
        return f"""
[et_pb_cta
    title="{self.headline}"
    button_text="{self.button_text}"
    button_url="{self.button_url}"
    background_color="{self.background_color or '#2563eb'}"
]
    {self.subheadline}
[/et_pb_cta]
"""


@dataclass
class CrossSellConfig:
    """Cross-sell/upsell configuration."""

    title: str = "You May Also Like"
    type: str = "cross_sell"  # cross_sell, upsell, related
    product_count: int = 4
    columns: int = 4
    show_rating: bool = True
    show_price: bool = True
    orderby: str = "rand"  # rand, date, price, popularity

    def to_divi_module(self) -> str:
        """Generate Divi shortcode for cross-sell section."""
        return f"""
[et_pb_section custom_padding="60px||60px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_text text_orientation="center"]
                <h2>{self.title}</h2>
            [/et_pb_text]
            [et_pb_shop
                type="{self.type}"
                posts_number="{self.product_count}"
                columns_number="{self.columns}"
                orderby="{self.orderby}"
                show_pagination="off"
            /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""


@dataclass
class MobileOptimization:
    """Mobile commerce optimization settings."""

    sticky_add_to_cart: bool = True
    simplified_navigation: bool = True
    touch_friendly_gallery: bool = True
    quick_view_enabled: bool = True
    mobile_filters_sidebar: bool = True
    compress_product_titles: bool = True
    stack_product_columns: bool = True
    min_button_height: int = 48  # pixels, for touch targets

    def to_css(self) -> str:
        """Generate mobile-specific CSS."""
        css = """
/* Mobile Commerce Optimization */
@media (max-width: 767px) {
"""
        if self.sticky_add_to_cart:
            css += """
    .woocommerce-product-details__short-description + form.cart {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: #ffffff;
        padding: 15px;
        box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
        z-index: 1000;
    }
"""

        if self.compress_product_titles:
            css += """
    .woocommerce ul.products li.product .woocommerce-loop-product__title {
        font-size: 14px;
        line-height: 1.3;
        max-height: 2.6em;
        overflow: hidden;
    }
"""

        if self.stack_product_columns:
            css += """
    .woocommerce ul.products {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 15px;
    }
    .woocommerce ul.products li.product {
        width: 100% !important;
        margin: 0 !important;
    }
"""

        css += f"""
    .woocommerce .button,
    .woocommerce button.button,
    .woocommerce a.button {{
        min-height: {self.min_button_height}px;
        display: flex;
        align-items: center;
        justify-content: center;
    }}
"""

        css += "}\n"
        return css


# ============================================================================
# PRODUCT PAGE LAYOUTS
# ============================================================================


class ProductPageBuilder:
    """Builds product page layouts."""

    @staticmethod
    def get_layout_template(
        layout_type: ProductLayoutType, colors: ColorScheme = None
    ) -> str:
        """Get Divi layout template for product page."""
        colors = colors or ColorScheme()

        templates = {
            ProductLayoutType.STANDARD: ProductPageBuilder._standard_layout,
            ProductLayoutType.GALLERY_LEFT: ProductPageBuilder._gallery_left_layout,
            ProductLayoutType.GALLERY_RIGHT: ProductPageBuilder._gallery_right_layout,
            ProductLayoutType.FULL_WIDTH: ProductPageBuilder._full_width_layout,
            ProductLayoutType.CENTERED: ProductPageBuilder._centered_layout,
            ProductLayoutType.SPLIT_SCREEN: ProductPageBuilder._split_screen_layout,
        }

        builder = templates.get(layout_type, ProductPageBuilder._standard_layout)
        return builder(colors)

    @staticmethod
    def _standard_layout(colors: ColorScheme) -> str:
        """Standard product layout - gallery left, details right."""
        return """
[et_pb_section fb_built="1" custom_padding="60px||60px|"]
    [et_pb_row column_structure="1_2,1_2"]
        <!-- Product Gallery -->
        [et_pb_column type="1_2"]
            [et_pb_wc_images product="current" /]
        [/et_pb_column]

        <!-- Product Details -->
        [et_pb_column type="1_2"]
            [et_pb_wc_breadcrumb product="current" /]
            [et_pb_wc_title product="current" header_level="h1" /]
            [et_pb_wc_rating product="current" /]
            [et_pb_wc_price product="current" /]
            [et_pb_wc_description product="current" /]
            [et_pb_wc_add_to_cart product="current" /]
            [et_pb_wc_meta product="current" /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]

<!-- Product Tabs -->
[et_pb_section custom_padding="40px||60px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_wc_tabs product="current" /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]

<!-- Related Products -->
[et_pb_section background_color="#f3f4f6" custom_padding="60px||60px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_wc_related_products product="current" columns_number="4" /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]

<!-- Upsells -->
[et_pb_section custom_padding="60px||60px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_wc_upsells product="current" columns_number="4" /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

    @staticmethod
    def _gallery_left_layout(colors: ColorScheme) -> str:
        """Gallery with thumbnails on the left."""
        return """
[et_pb_section custom_padding="60px||60px|"]
    [et_pb_row column_structure="1_2,1_2"]
        [et_pb_column type="1_2"]
            [et_pb_wc_gallery product="current" orientation="left" /]
        [/et_pb_column]
        [et_pb_column type="1_2"]
            [et_pb_wc_breadcrumb product="current" /]
            [et_pb_wc_title product="current" /]
            [et_pb_wc_rating product="current" /]
            [et_pb_wc_price product="current" /]

            <!-- Trust Badges -->
            [et_pb_blurb title="Free Shipping" use_icon="on" font_icon="%%47%%" icon_color="#10b981" icon_placement="left"]
                On orders over $50
            [/et_pb_blurb]
            [et_pb_blurb title="Secure Payment" use_icon="on" font_icon="%%96%%" icon_color="#10b981" icon_placement="left"]
                256-bit SSL encryption
            [/et_pb_blurb]

            [et_pb_wc_add_to_cart product="current" /]
            [et_pb_wc_meta product="current" /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]

[et_pb_section custom_padding="40px||60px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_wc_tabs product="current" /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

    @staticmethod
    def _gallery_right_layout(colors: ColorScheme) -> str:
        """Gallery on the right side."""
        return """
[et_pb_section custom_padding="60px||60px|"]
    [et_pb_row column_structure="1_2,1_2"]
        [et_pb_column type="1_2"]
            [et_pb_wc_breadcrumb product="current" /]
            [et_pb_wc_title product="current" /]
            [et_pb_wc_rating product="current" /]
            [et_pb_wc_price product="current" /]
            [et_pb_wc_description product="current" /]
            [et_pb_wc_add_to_cart product="current" /]
        [/et_pb_column]
        [et_pb_column type="1_2"]
            [et_pb_wc_images product="current" /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

    @staticmethod
    def _full_width_layout(colors: ColorScheme) -> str:
        """Full-width immersive layout."""
        return """
<!-- Full Width Hero Image -->
[et_pb_section fullwidth="on"]
    [et_pb_fullwidth_image src="%%product_hero_image%%" /]
[/et_pb_section]

[et_pb_section custom_padding="60px||60px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_wc_breadcrumb product="current" /]
            [et_pb_wc_title product="current" text_orientation="center" /]
            [et_pb_wc_rating product="current" text_orientation="center" /]
            [et_pb_wc_price product="current" text_orientation="center" /]
        [/et_pb_column]
    [/et_pb_row]

    [et_pb_row column_structure="1_4,1_2,1_4"]
        [et_pb_column type="1_4"][/et_pb_column]
        [et_pb_column type="1_2"]
            [et_pb_wc_description product="current" /]
            [et_pb_wc_add_to_cart product="current" /]
        [/et_pb_column]
        [et_pb_column type="1_4"][/et_pb_column]
    [/et_pb_row]
[/et_pb_section]

<!-- Gallery Grid -->
[et_pb_section background_color="#f3f4f6" custom_padding="60px||60px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_wc_gallery product="current" show_product_gallery="on" /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

    @staticmethod
    def _centered_layout(colors: ColorScheme) -> str:
        """Centered elegant layout."""
        return """
[et_pb_section custom_padding="80px||80px|"]
    [et_pb_row column_structure="1_3,1_3,1_3"]
        [et_pb_column type="1_3"][/et_pb_column]
        [et_pb_column type="1_3"]
            [et_pb_wc_images product="current" /]
        [/et_pb_column]
        [et_pb_column type="1_3"][/et_pb_column]
    [/et_pb_row]

    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_wc_title product="current" text_orientation="center" /]
            [et_pb_wc_rating product="current" text_orientation="center" /]
            [et_pb_wc_price product="current" text_orientation="center" /]
        [/et_pb_column]
    [/et_pb_row]

    [et_pb_row column_structure="1_4,1_2,1_4"]
        [et_pb_column type="1_4"][/et_pb_column]
        [et_pb_column type="1_2"]
            [et_pb_wc_add_to_cart product="current" /]
        [/et_pb_column]
        [et_pb_column type="1_4"][/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

    @staticmethod
    def _split_screen_layout(colors: ColorScheme) -> str:
        """Split screen dramatic layout."""
        return """
[et_pb_section custom_padding="0px||0px|" fullwidth="on"]
    [et_pb_row make_fullwidth="on" custom_padding="0px||0px|" column_structure="1_2,1_2"]
        <!-- Left: Gallery with background -->
        [et_pb_column type="1_2" background_color="#f3f4f6"]
            [et_pb_wc_images product="current" custom_padding="60px|40px|60px|40px" /]
        [/et_pb_column]

        <!-- Right: Product Details -->
        [et_pb_column type="1_2" custom_padding="60px|40px|60px|40px"]
            [et_pb_wc_breadcrumb product="current" /]
            [et_pb_wc_title product="current" /]
            [et_pb_wc_rating product="current" /]
            [et_pb_wc_price product="current" /]
            [et_pb_wc_description product="current" /]
            [et_pb_wc_add_to_cart product="current" /]

            [et_pb_divider show_divider="off" height="20px" /]

            <!-- Features List -->
            [et_pb_text]
                <ul class="product-features">
                    <li>✓ Free Express Shipping</li>
                    <li>✓ 30-Day Returns</li>
                    <li>✓ 2-Year Warranty</li>
                    <li>✓ Secure Checkout</li>
                </ul>
            [/et_pb_text]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""


# ============================================================================
# SHOP PAGE LAYOUTS
# ============================================================================


class ShopPageBuilder:
    """Builds shop page layouts."""

    @staticmethod
    def get_layout_template(
        layout_type: ShopLayoutType,
        colors: ColorScheme = None,
        columns: int = 4,
        products_per_page: int = 12,
    ) -> str:
        """Get Divi layout template for shop page."""
        colors = colors or ColorScheme()

        if layout_type == ShopLayoutType.GRID:
            return ShopPageBuilder._grid_layout(colors, columns, products_per_page)
        elif layout_type == ShopLayoutType.LIST:
            return ShopPageBuilder._list_layout(colors, products_per_page)
        elif layout_type == ShopLayoutType.FEATURED_FIRST:
            return ShopPageBuilder._featured_first_layout(
                colors, columns, products_per_page
            )
        elif layout_type == ShopLayoutType.CATEGORY_BOXES:
            return ShopPageBuilder._category_boxes_layout(colors)
        else:
            return ShopPageBuilder._grid_layout(colors, columns, products_per_page)

    @staticmethod
    def _grid_layout(colors: ColorScheme, columns: int, per_page: int) -> str:
        """Standard grid layout."""
        return f"""
<!-- Shop Header -->
[et_pb_section custom_padding="40px||20px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_text text_orientation="center"]
                <h1>Shop All Products</h1>
                <p>Discover our range of premium electronics</p>
            [/et_pb_text]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]

<!-- Products Grid -->
[et_pb_section custom_padding="20px||60px|"]
    [et_pb_row column_structure="1_4,3_4"]
        <!-- Sidebar Filters -->
        [et_pb_column type="1_4"]
            [et_pb_sidebar area="shop-sidebar" /]
        [/et_pb_column]

        <!-- Products -->
        [et_pb_column type="3_4"]
            [et_pb_shop
                type="product"
                posts_number="{per_page}"
                columns_number="{columns}"
                orderby="popularity"
                show_pagination="on"
            /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

    @staticmethod
    def _list_layout(colors: ColorScheme, per_page: int) -> str:
        """List view layout."""
        return f"""
[et_pb_section custom_padding="40px||60px|"]
    [et_pb_row column_structure="1_4,3_4"]
        <!-- Sidebar -->
        [et_pb_column type="1_4"]
            [et_pb_sidebar area="shop-sidebar" /]
        [/et_pb_column]

        <!-- Products List -->
        [et_pb_column type="3_4"]
            [et_pb_shop
                type="product"
                posts_number="{per_page}"
                columns_number="1"
                orderby="date"
                show_pagination="on"
            /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

    @staticmethod
    def _featured_first_layout(colors: ColorScheme, columns: int, per_page: int) -> str:
        """Featured products first layout."""
        return f"""
<!-- Featured Products Hero -->
[et_pb_section background_color="#1f2937" custom_padding="60px||60px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_text text_orientation="center" text_text_color="#ffffff"]
                <h2>Featured Products</h2>
            [/et_pb_text]
            [et_pb_shop
                type="featured"
                posts_number="4"
                columns_number="4"
                orderby="date"
                show_pagination="off"
            /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]

<!-- All Products -->
[et_pb_section custom_padding="60px||60px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_text text_orientation="center"]
                <h2>All Products</h2>
            [/et_pb_text]
            [et_pb_shop
                type="product"
                posts_number="{per_page}"
                columns_number="{columns}"
                show_pagination="on"
            /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

    @staticmethod
    def _category_boxes_layout(colors: ColorScheme) -> str:
        """Category boxes layout."""
        return """
<!-- Shop by Category -->
[et_pb_section custom_padding="60px||60px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_text text_orientation="center"]
                <h1>Shop by Category</h1>
            [/et_pb_text]
        [/et_pb_column]
    [/et_pb_row]

    [et_pb_row column_structure="1_3,1_3,1_3"]
        [et_pb_column type="1_3"]
            [et_pb_blurb
                title="Smartphones"
                url="/product-category/smartphones/"
                use_icon="on"
                font_icon="%%71%%"
                icon_color="#2563eb"
            ]
                Browse our latest smartphones
            [/et_pb_blurb]
        [/et_pb_column]
        [et_pb_column type="1_3"]
            [et_pb_blurb
                title="Laptops"
                url="/product-category/laptops/"
                use_icon="on"
                font_icon="%%72%%"
                icon_color="#2563eb"
            ]
                Powerful laptops for every need
            [/et_pb_blurb]
        [/et_pb_column]
        [et_pb_column type="1_3"]
            [et_pb_blurb
                title="Audio"
                url="/product-category/audio/"
                use_icon="on"
                font_icon="%%73%%"
                icon_color="#2563eb"
            ]
                Premium headphones & speakers
            [/et_pb_blurb]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]

<!-- Latest Products -->
[et_pb_section background_color="#f3f4f6" custom_padding="60px||60px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_text text_orientation="center"]
                <h2>Latest Arrivals</h2>
            [/et_pb_text]
            [et_pb_shop
                type="latest"
                posts_number="8"
                columns_number="4"
            /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""


# ============================================================================
# CART & CHECKOUT STYLING
# ============================================================================


class CartCheckoutBuilder:
    """Builds cart and checkout page styles."""

    @staticmethod
    def get_cart_css(style: CartStyle, colors: ColorScheme = None) -> str:
        """Get CSS for cart page styling."""
        colors = colors or ColorScheme()

        base_css = f"""
/* Cart Page Styling */
.woocommerce-cart .woocommerce {{
    max-width: 1200px;
    margin: 0 auto;
}}

.woocommerce table.shop_table {{
    border: 1px solid {colors.border};
    border-radius: 8px;
    overflow: hidden;
}}

.woocommerce table.shop_table th {{
    background-color: {colors.surface};
    font-weight: 600;
    padding: 15px;
}}

.woocommerce table.shop_table td {{
    padding: 20px 15px;
    vertical-align: middle;
}}

.woocommerce table.shop_table .product-thumbnail img {{
    width: 80px;
    height: 80px;
    object-fit: cover;
    border-radius: 8px;
}}

.woocommerce .cart_totals {{
    background-color: {colors.surface};
    padding: 30px;
    border-radius: 8px;
}}

.woocommerce .cart_totals h2 {{
    font-size: 24px;
    margin-bottom: 20px;
}}

.woocommerce .cart_totals .wc-proceed-to-checkout a.checkout-button {{
    background-color: {colors.primary};
    color: #ffffff;
    padding: 15px 30px;
    border-radius: 8px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

.woocommerce .cart_totals .wc-proceed-to-checkout a.checkout-button:hover {{
    background-color: #1d4ed8;
}}
"""

        if style == CartStyle.MODERN:
            base_css += f"""
/* Modern Cart Style */
.woocommerce table.shop_table {{
    border: none;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
}}

.woocommerce table.shop_table tbody tr {{
    border-bottom: 1px solid {colors.border};
}}

.woocommerce table.shop_table tbody tr:last-child {{
    border-bottom: none;
}}
"""
        elif style == CartStyle.MINIMAL:
            base_css += """
/* Minimal Cart Style */
.woocommerce table.shop_table {
    border: none;
    background: transparent;
}

.woocommerce table.shop_table th {
    background: transparent;
    border-bottom: 2px solid #1f2937;
}
"""

        return base_css

    @staticmethod
    def get_checkout_css(style: CheckoutStyle, colors: ColorScheme = None) -> str:
        """Get CSS for checkout page styling."""
        colors = colors or ColorScheme()

        base_css = f"""
/* Checkout Page Styling */
.woocommerce-checkout .woocommerce {{
    max-width: 1200px;
    margin: 0 auto;
}}

.woocommerce form.checkout {{
    display: grid;
    gap: 30px;
}}

.woocommerce form.checkout .col2-set {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 30px;
}}

.woocommerce form.checkout h3 {{
    font-size: 20px;
    padding-bottom: 15px;
    border-bottom: 2px solid {colors.primary};
    margin-bottom: 20px;
}}

.woocommerce form .form-row {{
    margin-bottom: 15px;
}}

.woocommerce form .form-row label {{
    font-weight: 600;
    margin-bottom: 5px;
    display: block;
}}

.woocommerce form .form-row input.input-text,
.woocommerce form .form-row select {{
    width: 100%;
    padding: 12px 15px;
    border: 1px solid {colors.border};
    border-radius: 8px;
    font-size: 16px;
}}

.woocommerce form .form-row input.input-text:focus,
.woocommerce form .form-row select:focus {{
    border-color: {colors.primary};
    outline: none;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}}

#order_review_heading {{
    font-size: 24px;
}}

.woocommerce-checkout #payment {{
    background-color: {colors.surface};
    padding: 30px;
    border-radius: 8px;
}}

.woocommerce-checkout #payment .place-order button {{
    background-color: {colors.primary};
    color: #ffffff;
    width: 100%;
    padding: 18px;
    border-radius: 8px;
    font-size: 18px;
    font-weight: 600;
    border: none;
    cursor: pointer;
}}

.woocommerce-checkout #payment .place-order button:hover {{
    background-color: #1d4ed8;
}}

/* Trust Badges */
.checkout-trust-badges {{
    display: flex;
    justify-content: center;
    gap: 20px;
    padding: 20px 0;
    border-top: 1px solid {colors.border};
    margin-top: 20px;
}}

.checkout-trust-badges img {{
    height: 40px;
    opacity: 0.7;
}}
"""

        if style == CheckoutStyle.SINGLE_PAGE:
            base_css += """
/* Single Page Checkout */
.woocommerce-checkout {
    padding: 60px 0;
}

.woocommerce form.checkout .col2-set,
.woocommerce form.checkout #order_review {
    max-width: 800px;
    margin: 0 auto;
}
"""
        elif style == CheckoutStyle.MULTI_STEP:
            base_css += """
/* Multi-Step Checkout Indicators */
.checkout-steps {
    display: flex;
    justify-content: center;
    margin-bottom: 40px;
}

.checkout-steps .step {
    display: flex;
    align-items: center;
    padding: 0 20px;
}

.checkout-steps .step-number {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: #e5e7eb;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 10px;
}

.checkout-steps .step.active .step-number {
    background: #2563eb;
    color: #ffffff;
}
"""

        return base_css

    @staticmethod
    def get_checkout_trust_elements() -> str:
        """Get HTML for checkout trust elements."""
        return """
<!-- Trust Elements -->
<div class="checkout-trust-section">
    <div class="trust-badges">
        <div class="badge">
            <span class="icon">🔒</span>
            <span class="text">Secure 256-bit SSL</span>
        </div>
        <div class="badge">
            <span class="icon">💳</span>
            <span class="text">All major cards accepted</span>
        </div>
        <div class="badge">
            <span class="icon">🚚</span>
            <span class="text">Free shipping over $50</span>
        </div>
        <div class="badge">
            <span class="icon">↩️</span>
            <span class="text">30-day returns</span>
        </div>
    </div>

    <div class="payment-icons">
        <img src="/images/payment-visa.svg" alt="Visa" />
        <img src="/images/payment-mastercard.svg" alt="Mastercard" />
        <img src="/images/payment-amex.svg" alt="American Express" />
        <img src="/images/payment-paypal.svg" alt="PayPal" />
        <img src="/images/payment-apple-pay.svg" alt="Apple Pay" />
        <img src="/images/payment-google-pay.svg" alt="Google Pay" />
    </div>
</div>
"""


# ============================================================================
# CATEGORY TEMPLATE BUILDER
# ============================================================================


class CategoryTemplateBuilder:
    """Builds category page templates."""

    @staticmethod
    def get_category_template(
        category: CategoryData,
        colors: ColorScheme = None,
        show_subcategories: bool = True,
        products_per_page: int = 12,
    ) -> str:
        """Get Divi template for category page."""
        colors = colors or ColorScheme()

        template = f"""
<!-- Category Hero -->
[et_pb_section background_image="{category.image or '/images/category-default.jpg'}" parallax="on" custom_padding="100px||100px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_text text_orientation="center" text_text_color="#ffffff" background_color="rgba(0,0,0,0.5)" custom_padding="30px"]
                <h1>{category.name}</h1>
                <p>{category.description or f'Browse our selection of {category.name.lower()}'}</p>
            [/et_pb_text]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

        if show_subcategories:
            template += """
<!-- Subcategories -->
[et_pb_section background_color="#f3f4f6" custom_padding="40px||40px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_text text_orientation="center"]
                <h3>Shop by Category</h3>
            [/et_pb_text]
            <!-- Subcategory grid would be dynamically generated -->
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

        template += f"""
<!-- Products -->
[et_pb_section custom_padding="60px||60px|"]
    [et_pb_row column_structure="1_4,3_4"]
        [et_pb_column type="1_4"]
            <!-- Filters -->
            [et_pb_text]
                <h4>Filter Products</h4>
            [/et_pb_text]
            [et_pb_sidebar area="shop-filters" /]
        [/et_pb_column]

        [et_pb_column type="3_4"]
            [et_pb_shop
                type="product_cat"
                include_categories="{category.slug}"
                posts_number="{products_per_page}"
                columns_number="3"
                orderby="popularity"
                show_pagination="on"
            /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

        return template

    @staticmethod
    def get_category_css(colors: ColorScheme = None) -> str:
        """Get CSS for category pages."""
        colors = colors or ColorScheme()

        return f"""
/* Category Page Styling */
.product-category-hero {{
    position: relative;
    min-height: 300px;
    display: flex;
    align-items: center;
    justify-content: center;
}}

.product-category-hero::before {{
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(rgba(0,0,0,0.3), rgba(0,0,0,0.5));
}}

.product-category-hero h1 {{
    position: relative;
    z-index: 1;
    color: #ffffff;
    font-size: 48px;
    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
}}

.subcategory-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    padding: 20px 0;
}}

.subcategory-card {{
    background: #ffffff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    transition: transform 0.3s, box-shadow 0.3s;
}}

.subcategory-card:hover {{
    transform: translateY(-5px);
    box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1);
}}

.subcategory-card img {{
    width: 100%;
    height: 150px;
    object-fit: cover;
}}

.subcategory-card h4 {{
    padding: 15px;
    margin: 0;
    text-align: center;
}}

/* Active Filters */
.active-filters {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 20px;
}}

.filter-tag {{
    background: {colors.surface};
    padding: 5px 15px;
    border-radius: 20px;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 5px;
}}

.filter-tag .remove {{
    cursor: pointer;
    color: {colors.text_light};
}}

.filter-tag .remove:hover {{
    color: {colors.sale};
}}
"""


# ============================================================================
# PROMOTION BANNER BUILDER
# ============================================================================


class PromotionBannerBuilder:
    """Builds promotional banners."""

    @staticmethod
    def create_flash_sale_banner(
        headline: str, discount: int, end_date: datetime, shop_url: str = "/shop"
    ) -> PromotionBanner:
        """Create a flash sale countdown banner."""
        return PromotionBanner(
            banner_type=BannerType.COUNTDOWN,
            headline=headline,
            subheadline=f"Save up to {discount}% on selected items",
            button_text="Shop The Sale",
            button_url=shop_url,
            countdown_end=end_date,
            background_color="#1f2937",
            text_color="#ffffff",
        )

    @staticmethod
    def create_free_shipping_strip() -> PromotionBanner:
        """Create a free shipping announcement strip."""
        return PromotionBanner(
            banner_type=BannerType.STRIP,
            headline="🚚 Free Shipping on Orders Over $50!",
            button_text="Shop Now",
            button_url="/shop",
            background_color="#10b981",
            text_color="#ffffff",
        )

    @staticmethod
    def create_hero_promotion(
        headline: str,
        subheadline: str,
        image_url: str,
        button_text: str = "Shop Now",
        button_url: str = "/shop",
    ) -> PromotionBanner:
        """Create a hero promotional banner."""
        return PromotionBanner(
            banner_type=BannerType.HERO,
            headline=headline,
            subheadline=subheadline,
            button_text=button_text,
            button_url=button_url,
            background_image=image_url,
            text_color="#ffffff",
        )

    @staticmethod
    def create_discount_code_banner(
        code: str, discount: int, min_spend: float = 0
    ) -> PromotionBanner:
        """Create a discount code banner."""
        headline = f"Use Code {code} for {discount}% Off"
        subheadline = (
            f"Minimum spend ${min_spend:.0f}" if min_spend > 0 else "No minimum spend"
        )

        return PromotionBanner(
            banner_type=BannerType.STRIP,
            headline=headline,
            subheadline=subheadline,
            button_text="Shop Now",
            button_url="/shop",
            discount_code=code,
            background_color="#7c3aed",
            text_color="#ffffff",
        )

    @staticmethod
    def get_banner_css() -> str:
        """Get CSS for promotional banners."""
        return """
/* Promotional Banner Styles */
.promo-strip {
    background: linear-gradient(90deg, #ef4444, #dc2626);
    color: #ffffff;
    padding: 12px 20px;
    text-align: center;
    font-weight: 600;
}

.promo-strip a {
    color: #ffffff;
    text-decoration: underline;
    margin-left: 10px;
}

.promo-countdown {
    display: flex;
    justify-content: center;
    gap: 15px;
    margin-top: 15px;
}

.promo-countdown .time-block {
    background: rgba(255,255,255,0.1);
    padding: 10px 15px;
    border-radius: 8px;
    text-align: center;
    min-width: 60px;
}

.promo-countdown .time-block .number {
    font-size: 28px;
    font-weight: 700;
}

.promo-countdown .time-block .label {
    font-size: 12px;
    opacity: 0.8;
}

.floating-banner {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: #ffffff;
    box-shadow: 0 10px 25px rgba(0,0,0,0.15);
    border-radius: 12px;
    padding: 20px;
    max-width: 350px;
    z-index: 1000;
    animation: slideIn 0.5s ease;
}

@keyframes slideIn {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

.floating-banner .close-btn {
    position: absolute;
    top: 10px;
    right: 10px;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 20px;
    color: #6b7280;
}

.discount-code-display {
    background: #f3f4f6;
    padding: 10px 20px;
    border-radius: 8px;
    font-family: monospace;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 2px;
    display: inline-flex;
    align-items: center;
    gap: 10px;
}

.discount-code-display .copy-btn {
    background: #2563eb;
    color: #ffffff;
    border: none;
    padding: 5px 10px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
}
"""


# ============================================================================
# MOBILE COMMERCE OPTIMIZER
# ============================================================================


class MobileCommerceOptimizer:
    """Optimizes e-commerce for mobile devices."""

    @staticmethod
    def get_mobile_optimizations(config: MobileOptimization = None) -> str:
        """Get complete mobile optimization CSS."""
        config = config or MobileOptimization()

        css = config.to_css()

        # Additional mobile optimizations
        css += """
/* Mobile Navigation */
@media (max-width: 767px) {
    .mobile-menu-toggle {
        display: block;
    }

    .site-navigation {
        position: fixed;
        top: 0;
        left: -100%;
        width: 85%;
        height: 100vh;
        background: #ffffff;
        transition: left 0.3s ease;
        z-index: 1000;
        overflow-y: auto;
    }

    .site-navigation.active {
        left: 0;
    }

    .site-navigation .menu-item {
        display: block;
        padding: 15px 20px;
        border-bottom: 1px solid #e5e7eb;
    }

    /* Mobile Search */
    .mobile-search {
        padding: 15px;
        background: #f3f4f6;
    }

    .mobile-search input {
        width: 100%;
        padding: 12px 15px;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        font-size: 16px;
    }

    /* Mobile Cart Icon */
    .mobile-cart-icon {
        position: fixed;
        bottom: 20px;
        right: 20px;
        width: 56px;
        height: 56px;
        background: #2563eb;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
        z-index: 1000;
    }

    .mobile-cart-icon .cart-count {
        position: absolute;
        top: -5px;
        right: -5px;
        background: #ef4444;
        color: #ffffff;
        width: 22px;
        height: 22px;
        border-radius: 50%;
        font-size: 12px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    /* Quick View Modal */
    .quick-view-modal {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: #ffffff;
        border-radius: 20px 20px 0 0;
        padding: 30px 20px;
        transform: translateY(100%);
        transition: transform 0.3s ease;
        z-index: 1001;
        max-height: 80vh;
        overflow-y: auto;
    }

    .quick-view-modal.active {
        transform: translateY(0);
    }

    .quick-view-modal .handle {
        width: 40px;
        height: 4px;
        background: #e5e7eb;
        border-radius: 2px;
        margin: 0 auto 20px;
    }

    /* Product Card Touch Optimizations */
    .woocommerce ul.products li.product {
        touch-action: manipulation;
    }

    .woocommerce ul.products li.product .add_to_cart_button {
        opacity: 1;
        transform: none;
    }
}

/* Tablet Optimizations */
@media (max-width: 980px) and (min-width: 768px) {
    .woocommerce ul.products {
        grid-template-columns: repeat(3, 1fr);
    }

    .product-page .product-gallery,
    .product-page .product-details {
        width: 100%;
    }
}

/* Touch-Friendly Quantity Selectors */
.quantity-selector {
    display: flex;
    align-items: center;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    overflow: hidden;
}

.quantity-selector button {
    width: 48px;
    height: 48px;
    background: #f3f4f6;
    border: none;
    font-size: 20px;
    cursor: pointer;
}

.quantity-selector input {
    width: 60px;
    height: 48px;
    text-align: center;
    border: none;
    font-size: 18px;
    font-weight: 600;
}
"""

        return css

    @staticmethod
    def get_mobile_checkout_optimizations() -> str:
        """Get mobile-specific checkout optimizations."""
        return """
/* Mobile Checkout Optimizations */
@media (max-width: 767px) {
    .woocommerce-checkout .col2-set {
        grid-template-columns: 1fr;
    }

    .woocommerce-checkout .form-row {
        width: 100%;
        float: none;
    }

    .woocommerce-checkout .form-row-first,
    .woocommerce-checkout .form-row-last {
        width: 100%;
    }

    /* Express Checkout Buttons */
    .express-checkout {
        margin-bottom: 30px;
    }

    .express-checkout .button {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        width: 100%;
        margin-bottom: 10px;
        padding: 15px;
        border-radius: 8px;
    }

    .express-checkout .apple-pay-btn {
        background: #000000;
        color: #ffffff;
    }

    .express-checkout .google-pay-btn {
        background: #ffffff;
        color: #000000;
        border: 1px solid #e5e7eb;
    }

    .express-checkout .paypal-btn {
        background: #ffc439;
        color: #000000;
    }

    /* Order Summary Sticky */
    .woocommerce-checkout #order_review {
        position: sticky;
        top: 20px;
        background: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    /* Auto-fill Styles */
    input:-webkit-autofill {
        -webkit-box-shadow: 0 0 0 30px #ffffff inset !important;
    }
}
"""

    @staticmethod
    def get_mobile_product_card_template() -> str:
        """Get optimized mobile product card template."""
        return """
<div class="mobile-product-card">
    <div class="product-image-wrapper">
        <img src="{{product_image}}" alt="{{product_name}}" loading="lazy" />
        {{#if on_sale}}
        <span class="sale-badge">-{{discount_percent}}%</span>
        {{/if}}
        <button class="quick-view-btn" data-product-id="{{product_id}}">
            Quick View
        </button>
    </div>

    <div class="product-info">
        <h3 class="product-title">{{product_name}}</h3>

        <div class="product-rating">
            <span class="stars">{{rating_stars}}</span>
            <span class="count">({{review_count}})</span>
        </div>

        <div class="product-price">
            {{#if on_sale}}
            <span class="original-price">${{regular_price}}</span>
            <span class="sale-price">${{sale_price}}</span>
            {{else}}
            <span class="price">${{price}}</span>
            {{/if}}
        </div>

        <button class="add-to-cart-btn" data-product-id="{{product_id}}">
            Add to Cart
        </button>
    </div>
</div>
"""


# ============================================================================
# CROSS-SELL & UPSELL MANAGER
# ============================================================================


class CrossSellManager:
    """Manages cross-sell and upsell sections."""

    @staticmethod
    def get_cross_sell_section(
        title: str = "You May Also Like", product_count: int = 4
    ) -> str:
        """Get cross-sell section template."""
        return f"""
[et_pb_section background_color="#f3f4f6" custom_padding="60px||60px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_text text_orientation="center"]
                <h2>{title}</h2>
                <p>Based on what's in your cart</p>
            [/et_pb_text]
            [et_pb_wc_cross_sells columns_number="{product_count}" /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

    @staticmethod
    def get_upsell_section(
        title: str = "Upgrade Your Purchase", product_count: int = 4
    ) -> str:
        """Get upsell section template."""
        return f"""
[et_pb_section custom_padding="60px||60px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_text text_orientation="center"]
                <h2>{title}</h2>
                <p>Premium alternatives you might love</p>
            [/et_pb_text]
            [et_pb_wc_upsells columns_number="{product_count}" /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

    @staticmethod
    def get_recently_viewed_section(product_count: int = 4) -> str:
        """Get recently viewed products section."""
        return f"""
[et_pb_section custom_padding="60px||60px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_text text_orientation="center"]
                <h2>Recently Viewed</h2>
            [/et_pb_text]
            [et_pb_shop
                type="recently_viewed"
                posts_number="{product_count}"
                columns_number="4"
                show_pagination="off"
            /]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

    @staticmethod
    def get_bundle_deals_section() -> str:
        """Get bundle deals section template."""
        return """
[et_pb_section background_color="#1f2937" custom_padding="60px||60px|"]
    [et_pb_row]
        [et_pb_column type="4_4"]
            [et_pb_text text_orientation="center" text_text_color="#ffffff"]
                <h2>Bundle & Save</h2>
                <p>Get more value with our curated bundles</p>
            [/et_pb_text]
        [/et_pb_column]
    [/et_pb_row]

    [et_pb_row column_structure="1_3,1_3,1_3"]
        [et_pb_column type="1_3"]
            [et_pb_blurb
                title="Starter Pack"
                image="/images/bundle-starter.jpg"
                url="/product/starter-bundle/"
            ]
                <p>Everything you need to get started</p>
                <p class="bundle-price"><del>$299</del> <strong>$249</strong></p>
                <a href="/product/starter-bundle/" class="et_pb_button">View Bundle</a>
            [/et_pb_blurb]
        [/et_pb_column]
        [et_pb_column type="1_3"]
            [et_pb_blurb
                title="Pro Pack"
                image="/images/bundle-pro.jpg"
                url="/product/pro-bundle/"
            ]
                <p>For the serious enthusiast</p>
                <p class="bundle-price"><del>$599</del> <strong>$499</strong></p>
                <a href="/product/pro-bundle/" class="et_pb_button">View Bundle</a>
            [/et_pb_blurb]
        [/et_pb_column]
        [et_pb_column type="1_3"]
            [et_pb_blurb
                title="Ultimate Pack"
                image="/images/bundle-ultimate.jpg"
                url="/product/ultimate-bundle/"
            ]
                <p>The complete package</p>
                <p class="bundle-price"><del>$999</del> <strong>$799</strong></p>
                <a href="/product/ultimate-bundle/" class="et_pb_button">View Bundle</a>
            [/et_pb_blurb]
        [/et_pb_column]
    [/et_pb_row]
[/et_pb_section]
"""

    @staticmethod
    def get_cross_sell_css() -> str:
        """Get CSS for cross-sell sections."""
        return """
/* Cross-Sell & Upsell Styling */
.woocommerce .cross-sells,
.woocommerce .upsells,
.woocommerce .related {
    margin-top: 60px;
    padding-top: 60px;
    border-top: 1px solid #e5e7eb;
}

.woocommerce .cross-sells > h2,
.woocommerce .upsells > h2,
.woocommerce .related > h2 {
    text-align: center;
    margin-bottom: 30px;
    font-size: 28px;
}

.woocommerce .cross-sells ul.products,
.woocommerce .upsells ul.products,
.woocommerce .related ul.products {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 30px;
}

@media (max-width: 980px) {
    .woocommerce .cross-sells ul.products,
    .woocommerce .upsells ul.products,
    .woocommerce .related ul.products {
        grid-template-columns: repeat(2, 1fr);
    }
}

@media (max-width: 480px) {
    .woocommerce .cross-sells ul.products,
    .woocommerce .upsells ul.products,
    .woocommerce .related ul.products {
        grid-template-columns: 1fr;
    }
}

/* Bundle Deals */
.bundle-card {
    background: #ffffff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.bundle-card .bundle-image {
    position: relative;
}

.bundle-card .bundle-image .save-badge {
    position: absolute;
    top: 15px;
    right: 15px;
    background: #ef4444;
    color: #ffffff;
    padding: 5px 15px;
    border-radius: 20px;
    font-weight: 700;
}

.bundle-card .bundle-content {
    padding: 20px;
}

.bundle-card .bundle-price {
    font-size: 24px;
    margin: 15px 0;
}

.bundle-card .bundle-price del {
    color: #9ca3af;
    font-size: 18px;
}

.bundle-card .bundle-price strong {
    color: #10b981;
}

.bundle-card .bundle-includes {
    list-style: none;
    padding: 0;
    margin: 15px 0;
}

.bundle-card .bundle-includes li {
    padding: 5px 0;
    padding-left: 25px;
    position: relative;
}

.bundle-card .bundle-includes li::before {
    content: '✓';
    position: absolute;
    left: 0;
    color: #10b981;
}
"""


# ============================================================================
# MAIN E-COMMERCE THEME AGENT
# ============================================================================


class DiviEcommerceAgent:
    """Main Divi e-commerce theme agent."""

    def __init__(self, demo_mode: bool = True):
        self.demo_mode = demo_mode
        self.colors = ColorScheme()
        self.product_builder = ProductPageBuilder()
        self.shop_builder = ShopPageBuilder()
        self.cart_builder = CartCheckoutBuilder()
        self.category_builder = CategoryTemplateBuilder()
        self.banner_builder = PromotionBannerBuilder()
        self.mobile_optimizer = MobileCommerceOptimizer()
        self.cross_sell_manager = CrossSellManager()

    def generate_product_layout(
        self, layout_type: ProductLayoutType = ProductLayoutType.STANDARD
    ) -> str:
        """Generate a product page layout."""
        return self.product_builder.get_layout_template(layout_type, self.colors)

    def generate_shop_layout(
        self,
        layout_type: ShopLayoutType = ShopLayoutType.GRID,
        columns: int = 4,
        products_per_page: int = 12,
    ) -> str:
        """Generate a shop page layout."""
        return self.shop_builder.get_layout_template(
            layout_type, self.colors, columns, products_per_page
        )

    def generate_category_template(
        self, category: CategoryData, show_subcategories: bool = True
    ) -> str:
        """Generate a category page template."""
        return self.category_builder.get_category_template(
            category, self.colors, show_subcategories
        )

    def generate_cart_styling(self, style: CartStyle = CartStyle.MODERN) -> str:
        """Generate cart page styling."""
        return self.cart_builder.get_cart_css(style, self.colors)

    def generate_checkout_styling(
        self, style: CheckoutStyle = CheckoutStyle.SINGLE_PAGE
    ) -> str:
        """Generate checkout page styling."""
        return self.cart_builder.get_checkout_css(style, self.colors)

    def generate_promotional_banner(
        self, banner_type: BannerType, headline: str, **kwargs
    ) -> str:
        """Generate a promotional banner."""
        banner = PromotionBanner(banner_type=banner_type, headline=headline, **kwargs)
        return banner.to_divi_module()

    def generate_mobile_css(self) -> str:
        """Generate mobile optimization CSS."""
        return self.mobile_optimizer.get_mobile_optimizations()

    def generate_cross_sell_section(self) -> str:
        """Generate cross-sell section."""
        return self.cross_sell_manager.get_cross_sell_section()

    def generate_complete_theme_css(self) -> str:
        """Generate complete theme CSS."""
        css_parts = [
            self.colors.to_css_variables(),
            self.generate_cart_styling(CartStyle.MODERN),
            self.generate_checkout_styling(CheckoutStyle.SINGLE_PAGE),
            self.category_builder.get_category_css(self.colors),
            self.banner_builder.get_banner_css(),
            self.mobile_optimizer.get_mobile_optimizations(),
            self.mobile_optimizer.get_mobile_checkout_optimizations(),
            self.cross_sell_manager.get_cross_sell_css(),
        ]

        return "\n\n".join(css_parts)

    def demo_run(self):
        """Run demonstration of e-commerce theme features."""
        print("\n" + "=" * 70)
        print("  Divi E-Commerce Theme Assistant - Demo Mode")
        print("  Electronics Store Theme Builder")
        print("=" * 70)

        # Demo 1: Product Layouts
        print("\n📦 Product Page Layouts:")
        print("-" * 50)
        for layout in ProductLayoutType:
            print(f"   • {layout.value.replace('_', ' ').title()}")
        print("   Default template lines: ~50 (Standard Layout)")

        # Demo 2: Shop Layouts
        print("\n🏪 Shop Page Layouts:")
        print("-" * 50)
        for layout in ShopLayoutType:
            print(f"   • {layout.value.replace('_', ' ').title()}")

        # Demo 3: Color Scheme
        print("\n🎨 E-Commerce Color Scheme:")
        print("-" * 50)
        print(f"   Primary:     {self.colors.primary} (Trust blue)")
        print(f"   Secondary:   {self.colors.secondary} (Success green)")
        print(f"   Sale:        {self.colors.sale} (Attention red)")
        print(f"   Accent:      {self.colors.accent} (Warning amber)")

        # Demo 4: Cart Styles
        print("\n🛒 Cart Page Styles:")
        print("-" * 50)
        for style in CartStyle:
            print(f"   • {style.value.title()}")

        # Demo 5: Checkout Styles
        print("\n💳 Checkout Page Styles:")
        print("-" * 50)
        for style in CheckoutStyle:
            print(f"   • {style.value.replace('_', ' ').title()}")

        # Demo 6: Promotional Banners
        print("\n📢 Promotional Banner Types:")
        print("-" * 50)
        for banner_type in BannerType:
            print(f"   • {banner_type.value.title()}")

        # Demo 7: Sample Banner
        print("\n🔥 Sample Flash Sale Banner:")
        print("-" * 50)
        banner = self.banner_builder.create_flash_sale_banner(
            headline="Flash Sale!",
            discount=30,
            end_date=datetime.now() + timedelta(days=3),
        )
        print(f"   Type: {banner.banner_type.value}")
        print(f"   Headline: {banner.headline}")
        print(f"   Subheadline: {banner.subheadline}")

        # Demo 8: Mobile Optimizations
        print("\n📱 Mobile Commerce Optimizations:")
        print("-" * 50)
        mobile_config = MobileOptimization()
        print(f"   • Sticky Add to Cart: {mobile_config.sticky_add_to_cart}")
        print(f"   • Quick View: {mobile_config.quick_view_enabled}")
        print(f"   • Touch Target Size: {mobile_config.min_button_height}px min")
        print(f"   • Mobile Filters: {mobile_config.mobile_filters_sidebar}")

        # Demo 9: Category Template
        print("\n📁 Sample Category (Smartphones):")
        print("-" * 50)
        category = CategoryData(
            id=1,
            name="Smartphones",
            slug="smartphones",
            description="Browse our latest smartphones from top brands",
            product_count=45,
        )
        print(f"   Name: {category.name}")
        print(f"   Products: {category.product_count}")
        print("   Template sections: Hero, Subcategories, Products Grid")

        # Demo 10: Cross-Sell/Upsell
        print("\n🔄 Cross-Sell & Upsell Sections:")
        print("-" * 50)
        print("   • You May Also Like (Cross-sell)")
        print("   • Upgrade Your Purchase (Upsell)")
        print("   • Recently Viewed")
        print("   • Bundle & Save")

        # Demo 11: Sample Product
        print("\n📱 Sample Product Data:")
        print("-" * 50)
        product = ProductData(
            id=1,
            name="Wireless Earbuds Pro",
            slug="wireless-earbuds-pro",
            price=149.99,
            regular_price=199.99,
            sale_price=149.99,
            on_sale=True,
            rating=4.5,
            review_count=127,
            categories=["Audio", "Earbuds"],
        )
        print(f"   Name: {product.name}")
        print(f"   Regular: ${product.regular_price}")
        print(f"   Sale: ${product.sale_price}")
        print(f"   Discount: {product.get_discount_percentage()}% off")
        print(f"   Rating: {product.rating}/5 ({product.review_count} reviews)")

        # Demo 12: Theme CSS Preview
        print("\n🎨 Theme CSS Generated:")
        print("-" * 50)
        css = self.generate_complete_theme_css()
        lines = css.split("\n")
        print(f"   Total CSS lines: {len(lines)}")
        print("   Includes: Variables, Cart, Checkout, Category,")
        print("             Banners, Mobile, Cross-sell styles")

        # Demo 13: Trust Elements
        print("\n🛡️  Checkout Trust Elements:")
        print("-" * 50)
        print("   • Secure 256-bit SSL badge")
        print("   • Payment icons (Visa, MC, Amex, PayPal)")
        print("   • Free shipping indicator")
        print("   • 30-day returns guarantee")

        # Demo 14: WooCommerce Modules
        print("\n🔧 Divi WooCommerce Modules Used:")
        print("-" * 50)
        wc_modules = [
            "et_pb_wc_images",
            "et_pb_wc_title",
            "et_pb_wc_price",
            "et_pb_wc_add_to_cart",
            "et_pb_wc_rating",
            "et_pb_wc_meta",
            "et_pb_wc_tabs",
            "et_pb_wc_related_products",
            "et_pb_wc_upsells",
            "et_pb_shop",
            "et_pb_wc_breadcrumb",
            "et_pb_wc_gallery",
        ]
        for module in wc_modules[:8]:
            print(f"   • {module}")

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
        description="Divi E-Commerce Theme Assistant for Electronics Store"
    )
    parser.add_argument("--demo", action="store_true", help="Run in demo mode")
    parser.add_argument(
        "--layout",
        type=str,
        choices=["product", "shop", "category", "cart", "checkout"],
        help="Generate specific layout",
    )
    parser.add_argument("--style", type=str, help="Layout style variant")
    parser.add_argument(
        "--category", type=str, help="Category name for category layout"
    )
    parser.add_argument(
        "--css", action="store_true", help="Generate complete theme CSS"
    )
    parser.add_argument(
        "--banner",
        type=str,
        choices=[bt.value for bt in BannerType],
        help="Generate promotional banner",
    )

    args = parser.parse_args()

    agent = DiviEcommerceAgent(demo_mode=args.demo)

    if args.demo:
        agent.demo_run()
    elif args.css:
        print(agent.generate_complete_theme_css())
    elif args.layout == "product":
        style = (
            ProductLayoutType(args.style) if args.style else ProductLayoutType.STANDARD
        )
        print(agent.generate_product_layout(style))
    elif args.layout == "shop":
        style = ShopLayoutType(args.style) if args.style else ShopLayoutType.GRID
        print(agent.generate_shop_layout(style))
    elif args.layout == "category":
        category = CategoryData(
            id=1,
            name=args.category or "Products",
            slug=(args.category or "products").lower().replace(" ", "-"),
        )
        print(agent.generate_category_template(category))
    elif args.layout == "cart":
        style = CartStyle(args.style) if args.style else CartStyle.MODERN
        print(agent.generate_cart_styling(style))
    elif args.layout == "checkout":
        style = CheckoutStyle(args.style) if args.style else CheckoutStyle.SINGLE_PAGE
        print(agent.generate_checkout_styling(style))
    elif args.banner:
        print(
            agent.generate_promotional_banner(
                BannerType(args.banner),
                headline="Sample Promotion",
            )
        )
    else:
        agent.demo_run()


if __name__ == "__main__":
    main()
