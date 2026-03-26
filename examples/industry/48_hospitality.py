#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Restaurant & Hospitality Bot
=============================

An AI assistant for restaurant operations including menu browsing,
reservations, dietary accommodations, and order management.

Features:
- Menu browsing with search
- Dietary restriction filtering
- Reservation management
- Order taking and modifications
- Recommendations based on preferences

Run:
    python examples/48_hospitality.py

Note:
    This is a demonstration with a simulated restaurant.
    In production, integrate with real POS and reservation systems.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any
import random

from agentic_brain import Agent

# ============================================================================
# Demo Restaurant Data
# ============================================================================

RESTAURANT_INFO = {
    "name": "The Garden Bistro",
    "cuisine": "Contemporary American",
    "address": "123 Main Street, Downtown",
    "phone": "(555) 123-4567",
    "hours": {
        "Monday": "11:00 AM - 9:00 PM",
        "Tuesday": "11:00 AM - 9:00 PM",
        "Wednesday": "11:00 AM - 9:00 PM",
        "Thursday": "11:00 AM - 10:00 PM",
        "Friday": "11:00 AM - 11:00 PM",
        "Saturday": "10:00 AM - 11:00 PM",
        "Sunday": "10:00 AM - 9:00 PM",
    },
    "features": [
        "Outdoor Seating",
        "Full Bar",
        "Private Dining",
        "Takeout",
        "Delivery",
    ],
}

MENU = {
    "appetizers": [
        {
            "id": "APP01",
            "name": "Garden Bruschetta",
            "description": "Toasted sourdough with heirloom tomatoes, fresh basil, and balsamic glaze",
            "price": 12.95,
            "dietary": ["vegetarian", "vegan-optional"],
            "allergens": ["gluten", "soy"],
            "popular": True,
        },
        {
            "id": "APP02",
            "name": "Crispy Calamari",
            "description": "Lightly fried squid with spicy marinara and lemon aioli",
            "price": 15.95,
            "dietary": [],
            "allergens": ["shellfish", "gluten", "eggs"],
            "popular": True,
        },
        {
            "id": "APP03",
            "name": "Spinach Artichoke Dip",
            "description": "Creamy blend of spinach, artichokes, and three cheeses with warm pita",
            "price": 13.95,
            "dietary": ["vegetarian", "gluten-free-optional"],
            "allergens": ["dairy", "gluten"],
            "popular": False,
        },
        {
            "id": "APP04",
            "name": "Tuna Tartare",
            "description": "Sushi-grade tuna with avocado, sesame, and wonton crisps",
            "price": 18.95,
            "dietary": ["gluten-free-optional"],
            "allergens": ["fish", "sesame", "gluten", "soy"],
            "popular": True,
        },
        {
            "id": "APP05",
            "name": "Loaded Potato Skins",
            "description": "Crispy potato skins with cheddar, bacon, and sour cream",
            "price": 11.95,
            "dietary": ["gluten-free"],
            "allergens": ["dairy"],
            "popular": False,
        },
    ],
    "salads": [
        {
            "id": "SAL01",
            "name": "Garden House Salad",
            "description": "Mixed greens, cherry tomatoes, cucumber, carrots with house vinaigrette",
            "price": 9.95,
            "dietary": ["vegetarian", "vegan", "gluten-free"],
            "allergens": [],
            "popular": False,
        },
        {
            "id": "SAL02",
            "name": "Classic Caesar",
            "description": "Romaine, parmesan, croutons, and house-made Caesar dressing",
            "price": 12.95,
            "dietary": ["vegetarian"],
            "allergens": ["dairy", "gluten", "eggs", "fish"],
            "popular": True,
        },
        {
            "id": "SAL03",
            "name": "Grilled Chicken Cobb",
            "description": "Grilled chicken, bacon, egg, avocado, blue cheese, tomatoes on mixed greens",
            "price": 17.95,
            "dietary": ["gluten-free"],
            "allergens": ["dairy", "eggs"],
            "popular": True,
        },
        {
            "id": "SAL04",
            "name": "Mediterranean Quinoa Bowl",
            "description": "Quinoa with cucumber, tomatoes, olives, feta, and lemon herb dressing",
            "price": 14.95,
            "dietary": ["vegetarian", "gluten-free"],
            "allergens": ["dairy"],
            "popular": True,
        },
    ],
    "entrees": [
        {
            "id": "ENT01",
            "name": "Grilled Atlantic Salmon",
            "description": "8oz salmon with lemon dill butter, seasonal vegetables, and rice pilaf",
            "price": 28.95,
            "dietary": ["gluten-free"],
            "allergens": ["fish", "dairy"],
            "popular": True,
        },
        {
            "id": "ENT02",
            "name": "New York Strip Steak",
            "description": "12oz USDA Choice strip with garlic herb butter, mashed potatoes, and asparagus",
            "price": 38.95,
            "dietary": ["gluten-free"],
            "allergens": ["dairy"],
            "popular": True,
        },
        {
            "id": "ENT03",
            "name": "Herb Roasted Chicken",
            "description": "Half chicken with rosemary, roasted vegetables, and natural jus",
            "price": 24.95,
            "dietary": ["gluten-free", "dairy-free"],
            "allergens": [],
            "popular": False,
        },
        {
            "id": "ENT04",
            "name": "Wild Mushroom Risotto",
            "description": "Creamy arborio rice with wild mushrooms, truffle oil, and parmesan",
            "price": 22.95,
            "dietary": ["vegetarian", "gluten-free"],
            "allergens": ["dairy"],
            "popular": True,
        },
        {
            "id": "ENT05",
            "name": "Pan-Seared Sea Bass",
            "description": "Chilean sea bass with miso glaze, bok choy, and jasmine rice",
            "price": 36.95,
            "dietary": ["gluten-free"],
            "allergens": ["fish", "soy"],
            "popular": True,
        },
        {
            "id": "ENT06",
            "name": "Garden Veggie Pasta",
            "description": "Seasonal vegetables with garlic, olive oil, and penne (or gluten-free option)",
            "price": 19.95,
            "dietary": ["vegetarian", "vegan", "gluten-free-optional"],
            "allergens": ["gluten"],
            "popular": False,
        },
        {
            "id": "ENT07",
            "name": "Braised Short Ribs",
            "description": "Slow-braised beef short ribs with red wine reduction and creamy polenta",
            "price": 32.95,
            "dietary": ["gluten-free"],
            "allergens": ["dairy"],
            "popular": True,
        },
        {
            "id": "ENT08",
            "name": "Lobster Mac & Cheese",
            "description": "Maine lobster with four cheeses and buttery breadcrumb topping",
            "price": 34.95,
            "dietary": [],
            "allergens": ["shellfish", "dairy", "gluten"],
            "popular": True,
        },
    ],
    "sides": [
        {
            "id": "SID01",
            "name": "Garlic Mashed Potatoes",
            "price": 6.95,
            "dietary": ["vegetarian", "gluten-free"],
            "allergens": ["dairy"],
        },
        {
            "id": "SID02",
            "name": "Grilled Asparagus",
            "price": 7.95,
            "dietary": ["vegan", "gluten-free"],
            "allergens": [],
        },
        {
            "id": "SID03",
            "name": "Truffle Fries",
            "price": 8.95,
            "dietary": ["vegetarian", "gluten-free"],
            "allergens": ["dairy"],
        },
        {
            "id": "SID04",
            "name": "Seasonal Vegetables",
            "price": 6.95,
            "dietary": ["vegan", "gluten-free"],
            "allergens": [],
        },
        {
            "id": "SID05",
            "name": "Mac & Cheese",
            "price": 7.95,
            "dietary": ["vegetarian"],
            "allergens": ["dairy", "gluten"],
        },
    ],
    "desserts": [
        {
            "id": "DES01",
            "name": "Chocolate Lava Cake",
            "description": "Warm chocolate cake with molten center, vanilla ice cream",
            "price": 10.95,
            "dietary": ["vegetarian"],
            "allergens": ["dairy", "eggs", "gluten"],
            "popular": True,
        },
        {
            "id": "DES02",
            "name": "New York Cheesecake",
            "description": "Classic creamy cheesecake with berry compote",
            "price": 9.95,
            "dietary": ["vegetarian"],
            "allergens": ["dairy", "eggs", "gluten"],
            "popular": True,
        },
        {
            "id": "DES03",
            "name": "Crème Brûlée",
            "description": "Classic vanilla custard with caramelized sugar top",
            "price": 9.95,
            "dietary": ["vegetarian", "gluten-free"],
            "allergens": ["dairy", "eggs"],
            "popular": False,
        },
        {
            "id": "DES04",
            "name": "Seasonal Fruit Sorbet",
            "description": "Three scoops of refreshing fruit sorbet",
            "price": 7.95,
            "dietary": ["vegan", "gluten-free"],
            "allergens": [],
            "popular": False,
        },
    ],
    "beverages": [
        {
            "id": "BEV01",
            "name": "Soft Drinks",
            "price": 3.50,
            "dietary": ["vegan"],
            "allergens": [],
        },
        {
            "id": "BEV02",
            "name": "Fresh Lemonade",
            "price": 4.50,
            "dietary": ["vegan"],
            "allergens": [],
        },
        {
            "id": "BEV03",
            "name": "Iced Tea",
            "price": 3.50,
            "dietary": ["vegan"],
            "allergens": [],
        },
        {
            "id": "BEV04",
            "name": "Coffee",
            "price": 3.95,
            "dietary": ["vegan"],
            "allergens": [],
        },
        {
            "id": "BEV05",
            "name": "Espresso",
            "price": 3.50,
            "dietary": ["vegan"],
            "allergens": [],
        },
        {
            "id": "BEV06",
            "name": "House Wine (Glass)",
            "price": 9.95,
            "dietary": ["vegan"],
            "allergens": ["sulfites"],
        },
        {
            "id": "BEV07",
            "name": "Craft Beer (Pint)",
            "price": 7.95,
            "dietary": [],
            "allergens": ["gluten"],
        },
    ],
}

# Storage for reservations and orders
reservations = []
current_order = {"items": [], "subtotal": 0, "notes": ""}


# ============================================================================
# Restaurant Tools
# ============================================================================


def get_restaurant_info() -> dict[str, Any]:
    """
    Get restaurant information including hours and features.

    Returns:
        Restaurant details
    """
    return RESTAURANT_INFO


def get_menu(category: str = None) -> dict[str, Any]:
    """
    Get menu items, optionally filtered by category.

    Args:
        category: Menu category (appetizers, salads, entrees, sides, desserts, beverages)

    Returns:
        Menu items
    """
    if category:
        category = category.lower()
        if category in MENU:
            return {
                "category": category.title(),
                "items": MENU[category],
                "count": len(MENU[category]),
            }
        else:
            return {
                "error": f"Category '{category}' not found",
                "available_categories": list(MENU.keys()),
            }

    # Return full menu summary
    menu_summary = {}
    for cat, items in MENU.items():
        menu_summary[cat] = {
            "count": len(items),
            "price_range": f"${min(i['price'] for i in items):.2f} - ${max(i['price'] for i in items):.2f}",
        }

    return {
        "restaurant": RESTAURANT_INFO["name"],
        "categories": menu_summary,
        "popular_items": _get_popular_items(),
    }


def _get_popular_items() -> list[dict]:
    """Get popular menu items."""
    popular = []
    for cat, items in MENU.items():
        for item in items:
            if item.get("popular"):
                popular.append(
                    {
                        "name": item["name"],
                        "category": cat.title(),
                        "price": item["price"],
                    }
                )
    return popular


def search_menu(
    query: str = None, dietary: str = None, max_price: float = None
) -> dict[str, Any]:
    """
    Search menu with filters.

    Args:
        query: Search term for name or description
        dietary: Dietary restriction (vegetarian, vegan, gluten-free)
        max_price: Maximum price

    Returns:
        Matching menu items
    """
    results = []

    for category, items in MENU.items():
        for item in items:
            # Apply filters
            if (
                query
                and query.lower() not in item["name"].lower()
                and query.lower() not in item.get("description", "").lower()
            ):
                continue

            if dietary:
                dietary_lower = dietary.lower().replace("-", "_").replace(" ", "_")
                if dietary_lower not in [
                    d.lower().replace("-", "_") for d in item.get("dietary", [])
                ]:
                    continue

            if max_price and item["price"] > max_price:
                continue

            results.append(
                {
                    "category": category.title(),
                    **item,
                }
            )

    return {
        "filters": {
            "query": query,
            "dietary": dietary,
            "max_price": max_price,
        },
        "results": results,
        "count": len(results),
    }


def check_allergens(allergen: str) -> dict[str, Any]:
    """
    Find items that DO NOT contain a specific allergen.

    Args:
        allergen: Allergen to avoid (gluten, dairy, eggs, shellfish, fish, soy, nuts, sesame)

    Returns:
        Safe items without the allergen
    """
    safe_items = []
    allergen_lower = allergen.lower()

    for category, items in MENU.items():
        for item in items:
            if allergen_lower not in [a.lower() for a in item.get("allergens", [])]:
                safe_items.append(
                    {
                        "category": category.title(),
                        "name": item["name"],
                        "price": item["price"],
                        "allergens": item.get("allergens", []),
                    }
                )

    return {
        "avoiding": allergen,
        "safe_items": safe_items,
        "count": len(safe_items),
        "note": "Always inform your server of allergies for safety.",
    }


def get_item_details(item_id: str) -> dict[str, Any]:
    """
    Get detailed information about a menu item.

    Args:
        item_id: Item ID (e.g., ENT01, APP02)

    Returns:
        Item details
    """
    item_id = item_id.upper()

    for category, items in MENU.items():
        for item in items:
            if item["id"] == item_id:
                return {
                    "category": category.title(),
                    **item,
                    "modifications_available": [
                        "Substitute side dish",
                        "Cooking temperature (for steaks/fish)",
                        "Sauce on side",
                        "Add protein",
                    ],
                }

    return {"error": f"Item {item_id} not found"}


def make_reservation(
    party_size: int,
    date: str,
    time: str,
    name: str,
    phone: str,
    special_requests: str = "",
) -> dict[str, Any]:
    """
    Make a restaurant reservation.

    Args:
        party_size: Number of guests
        date: Reservation date (YYYY-MM-DD)
        time: Reservation time (e.g., 7:00 PM)
        name: Name for reservation
        phone: Contact phone number
        special_requests: Any special requests

    Returns:
        Reservation confirmation
    """
    if party_size > 12:
        return {
            "error": "For parties larger than 12, please call us to arrange private dining.",
            "phone": RESTAURANT_INFO["phone"],
        }

    confirmation_number = f"RES{random.randint(10000, 99999)}"

    reservation = {
        "confirmation": confirmation_number,
        "party_size": party_size,
        "date": date,
        "time": time,
        "name": name,
        "phone": phone,
        "special_requests": special_requests,
        "status": "Confirmed",
        "created_at": datetime.now().isoformat(),
    }

    reservations.append(reservation)

    return {
        "success": True,
        "reservation": reservation,
        "message": f"Your table for {party_size} is confirmed for {date} at {time}.",
        "reminder": "Please arrive 10-15 minutes before your reservation time.",
        "cancellation_policy": "Please cancel at least 2 hours in advance.",
    }


def check_reservation(confirmation_number: str) -> dict[str, Any]:
    """
    Check reservation status.

    Args:
        confirmation_number: Reservation confirmation number

    Returns:
        Reservation details
    """
    for res in reservations:
        if res["confirmation"] == confirmation_number.upper():
            return {"reservation": res}

    return {"error": f"Reservation {confirmation_number} not found"}


def modify_reservation(
    confirmation_number: str,
    party_size: int = None,
    date: str = None,
    time: str = None,
) -> dict[str, Any]:
    """
    Modify an existing reservation.

    Args:
        confirmation_number: Reservation confirmation number
        party_size: New party size
        date: New date
        time: New time

    Returns:
        Updated reservation
    """
    for res in reservations:
        if res["confirmation"] == confirmation_number.upper():
            if party_size:
                res["party_size"] = party_size
            if date:
                res["date"] = date
            if time:
                res["time"] = time
            res["modified_at"] = datetime.now().isoformat()

            return {
                "success": True,
                "reservation": res,
                "message": "Your reservation has been updated.",
            }

    return {"error": f"Reservation {confirmation_number} not found"}


def cancel_reservation(confirmation_number: str) -> dict[str, Any]:
    """
    Cancel a reservation.

    Args:
        confirmation_number: Reservation confirmation number

    Returns:
        Cancellation confirmation
    """
    for res in reservations:
        if res["confirmation"] == confirmation_number.upper():
            res["status"] = "Cancelled"
            return {
                "success": True,
                "message": f"Reservation {confirmation_number} has been cancelled.",
                "note": "We hope to see you again soon!",
            }

    return {"error": f"Reservation {confirmation_number} not found"}


def add_to_order(
    item_id: str, quantity: int = 1, modifications: str = ""
) -> dict[str, Any]:
    """
    Add an item to the current order.

    Args:
        item_id: Menu item ID
        quantity: Number of items
        modifications: Special modifications

    Returns:
        Updated order
    """
    item_id = item_id.upper()

    # Find item
    for category, items in MENU.items():
        for item in items:
            if item["id"] == item_id:
                order_item = {
                    "item_id": item_id,
                    "name": item["name"],
                    "price": item["price"],
                    "quantity": quantity,
                    "modifications": modifications,
                    "line_total": item["price"] * quantity,
                }

                current_order["items"].append(order_item)
                current_order["subtotal"] = sum(
                    i["line_total"] for i in current_order["items"]
                )

                return {
                    "added": order_item,
                    "order_subtotal": round(current_order["subtotal"], 2),
                    "item_count": len(current_order["items"]),
                }

    return {"error": f"Item {item_id} not found on menu"}


def view_order() -> dict[str, Any]:
    """
    View the current order.

    Returns:
        Current order details
    """
    if not current_order["items"]:
        return {"message": "Your order is empty"}

    tax_rate = 0.08
    tax = current_order["subtotal"] * tax_rate
    total = current_order["subtotal"] + tax

    return {
        "items": current_order["items"],
        "subtotal": round(current_order["subtotal"], 2),
        "tax": round(tax, 2),
        "total": round(total, 2),
        "notes": current_order["notes"],
    }


def remove_from_order(item_id: str) -> dict[str, Any]:
    """
    Remove an item from the order.

    Args:
        item_id: Item ID to remove

    Returns:
        Updated order
    """
    item_id = item_id.upper()

    for i, item in enumerate(current_order["items"]):
        if item["item_id"] == item_id:
            removed = current_order["items"].pop(i)
            current_order["subtotal"] = sum(
                i["line_total"] for i in current_order["items"]
            )

            return {
                "removed": removed["name"],
                "order_subtotal": round(current_order["subtotal"], 2),
            }

    return {"error": f"Item {item_id} not in your order"}


def add_order_notes(notes: str) -> dict[str, Any]:
    """
    Add special notes to the order.

    Args:
        notes: Special instructions or notes

    Returns:
        Confirmation
    """
    current_order["notes"] = notes
    return {
        "success": True,
        "message": "Notes added to your order",
        "notes": notes,
    }


def get_recommendations(
    preferences: list[str] = None, occasion: str = None
) -> dict[str, Any]:
    """
    Get menu recommendations based on preferences.

    Args:
        preferences: List of preferences (e.g., ["seafood", "light", "spicy"])
        occasion: Type of occasion (date night, business, family, celebration)

    Returns:
        Personalized recommendations
    """
    recommendations = {
        "appetizer": None,
        "entree": None,
        "dessert": None,
        "reason": "",
    }

    if occasion == "date night":
        recommendations = {
            "appetizer": "Tuna Tartare - Elegant and shareable",
            "entree": "Pan-Seared Sea Bass or New York Strip Steak - Our finest options",
            "dessert": "Chocolate Lava Cake - Perfect for sharing",
            "wine_pairing": "Ask your server for wine recommendations",
        }
    elif occasion == "business":
        recommendations = {
            "appetizer": "Garden Bruschetta - Light and not messy",
            "entree": "Grilled Atlantic Salmon - Professional choice",
            "dessert": "Crème Brûlée - Classic and refined",
            "note": "We have private dining available for business meetings",
        }
    elif occasion == "family":
        recommendations = {
            "appetizers": "Spinach Artichoke Dip - Great for sharing",
            "entrees": "Herb Roasted Chicken or Lobster Mac & Cheese",
            "kids_options": "Ask about our kids menu",
            "note": "We have high chairs and booster seats available",
        }
    else:
        recommendations = {
            "most_popular": _get_popular_items()[:5],
            "chef_special": "Today's Chef Special - Ask your server",
            "dietary_friendly": "We accommodate vegetarian, vegan, and gluten-free diets",
        }

    return {
        "occasion": occasion or "General dining",
        "recommendations": recommendations,
        "tip": "Our staff can customize dishes to your preferences",
    }


# ============================================================================
# Agent Configuration
# ============================================================================

HOSPITALITY_TOOLS = [
    {
        "name": "get_restaurant_info",
        "description": "Get restaurant information including hours and features",
        "function": get_restaurant_info,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_menu",
        "description": "Get menu items by category (appetizers, salads, entrees, sides, desserts, beverages)",
        "function": get_menu,
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Menu category"},
            },
        },
    },
    {
        "name": "search_menu",
        "description": "Search menu with filters for dietary restrictions, price, and keywords",
        "function": search_menu,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
                "dietary": {
                    "type": "string",
                    "description": "Dietary restriction (vegetarian, vegan, gluten-free)",
                },
                "max_price": {"type": "number", "description": "Maximum price"},
            },
        },
    },
    {
        "name": "check_allergens",
        "description": "Find items safe for specific allergies",
        "function": check_allergens,
        "parameters": {
            "type": "object",
            "properties": {
                "allergen": {"type": "string", "description": "Allergen to avoid"},
            },
            "required": ["allergen"],
        },
    },
    {
        "name": "get_item_details",
        "description": "Get detailed information about a specific menu item",
        "function": get_item_details,
        "parameters": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Item ID (e.g., ENT01)"},
            },
            "required": ["item_id"],
        },
    },
    {
        "name": "make_reservation",
        "description": "Make a restaurant reservation",
        "function": make_reservation,
        "parameters": {
            "type": "object",
            "properties": {
                "party_size": {"type": "integer", "description": "Number of guests"},
                "date": {"type": "string", "description": "Date (YYYY-MM-DD)"},
                "time": {"type": "string", "description": "Time (e.g., 7:00 PM)"},
                "name": {"type": "string", "description": "Name for reservation"},
                "phone": {"type": "string", "description": "Phone number"},
                "special_requests": {
                    "type": "string",
                    "description": "Special requests",
                },
            },
            "required": ["party_size", "date", "time", "name", "phone"],
        },
    },
    {
        "name": "check_reservation",
        "description": "Check reservation status",
        "function": check_reservation,
        "parameters": {
            "type": "object",
            "properties": {
                "confirmation_number": {
                    "type": "string",
                    "description": "Confirmation number",
                },
            },
            "required": ["confirmation_number"],
        },
    },
    {
        "name": "modify_reservation",
        "description": "Modify an existing reservation",
        "function": modify_reservation,
        "parameters": {
            "type": "object",
            "properties": {
                "confirmation_number": {
                    "type": "string",
                    "description": "Confirmation number",
                },
                "party_size": {"type": "integer", "description": "New party size"},
                "date": {"type": "string", "description": "New date"},
                "time": {"type": "string", "description": "New time"},
            },
            "required": ["confirmation_number"],
        },
    },
    {
        "name": "cancel_reservation",
        "description": "Cancel a reservation",
        "function": cancel_reservation,
        "parameters": {
            "type": "object",
            "properties": {
                "confirmation_number": {
                    "type": "string",
                    "description": "Confirmation number",
                },
            },
            "required": ["confirmation_number"],
        },
    },
    {
        "name": "add_to_order",
        "description": "Add an item to the current order",
        "function": add_to_order,
        "parameters": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Menu item ID"},
                "quantity": {"type": "integer", "description": "Quantity"},
                "modifications": {
                    "type": "string",
                    "description": "Special modifications",
                },
            },
            "required": ["item_id"],
        },
    },
    {
        "name": "view_order",
        "description": "View the current order",
        "function": view_order,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "remove_from_order",
        "description": "Remove an item from the order",
        "function": remove_from_order,
        "parameters": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Item ID to remove"},
            },
            "required": ["item_id"],
        },
    },
    {
        "name": "add_order_notes",
        "description": "Add special notes to the order",
        "function": add_order_notes,
        "parameters": {
            "type": "object",
            "properties": {
                "notes": {"type": "string", "description": "Special instructions"},
            },
            "required": ["notes"],
        },
    },
    {
        "name": "get_recommendations",
        "description": "Get menu recommendations based on preferences or occasion",
        "function": get_recommendations,
        "parameters": {
            "type": "object",
            "properties": {
                "preferences": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Preferences",
                },
                "occasion": {
                    "type": "string",
                    "description": "Occasion (date night, business, family, celebration)",
                },
            },
        },
    },
]

SYSTEM_PROMPT = """You are a friendly restaurant assistant for The Garden Bistro.

Your capabilities:
- Help guests browse our menu
- Handle dietary restrictions and allergies
- Make, modify, and cancel reservations
- Take orders and handle modifications
- Provide personalized recommendations

Guidelines:
- Be warm, professional, and helpful
- Always ask about allergies when taking orders
- Suggest popular items when appropriate
- Handle dietary restrictions with care
- Confirm details when making reservations
- Upsell naturally (drinks, appetizers, desserts)

Restaurant Info:
- Name: The Garden Bistro
- Cuisine: Contemporary American
- Features: Outdoor seating, Full bar, Private dining

Menu categories: Appetizers, Salads, Entrees, Sides, Desserts, Beverages

Remember to be enthusiastic about our food and create a welcoming experience!"""


# ============================================================================
# Main Application
# ============================================================================


async def main():
    """Run the Restaurant & Hospitality Bot."""
    print("=" * 60)
    print("🍽️ The Garden Bistro - Virtual Host")
    print("=" * 60)
    print("\nWelcome! I'm here to help you with:")
    print("  • Browse our menu and get recommendations")
    print("  • Make or manage reservations")
    print("  • Place orders with customizations")
    print("  • Handle dietary restrictions and allergies")
    print("\n💡 Example questions:")
    print('  "What\'s on the menu?"')
    print('  "Do you have vegetarian options?"')
    print('  "I need a table for 4 on Saturday at 7pm"')
    print('  "What do you recommend for date night?"')
    print("\nType 'quit' to exit")
    print("-" * 60)

    # Create agent
    agent = Agent(
        name="restaurant_host",
        system_prompt=SYSTEM_PROMPT,
        tools=HOSPITALITY_TOOLS,
    )

    try:
        while True:
            user_input = input("\n🍽️ You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                print("\n👋 Thank you for visiting The Garden Bistro!")
                print("We hope to see you soon!")
                break

            # Special commands
            if user_input.lower() == "menu":
                menu = get_menu()
                print("\n📋 Menu Categories:")
                for cat, info in menu["categories"].items():
                    print(
                        f"  {cat.title()}: {info['count']} items ({info['price_range']})"
                    )
                continue

            if user_input.lower() == "order":
                order = view_order()
                if "message" in order:
                    print(f"\n🛒 {order['message']}")
                else:
                    print(f"\n🛒 Your Order (${order['total']:.2f}):")
                    for item in order["items"]:
                        print(
                            f"  • {item['name']} x{item['quantity']} - ${item['line_total']:.2f}"
                        )
                continue

            if user_input.lower() == "hours":
                info = get_restaurant_info()
                print("\n⏰ Hours:")
                for day, hours in info["hours"].items():
                    print(f"  {day}: {hours}")
                continue

            # Get response from agent
            response = await agent.chat_async(user_input)
            print(f"\n🤖 Host: {response}")

    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
