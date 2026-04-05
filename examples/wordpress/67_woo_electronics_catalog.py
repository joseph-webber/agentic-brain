#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 67: WooCommerce Electronics Catalog Management

Comprehensive product catalog management system for electronics retail.
Handles product hierarchy, attributes, pricing, stock monitoring, and comparisons.

Use Cases:
- Product catalog management (monitors, keyboards, cables, USB hubs, etc.)
- Category hierarchy (Computers > Peripherals > Keyboards)
- Product attributes (brand, specs, compatibility)
- Price management, bulk pricing, sale prices
- Stock level monitoring with reorder alerts
- Product comparison features

Requirements:
- WooCommerce 3.5+ with REST API enabled
- Consumer Key/Secret with read/write access
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================


class StockStatus(Enum):
    """Stock status levels."""

    IN_STOCK = "instock"
    LOW_STOCK = "lowstock"
    OUT_OF_STOCK = "outofstock"
    ON_BACKORDER = "onbackorder"
    DISCONTINUED = "discontinued"


class ProductType(Enum):
    """Product types."""

    SIMPLE = "simple"
    VARIABLE = "variable"
    GROUPED = "grouped"
    BUNDLE = "bundle"


class PriceType(Enum):
    """Price types."""

    REGULAR = "regular"
    SALE = "sale"
    BULK = "bulk"
    CLEARANCE = "clearance"


# =============================================================================
# CATEGORY HIERARCHY
# =============================================================================

CATEGORY_HIERARCHY = {
    "Computers": {
        "id": 100,
        "children": {
            "Desktops": {"id": 101, "children": {}},
            "Laptops": {"id": 102, "children": {}},
            "Tablets": {"id": 103, "children": {}},
        },
    },
    "Peripherals": {
        "id": 200,
        "children": {
            "Keyboards": {
                "id": 201,
                "children": {
                    "Mechanical": {"id": 2011, "children": {}},
                    "Membrane": {"id": 2012, "children": {}},
                    "Wireless": {"id": 2013, "children": {}},
                },
            },
            "Mice": {
                "id": 202,
                "children": {
                    "Gaming": {"id": 2021, "children": {}},
                    "Wireless": {"id": 2022, "children": {}},
                    "Ergonomic": {"id": 2023, "children": {}},
                },
            },
            "Webcams": {"id": 203, "children": {}},
            "Headsets": {"id": 204, "children": {}},
        },
    },
    "Monitors": {
        "id": 300,
        "children": {
            "Gaming Monitors": {"id": 301, "children": {}},
            "Office Monitors": {"id": 302, "children": {}},
            "Ultrawide": {"id": 303, "children": {}},
            "4K Monitors": {"id": 304, "children": {}},
        },
    },
    "Cables & Adapters": {
        "id": 400,
        "children": {
            "HDMI Cables": {"id": 401, "children": {}},
            "USB Cables": {"id": 402, "children": {}},
            "DisplayPort": {"id": 403, "children": {}},
            "Adapters": {"id": 404, "children": {}},
        },
    },
    "USB Hubs & Docks": {
        "id": 500,
        "children": {
            "USB Hubs": {"id": 501, "children": {}},
            "Docking Stations": {"id": 502, "children": {}},
            "Card Readers": {"id": 503, "children": {}},
        },
    },
    "Storage": {
        "id": 600,
        "children": {
            "External SSD": {"id": 601, "children": {}},
            "External HDD": {"id": 602, "children": {}},
            "USB Drives": {"id": 603, "children": {}},
            "Memory Cards": {"id": 604, "children": {}},
        },
    },
    "Power": {
        "id": 700,
        "children": {
            "Power Banks": {"id": 701, "children": {}},
            "Chargers": {"id": 702, "children": {}},
            "UPS": {"id": 703, "children": {}},
            "Surge Protectors": {"id": 704, "children": {}},
        },
    },
    "Networking": {
        "id": 800,
        "children": {
            "Routers": {"id": 801, "children": {}},
            "Switches": {"id": 802, "children": {}},
            "WiFi Adapters": {"id": 803, "children": {}},
            "Ethernet Cables": {"id": 804, "children": {}},
        },
    },
}


# =============================================================================
# DEMO DATA - 50+ ELECTRONICS PRODUCTS
# =============================================================================

DEMO_PRODUCTS = [
    # MONITORS (10 products)
    {
        "id": 1001,
        "name": "ProView 27-inch Gaming Monitor 165Hz",
        "sku": "MON-PV27G-165",
        "type": "simple",
        "price": "449.99",
        "regular_price": "499.99",
        "sale_price": "449.99",
        "stock_quantity": 25,
        "stock_status": "instock",
        "low_stock_threshold": 10,
        "category_path": ["Monitors", "Gaming Monitors"],
        "brand": "ProView",
        "attributes": {
            "screen_size": "27 inches",
            "resolution": "2560x1440",
            "refresh_rate": "165Hz",
            "panel_type": "IPS",
            "response_time": "1ms",
            "inputs": ["HDMI 2.1", "DisplayPort 1.4", "USB-C"],
            "hdr": "HDR400",
        },
        "weight": "5.2",
        "dimensions": {"length": "62", "width": "45", "height": "20"},
        "description": "High-performance gaming monitor with 165Hz refresh and 1ms response.",
        "short_description": '27" 1440p 165Hz Gaming Monitor',
        "related_products": [1002, 1020, 1030],
        "upsell_products": [1003, 1004],
        "bulk_pricing": [
            {"min_qty": 5, "discount_percent": 5},
            {"min_qty": 10, "discount_percent": 10},
        ],
    },
    {
        "id": 1002,
        "name": "ProView 24-inch Office Monitor",
        "sku": "MON-PV24O",
        "type": "simple",
        "price": "199.99",
        "regular_price": "199.99",
        "sale_price": None,
        "stock_quantity": 50,
        "stock_status": "instock",
        "low_stock_threshold": 15,
        "category_path": ["Monitors", "Office Monitors"],
        "brand": "ProView",
        "attributes": {
            "screen_size": "24 inches",
            "resolution": "1920x1080",
            "refresh_rate": "75Hz",
            "panel_type": "IPS",
            "response_time": "5ms",
            "inputs": ["HDMI", "VGA", "DisplayPort"],
            "hdr": None,
        },
        "weight": "4.1",
        "dimensions": {"length": "55", "width": "40", "height": "18"},
        "description": "Reliable office monitor with excellent color accuracy.",
        "short_description": '24" Full HD Office Monitor',
        "related_products": [1001, 1005],
        "upsell_products": [1001],
    },
    {
        "id": 1003,
        "name": "UltraWide 34-inch Curved Monitor",
        "sku": "MON-UW34C",
        "type": "simple",
        "price": "699.99",
        "regular_price": "799.99",
        "sale_price": "699.99",
        "stock_quantity": 12,
        "stock_status": "instock",
        "low_stock_threshold": 5,
        "category_path": ["Monitors", "Ultrawide"],
        "brand": "UltraWide",
        "attributes": {
            "screen_size": "34 inches",
            "resolution": "3440x1440",
            "refresh_rate": "144Hz",
            "panel_type": "VA",
            "response_time": "4ms",
            "inputs": ["HDMI 2.0", "DisplayPort 1.4", "USB-C PD 65W"],
            "hdr": "HDR600",
            "curvature": "1500R",
        },
        "weight": "8.5",
        "dimensions": {"length": "82", "width": "50", "height": "25"},
        "description": "Immersive ultrawide curved monitor for productivity and gaming.",
        "short_description": '34" Ultrawide Curved 144Hz',
        "related_products": [1001, 1004],
        "upsell_products": [1004],
    },
    {
        "id": 1004,
        "name": "CrystalView 32-inch 4K Monitor",
        "sku": "MON-CV32-4K",
        "type": "simple",
        "price": "549.99",
        "regular_price": "599.99",
        "sale_price": "549.99",
        "stock_quantity": 18,
        "stock_status": "instock",
        "low_stock_threshold": 8,
        "category_path": ["Monitors", "4K Monitors"],
        "brand": "CrystalView",
        "attributes": {
            "screen_size": "32 inches",
            "resolution": "3840x2160",
            "refresh_rate": "60Hz",
            "panel_type": "IPS",
            "response_time": "4ms",
            "inputs": ["HDMI 2.0", "DisplayPort 1.4", "USB-C"],
            "hdr": "HDR10",
        },
        "weight": "7.2",
        "dimensions": {"length": "73", "width": "48", "height": "22"},
        "description": "Stunning 4K display for creative professionals.",
        "short_description": '32" 4K UHD Professional Monitor',
        "related_products": [1003],
        "upsell_products": [],
    },
    {
        "id": 1005,
        "name": "BudgetView 22-inch Monitor",
        "sku": "MON-BV22",
        "type": "simple",
        "price": "129.99",
        "regular_price": "149.99",
        "sale_price": "129.99",
        "stock_quantity": 75,
        "stock_status": "instock",
        "low_stock_threshold": 20,
        "category_path": ["Monitors", "Office Monitors"],
        "brand": "BudgetView",
        "attributes": {
            "screen_size": "22 inches",
            "resolution": "1920x1080",
            "refresh_rate": "60Hz",
            "panel_type": "TN",
            "response_time": "5ms",
            "inputs": ["HDMI", "VGA"],
        },
        "weight": "3.2",
        "dimensions": {"length": "50", "width": "35", "height": "15"},
        "description": "Affordable everyday monitor for basic computing.",
        "short_description": '22" Full HD Budget Monitor',
        "related_products": [1002],
    },
    # KEYBOARDS (10 products)
    {
        "id": 1010,
        "name": "MechPro RGB Mechanical Keyboard",
        "sku": "KB-MECH-RGB",
        "type": "variable",
        "price": "129.99",
        "regular_price": "149.99",
        "sale_price": "129.99",
        "stock_quantity": 45,
        "stock_status": "instock",
        "low_stock_threshold": 15,
        "category_path": ["Peripherals", "Keyboards", "Mechanical"],
        "brand": "MechPro",
        "attributes": {
            "switch_type": "Blue Switches",
            "layout": "Full-size",
            "backlight": "RGB",
            "connection": "USB-C Wired",
            "keycaps": "PBT Double-shot",
            "n_key_rollover": "Full NKRO",
            "media_keys": True,
        },
        "variations": [
            {
                "id": 10101,
                "name": "Blue Switches",
                "sku": "KB-MECH-RGB-BL",
                "stock": 20,
            },
            {"id": 10102, "name": "Red Switches", "sku": "KB-MECH-RGB-RD", "stock": 15},
            {
                "id": 10103,
                "name": "Brown Switches",
                "sku": "KB-MECH-RGB-BR",
                "stock": 10,
            },
        ],
        "weight": "0.95",
        "dimensions": {"length": "44", "width": "14", "height": "4"},
        "description": "Premium mechanical keyboard with customizable RGB lighting.",
        "short_description": "Full-size RGB Mechanical Keyboard",
        "related_products": [1011, 1020],
    },
    {
        "id": 1011,
        "name": "SlimType Wireless Keyboard",
        "sku": "KB-SLIM-WL",
        "type": "simple",
        "price": "79.99",
        "regular_price": "89.99",
        "sale_price": "79.99",
        "stock_quantity": 60,
        "stock_status": "instock",
        "low_stock_threshold": 20,
        "category_path": ["Peripherals", "Keyboards", "Wireless"],
        "brand": "SlimType",
        "attributes": {
            "layout": "Compact",
            "connection": "Bluetooth + 2.4GHz",
            "battery": "Rechargeable Li-ion",
            "battery_life": "Up to 6 months",
            "multi_device": "3 devices",
        },
        "weight": "0.45",
        "dimensions": {"length": "38", "width": "12", "height": "2"},
        "description": "Ultra-slim wireless keyboard for multi-device productivity.",
        "short_description": "Compact Wireless Keyboard",
        "related_products": [1010, 1021],
    },
    {
        "id": 1012,
        "name": "ErgoType Split Keyboard",
        "sku": "KB-ERGO-SPLIT",
        "type": "simple",
        "price": "189.99",
        "regular_price": "199.99",
        "sale_price": "189.99",
        "stock_quantity": 15,
        "stock_status": "instock",
        "low_stock_threshold": 5,
        "category_path": ["Peripherals", "Keyboards", "Mechanical"],
        "brand": "ErgoType",
        "attributes": {
            "layout": "Split Ergonomic",
            "switch_type": "Linear Red",
            "connection": "USB-C",
            "tilt_angles": ["0°", "7°", "15°"],
            "wrist_rest": "Included",
        },
        "weight": "1.2",
        "dimensions": {"length": "48", "width": "20", "height": "5"},
        "description": "Ergonomic split keyboard designed for comfort during long typing sessions.",
        "short_description": "Ergonomic Split Mechanical Keyboard",
        "related_products": [1010, 1022],
    },
    {
        "id": 1013,
        "name": "BasicBoard USB Keyboard",
        "sku": "KB-BASIC-USB",
        "type": "simple",
        "price": "24.99",
        "regular_price": "29.99",
        "sale_price": "24.99",
        "stock_quantity": 150,
        "stock_status": "instock",
        "low_stock_threshold": 50,
        "category_path": ["Peripherals", "Keyboards", "Membrane"],
        "brand": "BasicBoard",
        "attributes": {
            "layout": "Full-size",
            "connection": "USB-A",
            "spill_resistant": True,
        },
        "weight": "0.55",
        "dimensions": {"length": "45", "width": "15", "height": "3"},
        "description": "Reliable membrane keyboard for everyday office use.",
        "short_description": "Full-size USB Keyboard",
        "bulk_pricing": [
            {"min_qty": 10, "discount_percent": 10},
            {"min_qty": 25, "discount_percent": 15},
            {"min_qty": 50, "discount_percent": 20},
        ],
    },
    {
        "id": 1014,
        "name": "CompactMech 60% Keyboard",
        "sku": "KB-CM60",
        "type": "simple",
        "price": "89.99",
        "regular_price": "99.99",
        "sale_price": "89.99",
        "stock_quantity": 35,
        "stock_status": "instock",
        "low_stock_threshold": 10,
        "category_path": ["Peripherals", "Keyboards", "Mechanical"],
        "brand": "CompactMech",
        "attributes": {
            "layout": "60%",
            "switch_type": "Gateron Brown",
            "backlight": "White LED",
            "connection": "USB-C Detachable",
            "hot_swappable": True,
        },
        "weight": "0.65",
        "dimensions": {"length": "29", "width": "10", "height": "4"},
        "description": "Compact 60% mechanical keyboard with hot-swappable switches.",
        "short_description": "60% Hot-swap Mechanical Keyboard",
    },
    # MICE (8 products)
    {
        "id": 1020,
        "name": "PrecisionX Gaming Mouse",
        "sku": "MS-PX-GAME",
        "type": "simple",
        "price": "79.99",
        "regular_price": "89.99",
        "sale_price": "79.99",
        "stock_quantity": 55,
        "stock_status": "instock",
        "low_stock_threshold": 15,
        "category_path": ["Peripherals", "Mice", "Gaming"],
        "brand": "PrecisionX",
        "attributes": {
            "sensor": "Optical 16000 DPI",
            "buttons": 8,
            "connection": "Wired USB",
            "weight": "85g adjustable",
            "rgb": True,
            "polling_rate": "1000Hz",
        },
        "weight": "0.12",
        "dimensions": {"length": "12", "width": "7", "height": "4"},
        "description": "High-precision gaming mouse with customizable DPI and RGB.",
        "short_description": "16000 DPI Gaming Mouse",
        "related_products": [1001, 1010],
    },
    {
        "id": 1021,
        "name": "ErgoGrip Wireless Mouse",
        "sku": "MS-EG-WL",
        "type": "simple",
        "price": "49.99",
        "regular_price": "59.99",
        "sale_price": "49.99",
        "stock_quantity": 80,
        "stock_status": "instock",
        "low_stock_threshold": 25,
        "category_path": ["Peripherals", "Mice", "Ergonomic"],
        "brand": "ErgoGrip",
        "attributes": {
            "sensor": "Optical 4000 DPI",
            "buttons": 6,
            "connection": "2.4GHz Wireless",
            "battery": "AA x 2",
            "battery_life": "18 months",
            "ergonomic_design": "Vertical grip",
        },
        "weight": "0.14",
        "dimensions": {"length": "12", "width": "8", "height": "7"},
        "description": "Ergonomic vertical mouse designed to reduce wrist strain.",
        "short_description": "Ergonomic Vertical Wireless Mouse",
    },
    {
        "id": 1022,
        "name": "TravelMouse Compact",
        "sku": "MS-TM-COMP",
        "type": "simple",
        "price": "29.99",
        "regular_price": "34.99",
        "sale_price": "29.99",
        "stock_quantity": 100,
        "stock_status": "instock",
        "low_stock_threshold": 30,
        "category_path": ["Peripherals", "Mice", "Wireless"],
        "brand": "TravelMouse",
        "attributes": {
            "sensor": "Optical 1600 DPI",
            "buttons": 3,
            "connection": "Bluetooth + USB Receiver",
            "battery": "AAA x 1",
            "foldable": True,
        },
        "weight": "0.06",
        "dimensions": {"length": "10", "width": "5", "height": "3"},
        "description": "Ultra-compact travel mouse with dual connectivity.",
        "short_description": "Foldable Travel Mouse",
    },
    {
        "id": 1023,
        "name": "BasicMouse USB",
        "sku": "MS-BASIC-USB",
        "type": "simple",
        "price": "12.99",
        "regular_price": "14.99",
        "sale_price": "12.99",
        "stock_quantity": 200,
        "stock_status": "instock",
        "low_stock_threshold": 50,
        "category_path": ["Peripherals", "Mice", "Wireless"],
        "brand": "BasicMouse",
        "attributes": {
            "sensor": "Optical 1000 DPI",
            "buttons": 3,
            "connection": "USB-A Wired",
        },
        "weight": "0.08",
        "dimensions": {"length": "11", "width": "6", "height": "4"},
        "description": "Simple and reliable wired mouse for everyday use.",
        "short_description": "Basic USB Mouse",
        "bulk_pricing": [
            {"min_qty": 10, "discount_percent": 10},
            {"min_qty": 25, "discount_percent": 15},
        ],
    },
    # CABLES (8 products)
    {
        "id": 1030,
        "name": "ProCable HDMI 2.1 - 2m",
        "sku": "CBL-HDMI21-2M",
        "type": "simple",
        "price": "24.99",
        "regular_price": "29.99",
        "sale_price": "24.99",
        "stock_quantity": 150,
        "stock_status": "instock",
        "low_stock_threshold": 40,
        "category_path": ["Cables & Adapters", "HDMI Cables"],
        "brand": "ProCable",
        "attributes": {
            "length": "2m",
            "version": "HDMI 2.1",
            "max_resolution": "8K@60Hz / 4K@120Hz",
            "arc": True,
            "ethernet": True,
        },
        "weight": "0.15",
        "dimensions": {"length": "25", "width": "5", "height": "3"},
        "description": "Premium HDMI 2.1 cable supporting 8K and 4K high refresh.",
        "short_description": "HDMI 2.1 Cable 2m",
        "bulk_pricing": [
            {"min_qty": 5, "discount_percent": 5},
            {"min_qty": 20, "discount_percent": 15},
        ],
    },
    {
        "id": 1031,
        "name": "ProCable USB-C to USB-C 1m",
        "sku": "CBL-USBC-1M",
        "type": "simple",
        "price": "19.99",
        "regular_price": "24.99",
        "sale_price": "19.99",
        "stock_quantity": 180,
        "stock_status": "instock",
        "low_stock_threshold": 50,
        "category_path": ["Cables & Adapters", "USB Cables"],
        "brand": "ProCable",
        "attributes": {
            "length": "1m",
            "type": "USB-C to USB-C",
            "usb_version": "USB 3.2 Gen 2",
            "power_delivery": "100W",
            "data_transfer": "10Gbps",
        },
        "weight": "0.08",
        "dimensions": {"length": "15", "width": "4", "height": "2"},
        "description": "Fast charging and data transfer USB-C cable.",
        "short_description": "USB-C Cable 1m 100W PD",
    },
    {
        "id": 1032,
        "name": "ProCable DisplayPort 1.4 - 2m",
        "sku": "CBL-DP14-2M",
        "type": "simple",
        "price": "22.99",
        "regular_price": "27.99",
        "sale_price": "22.99",
        "stock_quantity": 90,
        "stock_status": "instock",
        "low_stock_threshold": 25,
        "category_path": ["Cables & Adapters", "DisplayPort"],
        "brand": "ProCable",
        "attributes": {
            "length": "2m",
            "version": "DisplayPort 1.4",
            "max_resolution": "8K@60Hz",
            "hdr": True,
        },
        "weight": "0.12",
        "dimensions": {"length": "25", "width": "5", "height": "3"},
        "description": "High-bandwidth DisplayPort cable for gaming and professional displays.",
        "short_description": "DisplayPort 1.4 Cable 2m",
    },
    {
        "id": 1033,
        "name": "USB-C to HDMI Adapter",
        "sku": "ADP-USBC-HDMI",
        "type": "simple",
        "price": "29.99",
        "regular_price": "34.99",
        "sale_price": "29.99",
        "stock_quantity": 70,
        "stock_status": "instock",
        "low_stock_threshold": 20,
        "category_path": ["Cables & Adapters", "Adapters"],
        "brand": "ProCable",
        "attributes": {
            "input": "USB-C",
            "output": "HDMI 2.0",
            "max_resolution": "4K@60Hz",
            "compatibility": ["Windows", "macOS", "ChromeOS"],
        },
        "weight": "0.04",
        "dimensions": {"length": "8", "width": "3", "height": "1"},
        "description": "Connect USB-C devices to HDMI displays.",
        "short_description": "USB-C to HDMI 4K Adapter",
    },
    {
        "id": 1034,
        "name": "Cat6A Ethernet Cable - 5m",
        "sku": "CBL-ETH-CAT6A-5M",
        "type": "simple",
        "price": "18.99",
        "regular_price": "22.99",
        "sale_price": "18.99",
        "stock_quantity": 120,
        "stock_status": "instock",
        "low_stock_threshold": 35,
        "category_path": ["Networking", "Ethernet Cables"],
        "brand": "NetCable",
        "attributes": {
            "length": "5m",
            "category": "Cat6A",
            "speed": "10Gbps",
            "shielded": True,
        },
        "weight": "0.2",
        "dimensions": {"length": "30", "width": "5", "height": "5"},
        "description": "Shielded Cat6A Ethernet cable for high-speed networking.",
        "short_description": "Cat6A Ethernet 5m",
    },
    # USB HUBS & DOCKS (8 products)
    {
        "id": 1040,
        "name": "HubMax USB-C 7-Port Hub",
        "sku": "HUB-USBC-7P",
        "type": "simple",
        "price": "59.99",
        "regular_price": "69.99",
        "sale_price": "59.99",
        "stock_quantity": 40,
        "stock_status": "instock",
        "low_stock_threshold": 12,
        "category_path": ["USB Hubs & Docks", "USB Hubs"],
        "brand": "HubMax",
        "attributes": {
            "ports": ["USB-C x2", "USB-A 3.0 x3", "HDMI", "SD Card"],
            "power_delivery": "100W passthrough",
            "usb_version": "USB 3.2",
            "material": "Aluminum",
        },
        "weight": "0.18",
        "dimensions": {"length": "12", "width": "5", "height": "2"},
        "description": "Versatile USB-C hub with 7 ports and 100W power delivery.",
        "short_description": "7-Port USB-C Hub",
        "related_products": [1041, 1031],
    },
    {
        "id": 1041,
        "name": "DockPro Triple Display Dock",
        "sku": "DOCK-PRO-3D",
        "type": "simple",
        "price": "249.99",
        "regular_price": "299.99",
        "sale_price": "249.99",
        "stock_quantity": 15,
        "stock_status": "instock",
        "low_stock_threshold": 5,
        "category_path": ["USB Hubs & Docks", "Docking Stations"],
        "brand": "DockPro",
        "attributes": {
            "video_outputs": ["HDMI x2", "DisplayPort"],
            "max_displays": 3,
            "max_resolution": "4K@60Hz per display",
            "ports": ["USB-C", "USB-A 3.0 x4", "Ethernet", "Audio"],
            "power_delivery": "100W",
        },
        "weight": "0.45",
        "dimensions": {"length": "18", "width": "8", "height": "3"},
        "description": "Professional docking station supporting triple 4K displays.",
        "short_description": "Triple Display Docking Station",
    },
    {
        "id": 1042,
        "name": "SimpleHub USB 3.0 4-Port",
        "sku": "HUB-USB3-4P",
        "type": "simple",
        "price": "19.99",
        "regular_price": "24.99",
        "sale_price": "19.99",
        "stock_quantity": 95,
        "stock_status": "instock",
        "low_stock_threshold": 30,
        "category_path": ["USB Hubs & Docks", "USB Hubs"],
        "brand": "SimpleHub",
        "attributes": {
            "ports": "USB-A 3.0 x4",
            "usb_version": "USB 3.0",
            "powered": False,
        },
        "weight": "0.08",
        "dimensions": {"length": "8", "width": "4", "height": "2"},
        "description": "Compact 4-port USB 3.0 hub for everyday expansion.",
        "short_description": "4-Port USB 3.0 Hub",
        "bulk_pricing": [
            {"min_qty": 10, "discount_percent": 10},
        ],
    },
    {
        "id": 1043,
        "name": "CardReader Pro All-in-One",
        "sku": "CR-PRO-AIO",
        "type": "simple",
        "price": "34.99",
        "regular_price": "39.99",
        "sale_price": "34.99",
        "stock_quantity": 55,
        "stock_status": "instock",
        "low_stock_threshold": 15,
        "category_path": ["USB Hubs & Docks", "Card Readers"],
        "brand": "CardReader",
        "attributes": {
            "card_types": ["SD", "microSD", "CF", "xD"],
            "connection": "USB-C + USB-A",
            "speed": "UHS-II",
        },
        "weight": "0.06",
        "dimensions": {"length": "10", "width": "6", "height": "2"},
        "description": "Universal card reader supporting all major memory card formats.",
        "short_description": "All-in-One Card Reader",
    },
    # STORAGE (6 products)
    {
        "id": 1050,
        "name": "SpeedDrive Portable SSD 1TB",
        "sku": "SSD-EXT-1TB",
        "type": "simple",
        "price": "129.99",
        "regular_price": "149.99",
        "sale_price": "129.99",
        "stock_quantity": 35,
        "stock_status": "instock",
        "low_stock_threshold": 10,
        "category_path": ["Storage", "External SSD"],
        "brand": "SpeedDrive",
        "attributes": {
            "capacity": "1TB",
            "interface": "USB 3.2 Gen 2",
            "read_speed": "1050 MB/s",
            "write_speed": "1000 MB/s",
            "encryption": "AES 256-bit",
        },
        "weight": "0.1",
        "dimensions": {"length": "10", "width": "6", "height": "1"},
        "description": "Ultra-fast portable SSD with hardware encryption.",
        "short_description": "Portable SSD 1TB",
    },
    {
        "id": 1051,
        "name": "SpeedDrive Portable SSD 2TB",
        "sku": "SSD-EXT-2TB",
        "type": "simple",
        "price": "229.99",
        "regular_price": "269.99",
        "sale_price": "229.99",
        "stock_quantity": 20,
        "stock_status": "instock",
        "low_stock_threshold": 8,
        "category_path": ["Storage", "External SSD"],
        "brand": "SpeedDrive",
        "attributes": {
            "capacity": "2TB",
            "interface": "USB 3.2 Gen 2",
            "read_speed": "1050 MB/s",
            "write_speed": "1000 MB/s",
            "encryption": "AES 256-bit",
        },
        "weight": "0.1",
        "dimensions": {"length": "10", "width": "6", "height": "1"},
        "description": "Ultra-fast 2TB portable SSD with hardware encryption.",
        "short_description": "Portable SSD 2TB",
    },
    {
        "id": 1052,
        "name": "DataVault External HDD 4TB",
        "sku": "HDD-EXT-4TB",
        "type": "simple",
        "price": "119.99",
        "regular_price": "139.99",
        "sale_price": "119.99",
        "stock_quantity": 30,
        "stock_status": "instock",
        "low_stock_threshold": 10,
        "category_path": ["Storage", "External HDD"],
        "brand": "DataVault",
        "attributes": {
            "capacity": "4TB",
            "interface": "USB 3.0",
            "rpm": "5400",
        },
        "weight": "0.25",
        "dimensions": {"length": "12", "width": "8", "height": "2"},
        "description": "High-capacity external hard drive for backups and storage.",
        "short_description": "External HDD 4TB",
    },
    {
        "id": 1053,
        "name": "MiniDrive USB Flash Drive 128GB",
        "sku": "USB-FLASH-128",
        "type": "simple",
        "price": "19.99",
        "regular_price": "24.99",
        "sale_price": "19.99",
        "stock_quantity": 150,
        "stock_status": "instock",
        "low_stock_threshold": 40,
        "category_path": ["Storage", "USB Drives"],
        "brand": "MiniDrive",
        "attributes": {
            "capacity": "128GB",
            "interface": "USB 3.2",
            "speed": "Up to 400 MB/s",
        },
        "weight": "0.01",
        "dimensions": {"length": "4", "width": "2", "height": "1"},
        "description": "High-speed USB flash drive in compact metal housing.",
        "short_description": "USB Flash Drive 128GB",
        "bulk_pricing": [
            {"min_qty": 10, "discount_percent": 10},
            {"min_qty": 50, "discount_percent": 20},
        ],
    },
    # POWER (5 products)
    {
        "id": 1060,
        "name": "PowerMax 20000mAh Power Bank",
        "sku": "PWR-BANK-20K",
        "type": "simple",
        "price": "49.99",
        "regular_price": "59.99",
        "sale_price": "49.99",
        "stock_quantity": 45,
        "stock_status": "instock",
        "low_stock_threshold": 15,
        "category_path": ["Power", "Power Banks"],
        "brand": "PowerMax",
        "attributes": {
            "capacity": "20000mAh",
            "outputs": ["USB-C PD 60W", "USB-A QC 18W x2"],
            "input": "USB-C PD 60W",
            "display": "LED percentage",
        },
        "weight": "0.4",
        "dimensions": {"length": "15", "width": "7", "height": "3"},
        "description": "High-capacity power bank with 60W USB-C fast charging.",
        "short_description": "20000mAh 60W Power Bank",
    },
    {
        "id": 1061,
        "name": "FastCharge 65W GaN Charger",
        "sku": "CHG-GAN-65W",
        "type": "simple",
        "price": "44.99",
        "regular_price": "54.99",
        "sale_price": "44.99",
        "stock_quantity": 65,
        "stock_status": "instock",
        "low_stock_threshold": 20,
        "category_path": ["Power", "Chargers"],
        "brand": "FastCharge",
        "attributes": {
            "power": "65W",
            "ports": ["USB-C PD x2", "USB-A"],
            "technology": "GaN",
            "foldable_plug": True,
        },
        "weight": "0.12",
        "dimensions": {"length": "6", "width": "5", "height": "3"},
        "description": "Compact GaN charger that can charge laptop and phone simultaneously.",
        "short_description": "65W GaN USB-C Charger",
    },
    {
        "id": 1062,
        "name": "SafeGuard 8-Outlet Surge Protector",
        "sku": "SURGE-8OUT",
        "type": "simple",
        "price": "39.99",
        "regular_price": "44.99",
        "sale_price": "39.99",
        "stock_quantity": 50,
        "stock_status": "instock",
        "low_stock_threshold": 15,
        "category_path": ["Power", "Surge Protectors"],
        "brand": "SafeGuard",
        "attributes": {
            "outlets": 8,
            "usb_ports": 2,
            "joules": "2500J",
            "cord_length": "2m",
        },
        "weight": "0.6",
        "dimensions": {"length": "35", "width": "6", "height": "4"},
        "description": "Heavy-duty surge protector with USB charging ports.",
        "short_description": "8-Outlet Surge Protector",
    },
    # WEBCAMS & HEADSETS (5 products)
    {
        "id": 1070,
        "name": "ClearView 1080p Webcam",
        "sku": "CAM-CV-1080",
        "type": "simple",
        "price": "79.99",
        "regular_price": "89.99",
        "sale_price": "79.99",
        "stock_quantity": 40,
        "stock_status": "instock",
        "low_stock_threshold": 12,
        "category_path": ["Peripherals", "Webcams"],
        "brand": "ClearView",
        "attributes": {
            "resolution": "1080p @ 30fps",
            "autofocus": True,
            "microphone": "Dual stereo",
            "fov": "90°",
            "privacy_cover": True,
        },
        "weight": "0.15",
        "dimensions": {"length": "10", "width": "8", "height": "5"},
        "description": "Full HD webcam with dual microphones for clear video calls.",
        "short_description": "1080p HD Webcam",
    },
    {
        "id": 1071,
        "name": "ClearView 4K Pro Webcam",
        "sku": "CAM-CV-4K",
        "type": "simple",
        "price": "169.99",
        "regular_price": "199.99",
        "sale_price": "169.99",
        "stock_quantity": 18,
        "stock_status": "instock",
        "low_stock_threshold": 6,
        "category_path": ["Peripherals", "Webcams"],
        "brand": "ClearView",
        "attributes": {
            "resolution": "4K @ 30fps / 1080p @ 60fps",
            "autofocus": True,
            "microphone": "Quad stereo",
            "fov": "90°",
            "hdr": True,
            "privacy_cover": True,
        },
        "weight": "0.2",
        "dimensions": {"length": "12", "width": "8", "height": "6"},
        "description": "Professional 4K webcam with HDR for streaming and meetings.",
        "short_description": "4K HDR Pro Webcam",
    },
    {
        "id": 1072,
        "name": "SoundPro Wireless Headset",
        "sku": "HS-SP-WL",
        "type": "simple",
        "price": "129.99",
        "regular_price": "149.99",
        "sale_price": "129.99",
        "stock_quantity": 35,
        "stock_status": "instock",
        "low_stock_threshold": 10,
        "category_path": ["Peripherals", "Headsets"],
        "brand": "SoundPro",
        "attributes": {
            "type": "Over-ear",
            "connection": "Bluetooth 5.2 + 2.4GHz",
            "battery_life": "40 hours",
            "anc": True,
            "microphone": "Boom + Built-in",
        },
        "weight": "0.28",
        "dimensions": {"length": "20", "width": "18", "height": "8"},
        "description": "Professional wireless headset with ANC for office and gaming.",
        "short_description": "Wireless ANC Headset",
    },
    {
        "id": 1073,
        "name": "BasicSound USB Headset",
        "sku": "HS-BASIC-USB",
        "type": "simple",
        "price": "39.99",
        "regular_price": "44.99",
        "sale_price": "39.99",
        "stock_quantity": 80,
        "stock_status": "instock",
        "low_stock_threshold": 25,
        "category_path": ["Peripherals", "Headsets"],
        "brand": "BasicSound",
        "attributes": {
            "type": "On-ear",
            "connection": "USB-A",
            "microphone": "Boom with noise cancellation",
            "inline_controls": True,
        },
        "weight": "0.18",
        "dimensions": {"length": "18", "width": "16", "height": "6"},
        "description": "Comfortable USB headset for calls and video conferencing.",
        "short_description": "USB Headset with Mic",
        "bulk_pricing": [
            {"min_qty": 10, "discount_percent": 10},
            {"min_qty": 25, "discount_percent": 15},
        ],
    },
    # LOW STOCK / OUT OF STOCK items
    {
        "id": 1080,
        "name": "ProView 32-inch Curved Gaming Monitor",
        "sku": "MON-PV32C-G",
        "type": "simple",
        "price": "599.99",
        "regular_price": "699.99",
        "sale_price": "599.99",
        "stock_quantity": 3,
        "stock_status": "lowstock",
        "low_stock_threshold": 5,
        "category_path": ["Monitors", "Gaming Monitors"],
        "brand": "ProView",
        "attributes": {
            "screen_size": "32 inches",
            "resolution": "2560x1440",
            "refresh_rate": "240Hz",
            "panel_type": "VA",
            "response_time": "1ms",
            "curvature": "1000R",
        },
        "weight": "7.8",
        "dimensions": {"length": "72", "width": "50", "height": "22"},
        "description": "Premium curved gaming monitor with 240Hz for competitive gaming.",
        "short_description": '32" Curved 240Hz Gaming Monitor',
        "reorder_pending": True,
        "expected_restock": "2024-04-15",
    },
    {
        "id": 1081,
        "name": "MechPro TKL Tournament Keyboard",
        "sku": "KB-MECH-TKL",
        "type": "simple",
        "price": "159.99",
        "regular_price": "179.99",
        "sale_price": "159.99",
        "stock_quantity": 0,
        "stock_status": "outofstock",
        "low_stock_threshold": 8,
        "category_path": ["Peripherals", "Keyboards", "Mechanical"],
        "brand": "MechPro",
        "attributes": {
            "layout": "TKL (Tenkeyless)",
            "switch_type": "Speed Silver",
            "backlight": "RGB per-key",
            "polling_rate": "8000Hz",
        },
        "weight": "0.75",
        "dimensions": {"length": "36", "width": "14", "height": "4"},
        "description": "Tournament-grade TKL keyboard with 8000Hz polling rate.",
        "short_description": "TKL Tournament Keyboard",
        "backorder_allowed": True,
        "expected_restock": "2024-04-20",
    },
    {
        "id": 1082,
        "name": "UltraLight Gaming Mouse",
        "sku": "MS-ULTRA-LIGHT",
        "type": "simple",
        "price": "89.99",
        "regular_price": "99.99",
        "sale_price": "89.99",
        "stock_quantity": 2,
        "stock_status": "lowstock",
        "low_stock_threshold": 10,
        "category_path": ["Peripherals", "Mice", "Gaming"],
        "brand": "UltraLight",
        "attributes": {
            "weight": "58g",
            "sensor": "Optical 25600 DPI",
            "honeycomb_design": True,
            "paracord_cable": True,
        },
        "weight": "0.06",
        "dimensions": {"length": "12", "width": "6", "height": "4"},
        "description": "Ultra-lightweight gaming mouse with honeycomb shell design.",
        "short_description": "58g Ultralight Gaming Mouse",
    },
]


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class ProductAttribute:
    """Product attribute."""

    name: str
    value: Any
    visible: bool = True
    variation: bool = False


@dataclass
class BulkPricing:
    """Bulk pricing tier."""

    min_quantity: int
    discount_percent: float
    price_per_unit: Optional[float] = None


@dataclass
class Product:
    """Product representation."""

    id: int
    name: str
    sku: str
    product_type: str
    price: float
    regular_price: float
    sale_price: Optional[float]
    stock_quantity: int
    stock_status: StockStatus
    low_stock_threshold: int
    category_path: List[str]
    brand: str
    attributes: Dict[str, Any]
    description: str
    short_description: str
    weight: Optional[float] = None
    dimensions: Optional[Dict[str, str]] = None
    related_products: List[int] = field(default_factory=list)
    upsell_products: List[int] = field(default_factory=list)
    bulk_pricing: List[BulkPricing] = field(default_factory=list)
    variations: List[Dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        """Create Product from dictionary."""
        bulk_pricing = []
        for bp in data.get("bulk_pricing", []):
            bulk_pricing.append(
                BulkPricing(
                    min_quantity=bp["min_qty"],
                    discount_percent=bp["discount_percent"],
                )
            )

        return cls(
            id=data["id"],
            name=data["name"],
            sku=data["sku"],
            product_type=data.get("type", "simple"),
            price=float(data["price"]),
            regular_price=float(data["regular_price"]),
            sale_price=float(data["sale_price"]) if data.get("sale_price") else None,
            stock_quantity=data.get("stock_quantity", 0),
            stock_status=StockStatus(data.get("stock_status", "instock")),
            low_stock_threshold=data.get("low_stock_threshold", 10),
            category_path=data.get("category_path", []),
            brand=data.get("brand", ""),
            attributes=data.get("attributes", {}),
            description=data.get("description", ""),
            short_description=data.get("short_description", ""),
            weight=float(data["weight"]) if data.get("weight") else None,
            dimensions=data.get("dimensions"),
            related_products=data.get("related_products", []),
            upsell_products=data.get("upsell_products", []),
            bulk_pricing=bulk_pricing,
            variations=data.get("variations", []),
        )

    @property
    def is_on_sale(self) -> bool:
        """Check if product is on sale."""
        return self.sale_price is not None and self.sale_price < self.regular_price

    @property
    def discount_percent(self) -> int:
        """Calculate discount percentage."""
        if not self.is_on_sale:
            return 0
        return int((1 - self.sale_price / self.regular_price) * 100)

    @property
    def needs_reorder(self) -> bool:
        """Check if product needs reordering."""
        return self.stock_quantity <= self.low_stock_threshold

    @property
    def full_category(self) -> str:
        """Get full category path as string."""
        return " > ".join(self.category_path)

    def get_bulk_price(self, quantity: int) -> float:
        """Get price per unit for bulk order."""
        applicable_tier = None
        for tier in sorted(
            self.bulk_pricing, key=lambda x: x.min_quantity, reverse=True
        ):
            if quantity >= tier.min_quantity:
                applicable_tier = tier
                break

        if applicable_tier:
            return self.price * (1 - applicable_tier.discount_percent / 100)
        return self.price


@dataclass
class Category:
    """Category representation."""

    id: int
    name: str
    slug: str
    parent_id: Optional[int] = None
    children: List["Category"] = field(default_factory=list)
    product_count: int = 0


@dataclass
class StockAlert:
    """Stock alert for reorder."""

    product_id: int
    product_name: str
    sku: str
    current_stock: int
    threshold: int
    status: str
    suggested_reorder_qty: int = 0


@dataclass
class PriceUpdate:
    """Price update record."""

    product_id: int
    old_price: float
    new_price: float
    price_type: PriceType
    updated_at: datetime
    reason: str = ""


@dataclass
class ProductComparison:
    """Product comparison result."""

    products: List[Product]
    common_attributes: List[str]
    differences: Dict[str, List[Any]]
    recommendation: Optional[str] = None


# =============================================================================
# CATALOG MANAGER
# =============================================================================


class ElectronicsCatalogManager:
    """
    Electronics catalog management system.

    Capabilities:
    - Product CRUD operations
    - Category hierarchy management
    - Price management (regular, sale, bulk)
    - Stock monitoring and alerts
    - Product comparisons
    """

    def __init__(self, demo_mode: bool = True):
        self.demo_mode = demo_mode
        self.products: Dict[int, Product] = {}
        self.categories: Dict[int, Category] = {}
        self.price_history: List[PriceUpdate] = []

        if demo_mode:
            self._load_demo_data()

    def _load_demo_data(self):
        """Load demo product data."""
        for data in DEMO_PRODUCTS:
            product = Product.from_dict(data)
            self.products[product.id] = product

    # =========================================================================
    # PRODUCT OPERATIONS
    # =========================================================================

    def get_product(self, product_id: int) -> Optional[Product]:
        """Get product by ID."""
        return self.products.get(product_id)

    def get_product_by_sku(self, sku: str) -> Optional[Product]:
        """Get product by SKU."""
        for product in self.products.values():
            if product.sku.lower() == sku.lower():
                return product
        return None

    def search_products(
        self,
        query: str = "",
        category: str = "",
        brand: str = "",
        min_price: float = 0,
        max_price: float = float("inf"),
        in_stock_only: bool = False,
        on_sale_only: bool = False,
    ) -> List[Product]:
        """Search products with filters."""
        results = []
        query_lower = query.lower()

        for product in self.products.values():
            # Text search
            if query and not any(
                [
                    query_lower in product.name.lower(),
                    query_lower in product.sku.lower(),
                    query_lower in product.description.lower(),
                    query_lower in product.brand.lower(),
                ]
            ):
                continue

            # Category filter
            if category and not any(
                cat.lower() == category.lower() for cat in product.category_path
            ):
                continue

            # Brand filter
            if brand and product.brand.lower() != brand.lower():
                continue

            # Price filter
            if not (min_price <= product.price <= max_price):
                continue

            # Stock filter
            if in_stock_only and product.stock_status in [
                StockStatus.OUT_OF_STOCK,
                StockStatus.DISCONTINUED,
            ]:
                continue

            # Sale filter
            if on_sale_only and not product.is_on_sale:
                continue

            results.append(product)

        return results

    def get_products_by_category(self, category: str) -> List[Product]:
        """Get all products in a category (including subcategories)."""
        return [p for p in self.products.values() if category in p.category_path]

    def get_related_products(self, product_id: int) -> List[Product]:
        """Get related products."""
        product = self.get_product(product_id)
        if not product:
            return []

        related = []
        for rel_id in product.related_products:
            rel_product = self.get_product(rel_id)
            if rel_product:
                related.append(rel_product)
        return related

    def get_upsell_products(self, product_id: int) -> List[Product]:
        """Get upsell product suggestions."""
        product = self.get_product(product_id)
        if not product:
            return []

        upsells = []
        for up_id in product.upsell_products:
            up_product = self.get_product(up_id)
            if up_product:
                upsells.append(up_product)
        return upsells

    # =========================================================================
    # CATEGORY OPERATIONS
    # =========================================================================

    def get_category_hierarchy(self) -> Dict:
        """Get full category hierarchy."""
        return CATEGORY_HIERARCHY

    def get_category_tree_display(self, hierarchy: Dict = None, level: int = 0) -> str:
        """Get category tree as formatted string."""
        if hierarchy is None:
            hierarchy = CATEGORY_HIERARCHY

        lines = []
        for name, data in hierarchy.items():
            indent = "  " * level
            product_count = len(self.get_products_by_category(name))
            lines.append(
                f"{indent}{'└─' if level > 0 else '📁'} {name} ({product_count})"
            )

            if data.get("children"):
                lines.append(
                    self.get_category_tree_display(data["children"], level + 1)
                )

        return "\n".join(lines)

    def get_brands(self) -> List[str]:
        """Get list of all brands."""
        brands = set()
        for product in self.products.values():
            if product.brand:
                brands.add(product.brand)
        return sorted(brands)

    # =========================================================================
    # PRICE MANAGEMENT
    # =========================================================================

    def update_price(
        self,
        product_id: int,
        new_price: float,
        price_type: PriceType = PriceType.REGULAR,
        reason: str = "",
    ) -> bool:
        """Update product price."""
        product = self.get_product(product_id)
        if not product:
            return False

        old_price = (
            product.price
            if price_type == PriceType.REGULAR
            else (product.sale_price or product.price)
        )

        # Record history
        self.price_history.append(
            PriceUpdate(
                product_id=product_id,
                old_price=old_price,
                new_price=new_price,
                price_type=price_type,
                updated_at=datetime.now(),
                reason=reason,
            )
        )

        # Update price
        if price_type == PriceType.REGULAR:
            product.regular_price = new_price
            if not product.sale_price:
                product.price = new_price
        elif price_type == PriceType.SALE:
            product.sale_price = new_price
            product.price = new_price

        return True

    def set_sale_price(
        self, product_id: int, sale_price: float, reason: str = ""
    ) -> bool:
        """Set sale price for a product."""
        return self.update_price(product_id, sale_price, PriceType.SALE, reason)

    def end_sale(self, product_id: int) -> bool:
        """End sale and revert to regular price."""
        product = self.get_product(product_id)
        if not product:
            return False

        product.sale_price = None
        product.price = product.regular_price
        return True

    def get_bulk_price(self, product_id: int, quantity: int) -> Optional[float]:
        """Calculate bulk price for quantity."""
        product = self.get_product(product_id)
        if not product:
            return None
        return product.get_bulk_price(quantity)

    def get_products_on_sale(self) -> List[Product]:
        """Get all products currently on sale."""
        return [p for p in self.products.values() if p.is_on_sale]

    # =========================================================================
    # STOCK MANAGEMENT
    # =========================================================================

    def get_stock_alerts(self) -> List[StockAlert]:
        """Get products needing reorder."""
        alerts = []
        for product in self.products.values():
            if product.needs_reorder:
                status = "OUT_OF_STOCK" if product.stock_quantity == 0 else "LOW_STOCK"
                suggested_qty = max(product.low_stock_threshold * 3, 10)

                alerts.append(
                    StockAlert(
                        product_id=product.id,
                        product_name=product.name,
                        sku=product.sku,
                        current_stock=product.stock_quantity,
                        threshold=product.low_stock_threshold,
                        status=status,
                        suggested_reorder_qty=suggested_qty,
                    )
                )

        # Sort by urgency (out of stock first, then by stock level)
        alerts.sort(key=lambda x: (x.current_stock, x.product_name))
        return alerts

    def update_stock(
        self, product_id: int, quantity: int, absolute: bool = False
    ) -> bool:
        """Update stock quantity."""
        product = self.get_product(product_id)
        if not product:
            return False

        if absolute:
            product.stock_quantity = quantity
        else:
            product.stock_quantity += quantity

        # Update status
        if product.stock_quantity <= 0:
            product.stock_status = StockStatus.OUT_OF_STOCK
        elif product.stock_quantity <= product.low_stock_threshold:
            product.stock_status = StockStatus.LOW_STOCK
        else:
            product.stock_status = StockStatus.IN_STOCK

        return True

    def get_out_of_stock(self) -> List[Product]:
        """Get out of stock products."""
        return [
            p
            for p in self.products.values()
            if p.stock_status == StockStatus.OUT_OF_STOCK
        ]

    def get_low_stock(self) -> List[Product]:
        """Get low stock products."""
        return [
            p for p in self.products.values() if p.stock_status == StockStatus.LOW_STOCK
        ]

    # =========================================================================
    # PRODUCT COMPARISON
    # =========================================================================

    def compare_products(self, product_ids: List[int]) -> Optional[ProductComparison]:
        """Compare multiple products side by side."""
        products = []
        for pid in product_ids:
            product = self.get_product(pid)
            if product:
                products.append(product)

        if len(products) < 2:
            return None

        # Find common attributes
        all_attrs = set()
        for product in products:
            all_attrs.update(product.attributes.keys())

        common_attrs = list(all_attrs)

        # Build differences table
        differences = {}
        differences["Price"] = [f"${p.price:.2f}" for p in products]
        differences["Brand"] = [p.brand for p in products]
        differences["Stock"] = [p.stock_status.value for p in products]

        for attr in common_attrs:
            differences[attr] = [p.attributes.get(attr, "N/A") for p in products]

        # Generate recommendation
        recommendation = None
        if products[0].category_path and "Monitors" in products[0].category_path[0]:
            best = min(
                products,
                key=lambda p: (
                    p.price
                    if p.stock_status != StockStatus.OUT_OF_STOCK
                    else float("inf")
                ),
            )
            if best.stock_status != StockStatus.OUT_OF_STOCK:
                recommendation = f"Best value: {best.name} at ${best.price:.2f}"

        return ProductComparison(
            products=products,
            common_attributes=common_attrs,
            differences=differences,
            recommendation=recommendation,
        )

    # =========================================================================
    # REPORTING
    # =========================================================================

    def get_catalog_summary(self) -> Dict:
        """Get catalog statistics."""
        total = len(self.products)
        in_stock = len(
            [
                p
                for p in self.products.values()
                if p.stock_status == StockStatus.IN_STOCK
            ]
        )
        low_stock = len(
            [
                p
                for p in self.products.values()
                if p.stock_status == StockStatus.LOW_STOCK
            ]
        )
        out_of_stock = len(
            [
                p
                for p in self.products.values()
                if p.stock_status == StockStatus.OUT_OF_STOCK
            ]
        )
        on_sale = len(self.get_products_on_sale())

        return {
            "total_products": total,
            "in_stock": in_stock,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "on_sale": on_sale,
            "brands": len(self.get_brands()),
        }


# =============================================================================
# TOOL DEFINITIONS FOR AGENTIC-BRAIN
# =============================================================================

CATALOG_TOOLS = [
    {
        "name": "search_products",
        "description": "Search the electronics catalog with filters",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (name, SKU, description)",
                },
                "category": {"type": "string", "description": "Filter by category"},
                "brand": {"type": "string", "description": "Filter by brand"},
                "min_price": {"type": "number", "description": "Minimum price"},
                "max_price": {"type": "number", "description": "Maximum price"},
                "in_stock_only": {
                    "type": "boolean",
                    "description": "Only show in-stock items",
                },
                "on_sale_only": {
                    "type": "boolean",
                    "description": "Only show items on sale",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_product_details",
        "description": "Get detailed information about a specific product",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "integer", "description": "Product ID"},
                "sku": {
                    "type": "string",
                    "description": "Product SKU (alternative to ID)",
                },
            },
        },
    },
    {
        "name": "get_category_tree",
        "description": "Get the full category hierarchy",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "check_stock_alerts",
        "description": "Get list of products needing reorder",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "compare_products",
        "description": "Compare multiple products side by side",
        "parameters": {
            "type": "object",
            "properties": {
                "product_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of product IDs to compare",
                },
            },
            "required": ["product_ids"],
        },
    },
    {
        "name": "update_price",
        "description": "Update product price (regular or sale)",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "integer", "description": "Product ID"},
                "new_price": {"type": "number", "description": "New price"},
                "price_type": {
                    "type": "string",
                    "enum": ["regular", "sale"],
                    "description": "Type of price update",
                },
                "reason": {"type": "string", "description": "Reason for price change"},
            },
            "required": ["product_id", "new_price"],
        },
    },
    {
        "name": "update_stock",
        "description": "Update product stock quantity",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "integer", "description": "Product ID"},
                "quantity": {
                    "type": "integer",
                    "description": "Quantity change (positive to add, negative to subtract)",
                },
                "absolute": {
                    "type": "boolean",
                    "description": "If true, set absolute quantity instead of adjusting",
                },
            },
            "required": ["product_id", "quantity"],
        },
    },
    {
        "name": "get_bulk_price",
        "description": "Calculate bulk pricing for a quantity",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "integer", "description": "Product ID"},
                "quantity": {"type": "integer", "description": "Quantity to order"},
            },
            "required": ["product_id", "quantity"],
        },
    },
    {
        "name": "get_catalog_summary",
        "description": "Get catalog statistics and overview",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


SYSTEM_PROMPT = """You are an Electronics Catalog Manager assistant for a WooCommerce store.

Your role is to help manage the electronics product catalog, including:
- Searching and browsing products
- Managing product information and attributes
- Setting and updating prices (regular, sale, bulk)
- Monitoring stock levels and generating reorder alerts
- Comparing products to help with purchasing decisions

The store sells:
- Monitors (gaming, office, ultrawide, 4K)
- Keyboards (mechanical, wireless, ergonomic)
- Mice (gaming, wireless, ergonomic)
- Cables & Adapters (HDMI, USB, DisplayPort)
- USB Hubs & Docking Stations
- Storage (SSD, HDD, USB drives)
- Power accessories (power banks, chargers)
- Webcams & Headsets

When helping with:
1. **Product Search**: Use filters to narrow results
2. **Stock Alerts**: Prioritize out-of-stock items, suggest reorder quantities
3. **Price Updates**: Always record reason for audit trail
4. **Comparisons**: Highlight key differences and make recommendations

Always be helpful and provide detailed information about products when asked.
"""


# =============================================================================
# INTERACTIVE ASSISTANT
# =============================================================================


class CatalogAssistant:
    """Interactive catalog assistant."""

    def __init__(self, demo_mode: bool = True):
        self.catalog = ElectronicsCatalogManager(demo_mode=demo_mode)
        self.conversation_history: List[Dict] = []

    async def process_message(self, message: str) -> str:
        """Process user message and return response."""
        message_lower = message.lower()

        self.conversation_history.append(
            {
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Route to handlers
        if any(
            word in message_lower
            for word in ["search", "find", "looking for", "show me"]
        ):
            response = await self._handle_search(message)
        elif any(
            word in message_lower for word in ["compare", "versus", "vs", "difference"]
        ):
            response = await self._handle_compare(message)
        elif any(
            word in message_lower for word in ["stock", "inventory", "reorder", "alert"]
        ):
            response = await self._handle_stock(message)
        elif any(
            word in message_lower for word in ["price", "sale", "discount", "bulk"]
        ):
            response = await self._handle_price(message)
        elif any(
            word in message_lower for word in ["category", "categories", "browse"]
        ):
            response = await self._handle_categories()
        elif any(
            word in message_lower
            for word in ["summary", "overview", "stats", "statistics"]
        ):
            response = await self._handle_summary()
        elif any(word in message_lower for word in ["detail", "info", "about", "sku"]):
            response = await self._handle_product_detail(message)
        elif any(word in message_lower for word in ["help", "commands"]):
            response = self._get_help()
        else:
            response = await self._handle_general(message)

        self.conversation_history.append(
            {
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return response

    async def _handle_search(self, message: str) -> str:
        """Handle product search."""
        # Parse search query
        query = ""
        category = ""
        in_stock_only = "in stock" in message.lower()
        on_sale_only = "sale" in message.lower() or "discount" in message.lower()

        # Extract keywords
        keywords = [
            "monitors",
            "keyboards",
            "mice",
            "mouse",
            "cables",
            "hubs",
            "storage",
            "webcams",
            "headsets",
        ]
        for kw in keywords:
            if kw in message.lower():
                if kw == "monitors":
                    category = "Monitors"
                elif kw in ["keyboards"]:
                    category = "Keyboards"
                elif kw in ["mice", "mouse"]:
                    category = "Mice"
                elif kw == "cables":
                    category = "Cables & Adapters"
                elif kw == "hubs":
                    category = "USB Hubs"
                break

        # Clean query
        for word in [
            "search",
            "find",
            "show",
            "me",
            "looking",
            "for",
            "in",
            "stock",
            "on",
            "sale",
        ]:
            message = message.lower().replace(word, "")
        query = message.strip()

        results = self.catalog.search_products(
            query=query,
            category=category,
            in_stock_only=in_stock_only,
            on_sale_only=on_sale_only,
        )

        if not results:
            return "No products found matching your criteria. Try a different search or browse categories."

        lines = [f"🔍 **Found {len(results)} products:**\n"]
        for product in results[:10]:
            stock_emoji = {
                StockStatus.IN_STOCK: "✅",
                StockStatus.LOW_STOCK: "⚠️",
                StockStatus.OUT_OF_STOCK: "❌",
            }.get(product.stock_status, "❓")

            sale_badge = (
                f" 🏷️ {product.discount_percent}% OFF" if product.is_on_sale else ""
            )

            lines.append(f"{stock_emoji} **{product.name}**{sale_badge}")
            lines.append(
                f"   SKU: {product.sku} | ${product.price:.2f} | {product.full_category}"
            )
            lines.append("")

        if len(results) > 10:
            lines.append(
                f"... and {len(results) - 10} more. Refine your search for fewer results."
            )

        return "\n".join(lines)

    async def _handle_compare(self, message: str) -> str:
        """Handle product comparison."""
        # Extract product IDs from message
        ids = re.findall(r"\b(\d{4})\b", message)

        if len(ids) < 2:
            # Try to find by keywords
            return """To compare products, please provide 2 or more product IDs.

Example: "Compare 1001 and 1002"

Or specify what you'd like to compare:
- "Compare gaming monitors"
- "Compare mechanical keyboards" """

        product_ids = [int(id) for id in ids[:4]]  # Max 4 products
        comparison = self.catalog.compare_products(product_ids)

        if not comparison:
            return "Couldn't find those products. Please check the IDs and try again."

        lines = ["📊 **Product Comparison**\n"]

        # Header row
        header = (
            "| Attribute | "
            + " | ".join(p.name[:20] for p in comparison.products)
            + " |"
        )
        separator = "|" + "|".join(["---"] * (len(comparison.products) + 1)) + "|"
        lines.extend([header, separator])

        # Data rows
        for attr, values in comparison.differences.items():
            row = f"| {attr} | " + " | ".join(str(v)[:20] for v in values) + " |"
            lines.append(row)

        if comparison.recommendation:
            lines.append(f"\n💡 **Recommendation:** {comparison.recommendation}")

        return "\n".join(lines)

    async def _handle_stock(self, message: str) -> str:
        """Handle stock queries."""
        alerts = self.catalog.get_stock_alerts()

        if not alerts:
            return "✅ All products are well-stocked. No reorder alerts."

        lines = [f"🚨 **Stock Alerts ({len(alerts)} items need attention)**\n"]

        out_of_stock = [a for a in alerts if a.status == "OUT_OF_STOCK"]
        low_stock = [a for a in alerts if a.status == "LOW_STOCK"]

        if out_of_stock:
            lines.append("**❌ OUT OF STOCK:**")
            for alert in out_of_stock:
                lines.append(f"  • {alert.product_name} ({alert.sku})")
                lines.append(
                    f"    Suggested reorder: {alert.suggested_reorder_qty} units"
                )
            lines.append("")

        if low_stock:
            lines.append("**⚠️ LOW STOCK:**")
            for alert in low_stock:
                lines.append(f"  • {alert.product_name} ({alert.sku})")
                lines.append(
                    f"    Current: {alert.current_stock} | Threshold: {alert.threshold}"
                )
            lines.append("")

        return "\n".join(lines)

    async def _handle_price(self, message: str) -> str:
        """Handle price queries."""
        if "sale" in message.lower():
            on_sale = self.catalog.get_products_on_sale()

            if not on_sale:
                return "No products currently on sale."

            lines = [f"🏷️ **Products on Sale ({len(on_sale)} items)**\n"]
            for product in on_sale[:10]:
                lines.append(f"🔥 **{product.name}**")
                lines.append(
                    f"   ~~${product.regular_price:.2f}~~ **${product.price:.2f}** - Save {product.discount_percent}%!"
                )
                lines.append("")

            return "\n".join(lines)

        if "bulk" in message.lower():
            # Find product ID in message
            match = re.search(r"\b(\d{4})\b", message)
            qty_match = re.search(r"(\d+)\s*(?:units?|qty|quantity)", message.lower())

            if match and qty_match:
                product_id = int(match.group(1))
                quantity = int(qty_match.group(1))
                price = self.catalog.get_bulk_price(product_id, quantity)
                product = self.catalog.get_product(product_id)

                if price and product:
                    total = price * quantity
                    savings = (product.price - price) * quantity
                    return f"""💰 **Bulk Pricing for {product.name}**

Quantity: {quantity} units
Unit Price: ${price:.2f} (regular: ${product.price:.2f})
Total: ${total:.2f}
You Save: ${savings:.2f}"""

            return "To calculate bulk pricing, specify product ID and quantity. Example: 'bulk price for 1013, 25 units'"

        return "Would you like to see products on sale or calculate bulk pricing?"

    async def _handle_categories(self) -> str:
        """Handle category browsing."""
        tree = self.catalog.get_category_tree_display()
        summary = self.catalog.get_catalog_summary()

        return f"""📁 **Category Hierarchy**

{tree}

**Catalog Stats:**
- Total Products: {summary['total_products']}
- Brands: {summary['brands']}"""

    async def _handle_summary(self) -> str:
        """Handle catalog summary."""
        summary = self.catalog.get_catalog_summary()

        return f"""📊 **Catalog Summary**

📦 **Inventory:**
- Total Products: {summary['total_products']}
- In Stock: {summary['in_stock']} ✅
- Low Stock: {summary['low_stock']} ⚠️
- Out of Stock: {summary['out_of_stock']} ❌

🏷️ **Pricing:**
- Products on Sale: {summary['on_sale']}

🏢 **Brands:** {summary['brands']}"""

    async def _handle_product_detail(self, message: str) -> str:
        """Handle product detail request."""
        # Try to find product ID or SKU
        id_match = re.search(r"\b(\d{4})\b", message)
        sku_match = re.search(r"([A-Z]{2,4}-[A-Z0-9-]+)", message.upper())

        product = None
        if id_match:
            product = self.catalog.get_product(int(id_match.group(1)))
        elif sku_match:
            product = self.catalog.get_product_by_sku(sku_match.group(1))

        if not product:
            return "Please specify a product ID or SKU. Example: 'details for 1001' or 'info about MON-PV27G-165'"

        lines = [
            f"📦 **{product.name}**",
            f"SKU: {product.sku} | Brand: {product.brand}",
            f"Category: {product.full_category}",
            "",
            "**Pricing:**",
            f"  Current: ${product.price:.2f}",
        ]

        if product.is_on_sale:
            lines.append(
                f"  Regular: ~~${product.regular_price:.2f}~~ ({product.discount_percent}% OFF)"
            )

        if product.bulk_pricing:
            lines.append("  Bulk discounts available!")

        stock_status = {
            StockStatus.IN_STOCK: f"✅ In Stock ({product.stock_quantity} units)",
            StockStatus.LOW_STOCK: f"⚠️ Low Stock ({product.stock_quantity} units)",
            StockStatus.OUT_OF_STOCK: "❌ Out of Stock",
        }.get(product.stock_status, product.stock_status.value)

        lines.extend(
            [
                "",
                f"**Stock:** {stock_status}",
                "",
                "**Specifications:**",
            ]
        )

        for key, value in product.attributes.items():
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            lines.append(f"  • {key.replace('_', ' ').title()}: {value}")

        lines.extend(
            [
                "",
                "**Description:**",
                product.description,
            ]
        )

        return "\n".join(lines)

    async def _handle_general(self, message: str) -> str:
        """Handle general queries."""
        # Try a product search as fallback
        results = self.catalog.search_products(query=message)

        if results:
            return await self._handle_search(f"search {message}")

        return f"""I can help you with:
{self._get_help()}

What would you like to know?"""

    def _get_help(self) -> str:
        """Return help text."""
        return """**Available Commands:**

🔍 **Search** - "find gaming monitors", "search keyboard"
📊 **Compare** - "compare 1001 and 1002"
📦 **Stock** - "check stock alerts", "low stock items"
🏷️ **Pricing** - "products on sale", "bulk price for 1013, 25 units"
📁 **Browse** - "show categories", "browse catalog"
ℹ️ **Details** - "details for 1001", "info about KB-MECH-RGB"
📈 **Summary** - "catalog overview", "inventory stats"

Just ask in natural language!"""


# =============================================================================
# DEMO AND INTERACTIVE MODES
# =============================================================================


async def demo():
    """Run demonstration of catalog features."""
    print("=" * 70)
    print("WooCommerce Electronics Catalog Manager - DEMO")
    print("=" * 70)
    print("\n🖥️  Electronics Retail Store Catalog System")
    print("📦 Managing 50+ products across 8 categories\n")

    assistant = CatalogAssistant(demo_mode=True)

    demo_queries = [
        "Show me the catalog summary",
        "Search for gaming monitors",
        "Check stock alerts",
        "What's on sale?",
        "Details for product 1001",
        "Compare 1001 1002 1003",
        "Show categories",
        "Bulk price for 1013, 25 units",
    ]

    for query in demo_queries:
        print(f"👤 User: {query}")
        print("-" * 50)
        response = await assistant.process_message(query)
        print(f"🤖 Assistant:\n{response}")
        print("=" * 70)
        print()


async def interactive():
    """Run interactive catalog assistant."""
    print("=" * 70)
    print("WooCommerce Electronics Catalog Manager")
    print("=" * 70)
    print("\n🖥️  Type 'help' for commands, 'quit' to exit\n")

    assistant = CatalogAssistant(demo_mode=True)

    while True:
        try:
            user_input = input("👤 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "bye"]:
                print("👋 Goodbye!")
                break

            response = await assistant.process_message(user_input)
            print(f"\n🤖 Assistant:\n{response}\n")

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        asyncio.run(interactive())
    else:
        asyncio.run(demo())
