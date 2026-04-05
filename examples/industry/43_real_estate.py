#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Real Estate Assistant
=====================

An AI-powered real estate assistant that helps users find properties,
calculate mortgages, learn about neighborhoods, and schedule viewings.

Features:
- Property search with multiple filters
- Mortgage and affordability calculations
- Neighborhood information and comparisons
- Appointment scheduling for property viewings
- Saved searches and favorites

Run:
    python examples/43_real_estate.py

Note:
    This is a demonstration with simulated property listings.
    In production, integrate with MLS APIs and real estate databases.
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Any

from agentic_brain import Agent

# ============================================================================
# Demo Property Data
# ============================================================================

PROPERTY_LISTINGS = [
    {
        "id": "PROP001",
        "address": "123 Oak Street, Greenfield",
        "type": "Single Family Home",
        "price": 425000,
        "bedrooms": 3,
        "bathrooms": 2,
        "sqft": 1850,
        "lot_size": 0.25,
        "year_built": 2005,
        "features": [
            "Hardwood floors",
            "Updated kitchen",
            "Fenced yard",
            "Two-car garage",
        ],
        "neighborhood": "Greenfield Heights",
        "status": "Active",
        "days_on_market": 12,
        "hoa_fee": 0,
        "property_tax": 4250,
        "description": "Beautiful family home in sought-after Greenfield Heights. Open floor plan with modern kitchen, spacious backyard perfect for entertaining.",
    },
    {
        "id": "PROP002",
        "address": "456 Maple Avenue, Unit 12B, Downtown",
        "type": "Condo",
        "price": 289000,
        "bedrooms": 2,
        "bathrooms": 2,
        "sqft": 1100,
        "lot_size": 0,
        "year_built": 2018,
        "features": ["City views", "In-unit laundry", "Fitness center", "Rooftop deck"],
        "neighborhood": "Downtown Core",
        "status": "Active",
        "days_on_market": 5,
        "hoa_fee": 350,
        "property_tax": 2890,
        "description": "Modern downtown condo with stunning city views. Walking distance to restaurants, shops, and public transit.",
    },
    {
        "id": "PROP003",
        "address": "789 River Road, Riverside",
        "type": "Single Family Home",
        "price": 675000,
        "bedrooms": 4,
        "bathrooms": 3,
        "sqft": 2800,
        "lot_size": 0.5,
        "year_built": 2015,
        "features": [
            "River views",
            "Gourmet kitchen",
            "Home office",
            "Pool",
            "Smart home",
        ],
        "neighborhood": "Riverside Estates",
        "status": "Active",
        "days_on_market": 21,
        "hoa_fee": 150,
        "property_tax": 6750,
        "description": "Stunning riverside property with panoramic water views. Perfect for entertaining with resort-style backyard and pool.",
    },
    {
        "id": "PROP004",
        "address": "234 Pine Lane, Westwood",
        "type": "Townhouse",
        "price": 359000,
        "bedrooms": 3,
        "bathrooms": 2.5,
        "sqft": 1650,
        "lot_size": 0.1,
        "year_built": 2012,
        "features": ["End unit", "Attached garage", "Patio", "Community pool"],
        "neighborhood": "Westwood Commons",
        "status": "Active",
        "days_on_market": 8,
        "hoa_fee": 225,
        "property_tax": 3590,
        "description": "Spacious end-unit townhouse with plenty of natural light. Low-maintenance living with community amenities.",
    },
    {
        "id": "PROP005",
        "address": "567 Elm Court, Northview",
        "type": "Single Family Home",
        "price": 485000,
        "bedrooms": 4,
        "bathrooms": 2.5,
        "sqft": 2200,
        "lot_size": 0.3,
        "year_built": 1998,
        "features": [
            "Renovated bathrooms",
            "New roof",
            "Large deck",
            "Finished basement",
        ],
        "neighborhood": "Northview Park",
        "status": "Active",
        "days_on_market": 15,
        "hoa_fee": 0,
        "property_tax": 4850,
        "description": "Well-maintained home with recent updates. Great school district, quiet cul-de-sac location.",
    },
    {
        "id": "PROP006",
        "address": "890 Beach Boulevard, Unit 5A, Seaside",
        "type": "Condo",
        "price": 525000,
        "bedrooms": 2,
        "bathrooms": 2,
        "sqft": 1350,
        "lot_size": 0,
        "year_built": 2020,
        "features": ["Ocean views", "Balcony", "Concierge", "Beach access", "Parking"],
        "neighborhood": "Seaside Village",
        "status": "Active",
        "days_on_market": 3,
        "hoa_fee": 475,
        "property_tax": 5250,
        "description": "Luxury beachfront living with direct ocean views. Building offers resort-style amenities and direct beach access.",
    },
    {
        "id": "PROP007",
        "address": "345 College Street, University District",
        "type": "Multi-Family",
        "price": 599000,
        "bedrooms": 6,
        "bathrooms": 4,
        "sqft": 2400,
        "lot_size": 0.15,
        "year_built": 1985,
        "features": ["Duplex", "Rental income", "Updated units", "Off-street parking"],
        "neighborhood": "University District",
        "status": "Active",
        "days_on_market": 30,
        "hoa_fee": 0,
        "property_tax": 5990,
        "description": "Investment opportunity! Two-unit property near university. Both units recently renovated with strong rental history.",
    },
    {
        "id": "PROP008",
        "address": "678 Countryside Drive, Rural Valley",
        "type": "Single Family Home",
        "price": 395000,
        "bedrooms": 3,
        "bathrooms": 2,
        "sqft": 1900,
        "lot_size": 2.0,
        "year_built": 2008,
        "features": ["Acreage", "Barn", "Workshop", "Garden", "Mountain views"],
        "neighborhood": "Rural Valley",
        "status": "Active",
        "days_on_market": 45,
        "hoa_fee": 0,
        "property_tax": 3950,
        "description": "Country living at its finest! Spacious home on 2 acres with barn, workshop, and beautiful mountain views.",
    },
]

NEIGHBORHOODS = {
    "Greenfield Heights": {
        "description": "Family-friendly suburban neighborhood with excellent schools and parks.",
        "median_price": 420000,
        "school_rating": 8.5,
        "crime_rating": "Low",
        "walkability": 65,
        "commute_downtown": "25 minutes",
        "amenities": ["Parks", "Elementary school", "Shopping center", "Library"],
        "demographics": "Primarily families with children",
    },
    "Downtown Core": {
        "description": "Vibrant urban center with restaurants, nightlife, and cultural attractions.",
        "median_price": 350000,
        "school_rating": 7.0,
        "crime_rating": "Medium",
        "walkability": 95,
        "commute_downtown": "5 minutes",
        "amenities": ["Restaurants", "Theaters", "Museums", "Transit hub"],
        "demographics": "Young professionals and empty nesters",
    },
    "Riverside Estates": {
        "description": "Upscale waterfront community with luxury homes and private amenities.",
        "median_price": 650000,
        "school_rating": 9.0,
        "crime_rating": "Very Low",
        "walkability": 45,
        "commute_downtown": "20 minutes",
        "amenities": ["Marina", "Golf course", "Country club", "Private beach"],
        "demographics": "Affluent families and retirees",
    },
    "Westwood Commons": {
        "description": "Modern townhouse community with shared amenities and low maintenance.",
        "median_price": 340000,
        "school_rating": 7.5,
        "crime_rating": "Low",
        "walkability": 70,
        "commute_downtown": "15 minutes",
        "amenities": ["Pool", "Fitness center", "Walking trails", "Playground"],
        "demographics": "Young families and professionals",
    },
    "Northview Park": {
        "description": "Established neighborhood known for top-rated schools and community spirit.",
        "median_price": 475000,
        "school_rating": 9.5,
        "crime_rating": "Very Low",
        "walkability": 55,
        "commute_downtown": "30 minutes",
        "amenities": ["Award-winning schools", "Sports fields", "Community center"],
        "demographics": "Families with school-age children",
    },
    "Seaside Village": {
        "description": "Coastal community with beach lifestyle and resort amenities.",
        "median_price": 500000,
        "school_rating": 8.0,
        "crime_rating": "Low",
        "walkability": 80,
        "commute_downtown": "35 minutes",
        "amenities": ["Beach", "Boardwalk", "Seafood restaurants", "Surf shops"],
        "demographics": "Beach lovers and vacation homeowners",
    },
    "University District": {
        "description": "Eclectic neighborhood near the university with student housing and cafes.",
        "median_price": 380000,
        "school_rating": 7.0,
        "crime_rating": "Medium",
        "walkability": 85,
        "commute_downtown": "10 minutes",
        "amenities": ["University", "Bookstores", "Coffee shops", "Music venues"],
        "demographics": "Students, professors, and young renters",
    },
    "Rural Valley": {
        "description": "Peaceful countryside with larger lots and agricultural character.",
        "median_price": 375000,
        "school_rating": 7.5,
        "crime_rating": "Very Low",
        "walkability": 15,
        "commute_downtown": "45 minutes",
        "amenities": ["Farms", "Hiking trails", "Wineries", "Farmers market"],
        "demographics": "Families seeking rural lifestyle",
    },
}

# Scheduled appointments storage
scheduled_appointments = []

# User favorites storage
user_favorites = []


# ============================================================================
# Real Estate Tools
# ============================================================================


def search_properties(
    min_price: int = 0,
    max_price: int = 10000000,
    min_beds: int = 0,
    max_beds: int = 20,
    property_type: str = None,
    neighborhood: str = None,
    min_sqft: int = 0,
) -> dict[str, Any]:
    """
    Search for properties matching the given criteria.

    Args:
        min_price: Minimum price
        max_price: Maximum price
        min_beds: Minimum bedrooms
        max_beds: Maximum bedrooms
        property_type: Type of property (Single Family Home, Condo, Townhouse, etc.)
        neighborhood: Specific neighborhood
        min_sqft: Minimum square footage

    Returns:
        Matching property listings
    """
    results = []

    for prop in PROPERTY_LISTINGS:
        # Apply filters
        if prop["price"] < min_price or prop["price"] > max_price:
            continue
        if prop["bedrooms"] < min_beds or prop["bedrooms"] > max_beds:
            continue
        if property_type and property_type.lower() not in prop["type"].lower():
            continue
        if neighborhood and neighborhood.lower() not in prop["neighborhood"].lower():
            continue
        if prop["sqft"] < min_sqft:
            continue

        results.append(prop)

    return {
        "count": len(results),
        "properties": results,
        "filters_applied": {
            "price_range": f"${min_price:,} - ${max_price:,}",
            "bedrooms": f"{min_beds} - {max_beds}",
            "property_type": property_type or "Any",
            "neighborhood": neighborhood or "Any",
            "min_sqft": min_sqft,
        },
    }


def get_property_details(property_id: str) -> dict[str, Any]:
    """
    Get detailed information about a specific property.

    Args:
        property_id: The property ID (e.g., PROP001)

    Returns:
        Property details or error if not found
    """
    for prop in PROPERTY_LISTINGS:
        if prop["id"] == property_id.upper():
            # Calculate additional info
            price_per_sqft = prop["price"] / prop["sqft"]
            monthly_tax = prop["property_tax"] / 12
            total_monthly = monthly_tax + prop["hoa_fee"]

            return {
                **prop,
                "price_per_sqft": round(price_per_sqft, 2),
                "monthly_property_tax": round(monthly_tax, 2),
                "total_monthly_fees": round(total_monthly, 2),
                "neighborhood_info": NEIGHBORHOODS.get(prop["neighborhood"], {}),
            }

    return {"error": f"Property {property_id} not found"}


def calculate_mortgage(
    home_price: int,
    down_payment_percent: float = 20.0,
    interest_rate: float = 6.5,
    loan_term_years: int = 30,
    annual_property_tax: int = 0,
    monthly_hoa: int = 0,
    monthly_insurance: int = 150,
) -> dict[str, Any]:
    """
    Calculate monthly mortgage payment and affordability.

    Args:
        home_price: Total home price
        down_payment_percent: Down payment as percentage
        interest_rate: Annual interest rate
        loan_term_years: Loan term in years
        annual_property_tax: Annual property tax
        monthly_hoa: Monthly HOA fee
        monthly_insurance: Monthly homeowner's insurance

    Returns:
        Detailed mortgage calculation
    """
    down_payment = home_price * (down_payment_percent / 100)
    loan_amount = home_price - down_payment

    # Monthly interest rate
    monthly_rate = (interest_rate / 100) / 12
    num_payments = loan_term_years * 12

    # Calculate monthly principal and interest (P&I)
    if monthly_rate > 0:
        monthly_pi = (
            loan_amount
            * (monthly_rate * (1 + monthly_rate) ** num_payments)
            / ((1 + monthly_rate) ** num_payments - 1)
        )
    else:
        monthly_pi = loan_amount / num_payments

    # Monthly property tax
    monthly_tax = annual_property_tax / 12

    # Total monthly payment (PITI + HOA)
    total_monthly = monthly_pi + monthly_tax + monthly_insurance + monthly_hoa

    # Calculate total cost over loan term
    total_payments = monthly_pi * num_payments
    total_interest = total_payments - loan_amount

    return {
        "home_price": home_price,
        "down_payment": round(down_payment, 2),
        "down_payment_percent": down_payment_percent,
        "loan_amount": round(loan_amount, 2),
        "interest_rate": interest_rate,
        "loan_term_years": loan_term_years,
        "monthly_breakdown": {
            "principal_and_interest": round(monthly_pi, 2),
            "property_tax": round(monthly_tax, 2),
            "homeowners_insurance": monthly_insurance,
            "hoa_fee": monthly_hoa,
            "total_monthly_payment": round(total_monthly, 2),
        },
        "total_interest_paid": round(total_interest, 2),
        "total_cost": round(total_payments + down_payment, 2),
        "recommended_income": round(total_monthly / 0.28 * 12, 2),
        "note": "Recommended income based on 28% housing ratio guideline.",
    }


def get_neighborhood_info(neighborhood_name: str) -> dict[str, Any]:
    """
    Get detailed information about a neighborhood.

    Args:
        neighborhood_name: Name of the neighborhood

    Returns:
        Neighborhood details
    """
    # Find best match
    for name, info in NEIGHBORHOODS.items():
        if neighborhood_name.lower() in name.lower():
            return {
                "name": name,
                **info,
                "active_listings": len(
                    [
                        p
                        for p in PROPERTY_LISTINGS
                        if p["neighborhood"] == name and p["status"] == "Active"
                    ]
                ),
            }

    return {
        "error": f"Neighborhood '{neighborhood_name}' not found",
        "available_neighborhoods": list(NEIGHBORHOODS.keys()),
    }


def compare_neighborhoods(neighborhood1: str, neighborhood2: str) -> dict[str, Any]:
    """
    Compare two neighborhoods side by side.

    Args:
        neighborhood1: First neighborhood name
        neighborhood2: Second neighborhood name

    Returns:
        Comparison of both neighborhoods
    """
    info1 = get_neighborhood_info(neighborhood1)
    info2 = get_neighborhood_info(neighborhood2)

    if "error" in info1 or "error" in info2:
        return {
            "error": "One or both neighborhoods not found",
            "info1": info1,
            "info2": info2,
        }

    return {
        "comparison": {
            "categories": [
                "Median Price",
                "School Rating",
                "Crime Rating",
                "Walkability",
                "Commute",
            ],
            neighborhood1: [
                f"${info1['median_price']:,}",
                f"{info1['school_rating']}/10",
                info1["crime_rating"],
                f"{info1['walkability']}/100",
                info1["commute_downtown"],
            ],
            neighborhood2: [
                f"${info2['median_price']:,}",
                f"{info2['school_rating']}/10",
                info2["crime_rating"],
                f"{info2['walkability']}/100",
                info2["commute_downtown"],
            ],
        },
        "neighborhood1_details": info1,
        "neighborhood2_details": info2,
    }


def schedule_viewing(
    property_id: str,
    preferred_date: str,
    preferred_time: str,
    name: str,
    phone: str,
    email: str,
) -> dict[str, Any]:
    """
    Schedule a property viewing appointment.

    Args:
        property_id: Property ID to view
        preferred_date: Preferred date (YYYY-MM-DD)
        preferred_time: Preferred time (HH:MM)
        name: Contact name
        phone: Contact phone
        email: Contact email

    Returns:
        Appointment confirmation
    """
    # Verify property exists
    prop = None
    for p in PROPERTY_LISTINGS:
        if p["id"] == property_id.upper():
            prop = p
            break

    if not prop:
        return {"error": f"Property {property_id} not found"}

    # Create appointment
    appointment_id = f"APT{random.randint(10000, 99999)}"

    appointment = {
        "appointment_id": appointment_id,
        "property_id": property_id.upper(),
        "property_address": prop["address"],
        "date": preferred_date,
        "time": preferred_time,
        "contact": {
            "name": name,
            "phone": phone,
            "email": email,
        },
        "status": "Confirmed",
        "created_at": datetime.now().isoformat(),
    }

    scheduled_appointments.append(appointment)

    return {
        "success": True,
        "appointment": appointment,
        "message": f"Your viewing for {prop['address']} has been scheduled for {preferred_date} at {preferred_time}.",
        "reminder": "You will receive a confirmation email and reminder 24 hours before your appointment.",
    }


def get_appointments() -> dict[str, Any]:
    """
    Get all scheduled appointments.

    Returns:
        List of scheduled appointments
    """
    return {
        "count": len(scheduled_appointments),
        "appointments": scheduled_appointments,
    }


def save_favorite(property_id: str) -> dict[str, Any]:
    """
    Save a property to favorites.

    Args:
        property_id: Property ID to save

    Returns:
        Confirmation
    """
    property_id = property_id.upper()

    # Verify property exists
    prop = None
    for p in PROPERTY_LISTINGS:
        if p["id"] == property_id:
            prop = p
            break

    if not prop:
        return {"error": f"Property {property_id} not found"}

    if property_id in user_favorites:
        return {"message": f"Property {property_id} is already in your favorites"}

    user_favorites.append(property_id)

    return {
        "success": True,
        "message": f"Property at {prop['address']} has been added to your favorites.",
        "total_favorites": len(user_favorites),
    }


def get_favorites() -> dict[str, Any]:
    """
    Get saved favorite properties.

    Returns:
        List of favorite properties
    """
    favorites = []
    for prop_id in user_favorites:
        for prop in PROPERTY_LISTINGS:
            if prop["id"] == prop_id:
                favorites.append(prop)
                break

    return {
        "count": len(favorites),
        "properties": favorites,
    }


def estimate_closing_costs(
    home_price: int, is_first_time_buyer: bool = False
) -> dict[str, Any]:
    """
    Estimate closing costs for a property purchase.

    Args:
        home_price: Purchase price
        is_first_time_buyer: Whether buyer qualifies for first-time buyer programs

    Returns:
        Estimated closing costs breakdown
    """
    # Standard closing cost estimates
    costs = {
        "loan_origination_fee": round(home_price * 0.01, 2),
        "appraisal_fee": 500,
        "credit_report_fee": 50,
        "title_insurance": round(home_price * 0.005, 2),
        "title_search_fee": 400,
        "escrow_fee": round(home_price * 0.002, 2),
        "recording_fees": 200,
        "home_inspection": 450,
        "property_survey": 400,
        "attorney_fees": 1000,
        "transfer_taxes": round(home_price * 0.01, 2),
        "prepaid_insurance": round(home_price * 0.004, 2),
        "prepaid_taxes": round(home_price * 0.003, 2),
    }

    total = sum(costs.values())

    # First-time buyer discount
    discount = 0
    if is_first_time_buyer:
        discount = total * 0.05

    return {
        "home_price": home_price,
        "closing_costs_breakdown": costs,
        "subtotal": round(total, 2),
        "first_time_buyer_discount": round(discount, 2),
        "total_closing_costs": round(total - discount, 2),
        "percentage_of_price": round((total - discount) / home_price * 100, 2),
        "note": "These are estimates. Actual closing costs may vary based on location and lender.",
    }


# ============================================================================
# Agent Configuration
# ============================================================================

REAL_ESTATE_TOOLS = [
    {
        "name": "search_properties",
        "description": "Search for properties matching criteria like price range, bedrooms, property type, and neighborhood. Returns matching listings.",
        "function": search_properties,
        "parameters": {
            "type": "object",
            "properties": {
                "min_price": {"type": "integer", "description": "Minimum price"},
                "max_price": {"type": "integer", "description": "Maximum price"},
                "min_beds": {"type": "integer", "description": "Minimum bedrooms"},
                "max_beds": {"type": "integer", "description": "Maximum bedrooms"},
                "property_type": {
                    "type": "string",
                    "description": "Property type (Single Family Home, Condo, Townhouse, Multi-Family)",
                },
                "neighborhood": {"type": "string", "description": "Neighborhood name"},
                "min_sqft": {
                    "type": "integer",
                    "description": "Minimum square footage",
                },
            },
        },
    },
    {
        "name": "get_property_details",
        "description": "Get detailed information about a specific property by ID",
        "function": get_property_details,
        "parameters": {
            "type": "object",
            "properties": {
                "property_id": {
                    "type": "string",
                    "description": "Property ID (e.g., PROP001)",
                },
            },
            "required": ["property_id"],
        },
    },
    {
        "name": "calculate_mortgage",
        "description": "Calculate monthly mortgage payment and affordability. Returns detailed breakdown of payments.",
        "function": calculate_mortgage,
        "parameters": {
            "type": "object",
            "properties": {
                "home_price": {"type": "integer", "description": "Total home price"},
                "down_payment_percent": {
                    "type": "number",
                    "description": "Down payment percentage (default 20)",
                },
                "interest_rate": {
                    "type": "number",
                    "description": "Annual interest rate (default 6.5)",
                },
                "loan_term_years": {
                    "type": "integer",
                    "description": "Loan term in years (default 30)",
                },
                "annual_property_tax": {
                    "type": "integer",
                    "description": "Annual property tax",
                },
                "monthly_hoa": {"type": "integer", "description": "Monthly HOA fee"},
                "monthly_insurance": {
                    "type": "integer",
                    "description": "Monthly homeowner's insurance",
                },
            },
            "required": ["home_price"],
        },
    },
    {
        "name": "get_neighborhood_info",
        "description": "Get information about a neighborhood including schools, safety, walkability, and amenities",
        "function": get_neighborhood_info,
        "parameters": {
            "type": "object",
            "properties": {
                "neighborhood_name": {
                    "type": "string",
                    "description": "Name of the neighborhood",
                },
            },
            "required": ["neighborhood_name"],
        },
    },
    {
        "name": "compare_neighborhoods",
        "description": "Compare two neighborhoods side by side",
        "function": compare_neighborhoods,
        "parameters": {
            "type": "object",
            "properties": {
                "neighborhood1": {
                    "type": "string",
                    "description": "First neighborhood",
                },
                "neighborhood2": {
                    "type": "string",
                    "description": "Second neighborhood",
                },
            },
            "required": ["neighborhood1", "neighborhood2"],
        },
    },
    {
        "name": "schedule_viewing",
        "description": "Schedule a property viewing appointment",
        "function": schedule_viewing,
        "parameters": {
            "type": "object",
            "properties": {
                "property_id": {"type": "string", "description": "Property ID"},
                "preferred_date": {
                    "type": "string",
                    "description": "Preferred date (YYYY-MM-DD)",
                },
                "preferred_time": {
                    "type": "string",
                    "description": "Preferred time (HH:MM)",
                },
                "name": {"type": "string", "description": "Contact name"},
                "phone": {"type": "string", "description": "Contact phone"},
                "email": {"type": "string", "description": "Contact email"},
            },
            "required": [
                "property_id",
                "preferred_date",
                "preferred_time",
                "name",
                "phone",
                "email",
            ],
        },
    },
    {
        "name": "get_appointments",
        "description": "Get all scheduled viewing appointments",
        "function": get_appointments,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "save_favorite",
        "description": "Save a property to favorites list",
        "function": save_favorite,
        "parameters": {
            "type": "object",
            "properties": {
                "property_id": {"type": "string", "description": "Property ID to save"},
            },
            "required": ["property_id"],
        },
    },
    {
        "name": "get_favorites",
        "description": "Get list of saved favorite properties",
        "function": get_favorites,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "estimate_closing_costs",
        "description": "Estimate closing costs for a property purchase",
        "function": estimate_closing_costs,
        "parameters": {
            "type": "object",
            "properties": {
                "home_price": {"type": "integer", "description": "Purchase price"},
                "is_first_time_buyer": {
                    "type": "boolean",
                    "description": "First-time buyer status",
                },
            },
            "required": ["home_price"],
        },
    },
]

SYSTEM_PROMPT = """You are a helpful real estate assistant helping users find their perfect property.

Your capabilities:
- Search for properties by price, bedrooms, type, neighborhood, and size
- Provide detailed property information
- Calculate mortgage payments and affordability
- Share neighborhood information (schools, safety, amenities)
- Compare different neighborhoods
- Schedule property viewings
- Manage saved favorites
- Estimate closing costs

Guidelines:
- Always be helpful and informative
- When users describe their needs, search for matching properties
- Proactively offer mortgage calculations when discussing prices
- Suggest comparable properties when appropriate
- Highlight important property features and neighborhood benefits
- Help users understand the home buying process
- Be transparent about being a demonstration system with simulated data

Available neighborhoods: Greenfield Heights, Downtown Core, Riverside Estates, 
Westwood Commons, Northview Park, Seaside Village, University District, Rural Valley

Property types available: Single Family Home, Condo, Townhouse, Multi-Family"""


# ============================================================================
# Main Application
# ============================================================================


async def main():
    """Run the Real Estate Assistant."""
    print("=" * 60)
    print("🏠 Real Estate Assistant")
    print("=" * 60)
    print("\nWelcome! I can help you:")
    print("  • Search for properties by your criteria")
    print("  • Calculate mortgage payments")
    print("  • Learn about neighborhoods")
    print("  • Schedule property viewings")
    print("  • Save favorite properties")
    print("\n💡 Example questions:")
    print('  "Show me 3-bedroom homes under $500,000"')
    print('  "What\'s the monthly payment on a $400,000 home?"')
    print('  "Tell me about Greenfield Heights neighborhood"')
    print('  "Compare Downtown and Riverside neighborhoods"')
    print("\nType 'quit' to exit\n")
    print("-" * 60)

    # Create agent
    agent = Agent(
        name="real_estate_assistant",
        system_prompt=SYSTEM_PROMPT,
        tools=REAL_ESTATE_TOOLS,
    )

    try:
        while True:
            user_input = input("\n🏠 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                print("\n👋 Thank you for using Real Estate Assistant!")
                print("Good luck with your home search!")
                break

            # Special commands
            if user_input.lower() == "listings":
                print("\n📋 Available Properties:")
                for prop in PROPERTY_LISTINGS:
                    print(f"  {prop['id']}: {prop['address']} - ${prop['price']:,}")
                continue

            if user_input.lower() == "neighborhoods":
                print("\n🏘️ Available Neighborhoods:")
                for name in NEIGHBORHOODS:
                    print(f"  • {name}")
                continue

            if user_input.lower() == "favorites":
                favs = get_favorites()
                if favs["count"] == 0:
                    print("\n❤️ No saved favorites yet.")
                else:
                    print(f"\n❤️ Your Favorites ({favs['count']}):")
                    for prop in favs["properties"]:
                        print(f"  • {prop['address']} - ${prop['price']:,}")
                continue

            if user_input.lower() == "appointments":
                appts = get_appointments()
                if appts["count"] == 0:
                    print("\n📅 No scheduled appointments.")
                else:
                    print(f"\n📅 Your Appointments ({appts['count']}):")
                    for appt in appts["appointments"]:
                        print(
                            f"  • {appt['date']} {appt['time']} - {appt['property_address']}"
                        )
                continue

            # Get response from agent
            response = await agent.chat_async(user_input)
            print(f"\n🤖 Agent: {response}")

    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
