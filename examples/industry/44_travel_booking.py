#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Travel & Booking Agent
======================

An AI travel assistant that helps users search for flights and hotels,
plan itineraries, compare prices, and manage bookings.

Features:
- Flight search with flexible dates
- Hotel search and comparison
- Itinerary planning and suggestions
- Price comparison across options
- Booking management

Run:
    python examples/44_travel_booking.py

Note:
    This is a demonstration with simulated travel data.
    In production, integrate with travel APIs (Amadeus, Skyscanner, etc.)
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Any

from agentic_brain import Agent

# ============================================================================
# Demo Flight Data
# ============================================================================

AIRPORTS = {
    "NYC": {"name": "New York City", "airports": ["JFK", "LGA", "EWR"]},
    "LAX": {"name": "Los Angeles", "airports": ["LAX"]},
    "CHI": {"name": "Chicago", "airports": ["ORD", "MDW"]},
    "MIA": {"name": "Miami", "airports": ["MIA"]},
    "SFO": {"name": "San Francisco", "airports": ["SFO"]},
    "SEA": {"name": "Seattle", "airports": ["SEA"]},
    "BOS": {"name": "Boston", "airports": ["BOS"]},
    "DEN": {"name": "Denver", "airports": ["DEN"]},
    "LAS": {"name": "Las Vegas", "airports": ["LAS"]},
    "ATL": {"name": "Atlanta", "airports": ["ATL"]},
    "LON": {"name": "London", "airports": ["LHR", "LGW"]},
    "PAR": {"name": "Paris", "airports": ["CDG", "ORY"]},
    "TYO": {"name": "Tokyo", "airports": ["NRT", "HND"]},
    "SYD": {"name": "Sydney", "airports": ["SYD"]},
}

AIRLINES = [
    "United Airlines",
    "American Airlines",
    "Delta Air Lines",
    "Southwest",
    "JetBlue",
    "Alaska Airlines",
]

# ============================================================================
# Demo Hotel Data
# ============================================================================

HOTELS = {
    "NYC": [
        {
            "name": "The Manhattan Grand",
            "stars": 5,
            "price_per_night": 450,
            "amenities": ["Spa", "Pool", "Restaurant", "Gym", "Concierge"],
            "rating": 4.8,
            "location": "Times Square",
        },
        {
            "name": "Brooklyn Bridge Hotel",
            "stars": 4,
            "price_per_night": 280,
            "amenities": ["Restaurant", "Gym", "Business Center"],
            "rating": 4.5,
            "location": "Brooklyn",
        },
        {
            "name": "Central Park Inn",
            "stars": 4,
            "price_per_night": 320,
            "amenities": ["Restaurant", "Gym", "Room Service"],
            "rating": 4.6,
            "location": "Upper West Side",
        },
        {
            "name": "Downtown Express",
            "stars": 3,
            "price_per_night": 175,
            "amenities": ["Free WiFi", "Continental Breakfast"],
            "rating": 4.2,
            "location": "Financial District",
        },
    ],
    "LAX": [
        {
            "name": "Beverly Hills Luxury Resort",
            "stars": 5,
            "price_per_night": 550,
            "amenities": ["Spa", "Pool", "Golf", "Restaurant", "Valet"],
            "rating": 4.9,
            "location": "Beverly Hills",
        },
        {
            "name": "Santa Monica Beach Hotel",
            "stars": 4,
            "price_per_night": 320,
            "amenities": ["Beach Access", "Pool", "Restaurant"],
            "rating": 4.6,
            "location": "Santa Monica",
        },
        {
            "name": "Hollywood Boutique",
            "stars": 4,
            "price_per_night": 250,
            "amenities": ["Rooftop Bar", "Gym", "Shuttle"],
            "rating": 4.4,
            "location": "Hollywood",
        },
        {
            "name": "LAX Airport Inn",
            "stars": 3,
            "price_per_night": 140,
            "amenities": ["Free Shuttle", "Parking", "WiFi"],
            "rating": 4.0,
            "location": "Near Airport",
        },
    ],
    "LON": [
        {
            "name": "The Royal Westminster",
            "stars": 5,
            "price_per_night": 520,
            "amenities": ["Spa", "Fine Dining", "Concierge", "Butler Service"],
            "rating": 4.9,
            "location": "Westminster",
        },
        {
            "name": "Covent Garden Hotel",
            "stars": 4,
            "price_per_night": 340,
            "amenities": ["Restaurant", "Bar", "Gym"],
            "rating": 4.7,
            "location": "Covent Garden",
        },
        {
            "name": "Kings Cross Modern",
            "stars": 4,
            "price_per_night": 220,
            "amenities": ["WiFi", "Gym", "Restaurant"],
            "rating": 4.4,
            "location": "Kings Cross",
        },
        {
            "name": "Budget London Stay",
            "stars": 3,
            "price_per_night": 120,
            "amenities": ["WiFi", "Breakfast Included"],
            "rating": 4.1,
            "location": "Zone 2",
        },
    ],
    "PAR": [
        {
            "name": "Le Château Paris",
            "stars": 5,
            "price_per_night": 580,
            "amenities": ["Michelin Restaurant", "Spa", "Concierge"],
            "rating": 4.9,
            "location": "8th Arrondissement",
        },
        {
            "name": "Montmartre Art Hotel",
            "stars": 4,
            "price_per_night": 290,
            "amenities": ["Art Gallery", "Café", "Terrace"],
            "rating": 4.6,
            "location": "Montmartre",
        },
        {
            "name": "Saint-Germain Classic",
            "stars": 4,
            "price_per_night": 320,
            "amenities": ["Restaurant", "Bar", "Garden"],
            "rating": 4.5,
            "location": "Saint-Germain",
        },
        {
            "name": "Paris Budget Inn",
            "stars": 3,
            "price_per_night": 110,
            "amenities": ["WiFi", "Metro Nearby"],
            "rating": 4.0,
            "location": "11th Arrondissement",
        },
    ],
    "TYO": [
        {
            "name": "Imperial Tokyo",
            "stars": 5,
            "price_per_night": 480,
            "amenities": ["Onsen", "Multiple Restaurants", "Garden", "Concierge"],
            "rating": 4.9,
            "location": "Chiyoda",
        },
        {
            "name": "Shibuya Crossing Hotel",
            "stars": 4,
            "price_per_night": 280,
            "amenities": ["Rooftop Bar", "Gym", "WiFi"],
            "rating": 4.6,
            "location": "Shibuya",
        },
        {
            "name": "Shinjuku Business Hotel",
            "stars": 4,
            "price_per_night": 200,
            "amenities": ["Restaurant", "Business Center"],
            "rating": 4.4,
            "location": "Shinjuku",
        },
        {
            "name": "Capsule Stay Tokyo",
            "stars": 2,
            "price_per_night": 50,
            "amenities": ["WiFi", "Locker", "Shower"],
            "rating": 4.2,
            "location": "Akihabara",
        },
    ],
}

# Default hotels for cities not in the list
DEFAULT_HOTELS = [
    {
        "name": "City Center Hotel",
        "stars": 4,
        "price_per_night": 200,
        "amenities": ["Pool", "Restaurant", "Gym"],
        "rating": 4.3,
        "location": "Downtown",
    },
    {
        "name": "Airport Comfort Inn",
        "stars": 3,
        "price_per_night": 120,
        "amenities": ["Free Shuttle", "WiFi", "Parking"],
        "rating": 4.0,
        "location": "Near Airport",
    },
    {
        "name": "Budget Traveler Lodge",
        "stars": 2,
        "price_per_night": 75,
        "amenities": ["WiFi", "Breakfast"],
        "rating": 3.8,
        "location": "City Outskirts",
    },
]

# ============================================================================
# Demo Attractions Data
# ============================================================================

ATTRACTIONS = {
    "NYC": [
        "Statue of Liberty",
        "Central Park",
        "Empire State Building",
        "Broadway Shows",
        "Times Square",
        "Metropolitan Museum of Art",
        "Brooklyn Bridge",
    ],
    "LAX": [
        "Hollywood Walk of Fame",
        "Santa Monica Pier",
        "Griffith Observatory",
        "Universal Studios",
        "Venice Beach",
        "Getty Museum",
    ],
    "LON": [
        "Big Ben",
        "Tower of London",
        "British Museum",
        "Buckingham Palace",
        "London Eye",
        "Westminster Abbey",
        "Camden Market",
    ],
    "PAR": [
        "Eiffel Tower",
        "Louvre Museum",
        "Notre-Dame",
        "Champs-Élysées",
        "Sacré-Cœur",
        "Versailles Palace",
        "Montmartre",
    ],
    "TYO": [
        "Senso-ji Temple",
        "Tokyo Skytree",
        "Shibuya Crossing",
        "Meiji Shrine",
        "Tsukiji Market",
        "Tokyo Disneyland",
        "Akihabara",
    ],
}

# Booking storage
user_bookings = []
saved_trips = []


# ============================================================================
# Travel Tools
# ============================================================================


def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
    passengers: int = 1,
    cabin_class: str = "economy",
) -> dict[str, Any]:
    """
    Search for available flights.

    Args:
        origin: Origin city code (e.g., NYC, LAX)
        destination: Destination city code
        departure_date: Departure date (YYYY-MM-DD)
        return_date: Optional return date for round trip
        passengers: Number of passengers
        cabin_class: Cabin class (economy, premium_economy, business, first)

    Returns:
        Available flights with prices
    """
    origin = origin.upper()
    destination = destination.upper()

    if origin not in AIRPORTS:
        return {
            "error": f"Unknown origin: {origin}",
            "available_codes": list(AIRPORTS.keys()),
        }
    if destination not in AIRPORTS:
        return {
            "error": f"Unknown destination: {destination}",
            "available_codes": list(AIRPORTS.keys()),
        }

    # Generate sample flights
    cabin_multipliers = {
        "economy": 1.0,
        "premium_economy": 1.5,
        "business": 2.5,
        "first": 4.0,
    }
    multiplier = cabin_multipliers.get(cabin_class.lower(), 1.0)

    base_price = random.randint(150, 500) * multiplier

    flights = []
    for _i in range(4):
        airline = random.choice(AIRLINES)
        dep_hour = random.randint(6, 21)
        duration = random.randint(2, 12)
        stops = 0 if duration < 4 else random.randint(0, 1)

        price = base_price + random.randint(-50, 100)
        if stops == 0:
            price *= 1.15

        flight = {
            "flight_id": f"FL{random.randint(1000, 9999)}",
            "airline": airline,
            "origin": f"{AIRPORTS[origin]['airports'][0]}",
            "destination": f"{AIRPORTS[destination]['airports'][0]}",
            "departure_time": f"{dep_hour:02d}:{random.choice(['00', '15', '30', '45'])}",
            "arrival_time": f"{(dep_hour + duration) % 24:02d}:{random.choice(['00', '15', '30', '45'])}",
            "duration": f"{duration}h {random.randint(0, 59)}m",
            "stops": stops,
            "cabin_class": cabin_class,
            "price_per_person": round(price, 2),
            "total_price": round(price * passengers, 2),
            "seats_available": random.randint(1, 15),
        }
        flights.append(flight)

    # Sort by price
    flights.sort(key=lambda x: x["price_per_person"])

    result = {
        "search": {
            "origin": f"{AIRPORTS[origin]['name']} ({origin})",
            "destination": f"{AIRPORTS[destination]['name']} ({destination})",
            "departure_date": departure_date,
            "return_date": return_date,
            "passengers": passengers,
            "cabin_class": cabin_class,
        },
        "outbound_flights": flights,
    }

    # Add return flights if round trip
    if return_date:
        return_flights = []
        for f in flights:
            rf = f.copy()
            rf["flight_id"] = f"FL{random.randint(1000, 9999)}"
            rf["origin"], rf["destination"] = rf["destination"], rf["origin"]
            rf["price_per_person"] = round(
                rf["price_per_person"] * random.uniform(0.9, 1.1), 2
            )
            rf["total_price"] = round(rf["price_per_person"] * passengers, 2)
            return_flights.append(rf)
        result["return_flights"] = return_flights

    return result


def search_hotels(
    city: str,
    check_in: str,
    check_out: str,
    guests: int = 2,
    rooms: int = 1,
    min_stars: int = 0,
    max_price: int = 10000,
) -> dict[str, Any]:
    """
    Search for available hotels.

    Args:
        city: City code (e.g., NYC, PAR)
        check_in: Check-in date (YYYY-MM-DD)
        check_out: Check-out date (YYYY-MM-DD)
        guests: Number of guests
        rooms: Number of rooms
        min_stars: Minimum star rating
        max_price: Maximum price per night

    Returns:
        Available hotels with prices
    """
    city = city.upper()

    # Get hotels for city
    city_hotels = HOTELS.get(city, DEFAULT_HOTELS)

    # Calculate nights
    try:
        in_date = datetime.strptime(check_in, "%Y-%m-%d")
        out_date = datetime.strptime(check_out, "%Y-%m-%d")
        nights = (out_date - in_date).days
        if nights <= 0:
            return {"error": "Check-out must be after check-in"}
    except ValueError:
        nights = 1

    # Filter and calculate totals
    available_hotels = []
    for hotel in city_hotels:
        if hotel["stars"] >= min_stars and hotel["price_per_night"] <= max_price:
            total = hotel["price_per_night"] * nights * rooms
            available_hotels.append(
                {
                    **hotel,
                    "nights": nights,
                    "rooms": rooms,
                    "total_price": round(total, 2),
                    "price_per_night_per_room": hotel["price_per_night"],
                }
            )

    # Sort by price
    available_hotels.sort(key=lambda x: x["total_price"])

    city_name = AIRPORTS.get(city, {"name": city})["name"]

    return {
        "search": {
            "city": city_name,
            "check_in": check_in,
            "check_out": check_out,
            "nights": nights,
            "guests": guests,
            "rooms": rooms,
        },
        "hotels": available_hotels,
        "best_value": available_hotels[0] if available_hotels else None,
        "highest_rated": (
            max(available_hotels, key=lambda x: x["rating"])
            if available_hotels
            else None
        ),
    }


def get_destination_info(city: str) -> dict[str, Any]:
    """
    Get information about a travel destination.

    Args:
        city: City code

    Returns:
        Destination information including attractions
    """
    city = city.upper()

    if city not in AIRPORTS:
        return {
            "error": f"Unknown city: {city}",
            "available_cities": list(AIRPORTS.keys()),
        }

    attractions = ATTRACTIONS.get(city, ["Various local attractions available"])

    # Generate travel tips
    tips = {
        "NYC": [
            "Get a MetroCard for subway",
            "Book Broadway shows in advance",
            "Try a bagel and pizza",
        ],
        "LAX": [
            "Rent a car for flexibility",
            "Visit during off-peak for better traffic",
            "Don't miss the sunset at Santa Monica",
        ],
        "LON": [
            "Get an Oyster card for transport",
            "Mind the gap!",
            "Try afternoon tea",
        ],
        "PAR": [
            "Learn basic French phrases",
            "Museums closed on Tuesdays",
            "Try the croissants!",
        ],
        "TYO": [
            "Get a JR Pass for trains",
            "Cash is still common",
            "Try conveyor belt sushi",
        ],
    }

    return {
        "city": AIRPORTS[city]["name"],
        "code": city,
        "airports": AIRPORTS[city]["airports"],
        "top_attractions": attractions,
        "travel_tips": tips.get(
            city, ["Research local customs", "Learn basic local phrases"]
        ),
        "best_time_to_visit": "Spring and Fall offer mild weather",
        "currency": (
            "USD"
            if city
            in ["NYC", "LAX", "CHI", "MIA", "SFO", "SEA", "BOS", "DEN", "LAS", "ATL"]
            else "Local currency"
        ),
    }


def create_itinerary(
    city: str,
    days: int,
    interests: list[str] = None,
) -> dict[str, Any]:
    """
    Create a suggested itinerary for a destination.

    Args:
        city: City code
        days: Number of days
        interests: List of interests (culture, food, nature, shopping, nightlife)

    Returns:
        Day-by-day itinerary suggestion
    """
    city = city.upper()
    interests = interests or ["culture", "food"]

    if city not in AIRPORTS:
        return {"error": f"Unknown city: {city}"}

    attractions = ATTRACTIONS.get(city, ["Local sightseeing"])

    itinerary = []
    for day in range(1, min(days + 1, 8)):
        day_plan = {
            "day": day,
            "theme": f"Day {day} Exploration",
            "activities": [],
        }

        # Morning
        morning_attraction = attractions[(day - 1) % len(attractions)]
        day_plan["activities"].append(
            {
                "time": "09:00 - 12:00",
                "activity": f"Visit {morning_attraction}",
                "type": "sightseeing",
            }
        )

        # Lunch
        day_plan["activities"].append(
            {
                "time": "12:00 - 13:30",
                "activity": "Local restaurant for authentic cuisine",
                "type": "dining",
            }
        )

        # Afternoon
        afternoon_attraction = attractions[(day) % len(attractions)]
        day_plan["activities"].append(
            {
                "time": "14:00 - 17:00",
                "activity": f"Explore {afternoon_attraction}",
                "type": "sightseeing",
            }
        )

        # Evening
        evening_activities = {
            "NYC": "Broadway show or jazz club",
            "LAX": "Sunset at the beach",
            "LON": "West End show or pub dinner",
            "PAR": "Seine river walk and dinner",
            "TYO": "Explore the nightlife districts",
        }
        day_plan["activities"].append(
            {
                "time": "18:00 - 22:00",
                "activity": evening_activities.get(city, "Evening entertainment"),
                "type": "evening",
            }
        )

        itinerary.append(day_plan)

    return {
        "destination": AIRPORTS[city]["name"],
        "days": days,
        "interests": interests,
        "itinerary": itinerary,
        "tips": [
            "Adjust timing based on your pace",
            "Book popular attractions in advance",
            "Leave room for spontaneous discoveries",
        ],
    }


def compare_prices(
    origin: str,
    destination: str,
    dates: list[str],
    passengers: int = 1,
) -> dict[str, Any]:
    """
    Compare prices across different dates.

    Args:
        origin: Origin city code
        destination: Destination city code
        dates: List of dates to compare (YYYY-MM-DD format)
        passengers: Number of passengers

    Returns:
        Price comparison across dates
    """
    comparison = []

    for date in dates[:5]:  # Limit to 5 dates
        flights = search_flights(origin, destination, date, passengers=passengers)
        if "outbound_flights" in flights:
            cheapest = flights["outbound_flights"][0]
            comparison.append(
                {
                    "date": date,
                    "cheapest_price": cheapest["price_per_person"],
                    "airline": cheapest["airline"],
                    "departure_time": cheapest["departure_time"],
                }
            )

    # Sort by price
    comparison.sort(key=lambda x: x["cheapest_price"])

    best_date = comparison[0] if comparison else None

    return {
        "origin": origin,
        "destination": destination,
        "passengers": passengers,
        "price_comparison": comparison,
        "best_deal": best_date,
        "potential_savings": (
            round(comparison[-1]["cheapest_price"] - comparison[0]["cheapest_price"], 2)
            if len(comparison) > 1
            else 0
        ),
    }


def book_trip(
    flight_id: str = None,
    hotel_name: str = None,
    traveler_name: str = "Guest",
    traveler_email: str = None,
) -> dict[str, Any]:
    """
    Book a flight and/or hotel.

    Args:
        flight_id: Flight ID to book
        hotel_name: Hotel name to book
        traveler_name: Traveler's name
        traveler_email: Traveler's email

    Returns:
        Booking confirmation
    """
    if not flight_id and not hotel_name:
        return {"error": "Please provide either a flight_id or hotel_name to book"}

    booking_id = f"BK{random.randint(100000, 999999)}"

    booking = {
        "booking_id": booking_id,
        "status": "Confirmed",
        "traveler": {
            "name": traveler_name,
            "email": traveler_email,
        },
        "created_at": datetime.now().isoformat(),
        "components": [],
    }

    if flight_id:
        booking["components"].append(
            {
                "type": "flight",
                "reference": flight_id,
                "status": "Confirmed",
            }
        )

    if hotel_name:
        booking["components"].append(
            {
                "type": "hotel",
                "name": hotel_name,
                "status": "Confirmed",
            }
        )

    user_bookings.append(booking)

    return {
        "success": True,
        "booking": booking,
        "message": "Your booking has been confirmed! A confirmation email will be sent shortly.",
        "next_steps": [
            "Check your email for confirmation",
            "Review cancellation policies",
            "Download your booking details",
        ],
    }


def get_bookings() -> dict[str, Any]:
    """
    Get all user bookings.

    Returns:
        List of bookings
    """
    return {
        "count": len(user_bookings),
        "bookings": user_bookings,
    }


def cancel_booking(booking_id: str) -> dict[str, Any]:
    """
    Cancel a booking.

    Args:
        booking_id: Booking ID to cancel

    Returns:
        Cancellation confirmation
    """
    for booking in user_bookings:
        if booking["booking_id"] == booking_id:
            booking["status"] = "Cancelled"
            return {
                "success": True,
                "message": f"Booking {booking_id} has been cancelled.",
                "refund_info": "Refund will be processed within 5-7 business days.",
            }

    return {"error": f"Booking {booking_id} not found"}


def save_trip(
    trip_name: str,
    origin: str,
    destination: str,
    dates: str,
    notes: str = "",
) -> dict[str, Any]:
    """
    Save a trip idea for later.

    Args:
        trip_name: Name for this trip
        origin: Origin city
        destination: Destination city
        dates: Tentative dates
        notes: Any notes

    Returns:
        Confirmation
    """
    trip = {
        "id": f"TRIP{random.randint(1000, 9999)}",
        "name": trip_name,
        "origin": origin,
        "destination": destination,
        "dates": dates,
        "notes": notes,
        "saved_at": datetime.now().isoformat(),
    }

    saved_trips.append(trip)

    return {
        "success": True,
        "trip": trip,
        "message": f"Trip '{trip_name}' has been saved!",
    }


def get_saved_trips() -> dict[str, Any]:
    """
    Get all saved trip ideas.

    Returns:
        List of saved trips
    """
    return {
        "count": len(saved_trips),
        "trips": saved_trips,
    }


# ============================================================================
# Agent Configuration
# ============================================================================

TRAVEL_TOOLS = [
    {
        "name": "search_flights",
        "description": "Search for available flights between cities. Returns flight options with prices.",
        "function": search_flights,
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "Origin city code (e.g., NYC, LAX, LON)",
                },
                "destination": {
                    "type": "string",
                    "description": "Destination city code",
                },
                "departure_date": {
                    "type": "string",
                    "description": "Departure date (YYYY-MM-DD)",
                },
                "return_date": {
                    "type": "string",
                    "description": "Return date for round trip",
                },
                "passengers": {
                    "type": "integer",
                    "description": "Number of passengers",
                },
                "cabin_class": {
                    "type": "string",
                    "description": "Cabin class: economy, premium_economy, business, first",
                },
            },
            "required": ["origin", "destination", "departure_date"],
        },
    },
    {
        "name": "search_hotels",
        "description": "Search for available hotels in a city",
        "function": search_hotels,
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City code"},
                "check_in": {
                    "type": "string",
                    "description": "Check-in date (YYYY-MM-DD)",
                },
                "check_out": {
                    "type": "string",
                    "description": "Check-out date (YYYY-MM-DD)",
                },
                "guests": {"type": "integer", "description": "Number of guests"},
                "rooms": {"type": "integer", "description": "Number of rooms"},
                "min_stars": {"type": "integer", "description": "Minimum star rating"},
                "max_price": {
                    "type": "integer",
                    "description": "Maximum price per night",
                },
            },
            "required": ["city", "check_in", "check_out"],
        },
    },
    {
        "name": "get_destination_info",
        "description": "Get information about a travel destination including attractions and tips",
        "function": get_destination_info,
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City code"},
            },
            "required": ["city"],
        },
    },
    {
        "name": "create_itinerary",
        "description": "Create a suggested day-by-day itinerary for a destination",
        "function": create_itinerary,
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City code"},
                "days": {"type": "integer", "description": "Number of days"},
                "interests": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Interests: culture, food, nature, shopping, nightlife",
                },
            },
            "required": ["city", "days"],
        },
    },
    {
        "name": "compare_prices",
        "description": "Compare flight prices across different dates to find the best deal",
        "function": compare_prices,
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Origin city code"},
                "destination": {
                    "type": "string",
                    "description": "Destination city code",
                },
                "dates": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of dates to compare",
                },
                "passengers": {
                    "type": "integer",
                    "description": "Number of passengers",
                },
            },
            "required": ["origin", "destination", "dates"],
        },
    },
    {
        "name": "book_trip",
        "description": "Book a flight and/or hotel",
        "function": book_trip,
        "parameters": {
            "type": "object",
            "properties": {
                "flight_id": {"type": "string", "description": "Flight ID to book"},
                "hotel_name": {"type": "string", "description": "Hotel name to book"},
                "traveler_name": {"type": "string", "description": "Traveler's name"},
                "traveler_email": {"type": "string", "description": "Traveler's email"},
            },
        },
    },
    {
        "name": "get_bookings",
        "description": "Get all user bookings",
        "function": get_bookings,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "cancel_booking",
        "description": "Cancel an existing booking",
        "function": cancel_booking,
        "parameters": {
            "type": "object",
            "properties": {
                "booking_id": {"type": "string", "description": "Booking ID to cancel"},
            },
            "required": ["booking_id"],
        },
    },
    {
        "name": "save_trip",
        "description": "Save a trip idea for later planning",
        "function": save_trip,
        "parameters": {
            "type": "object",
            "properties": {
                "trip_name": {"type": "string", "description": "Name for this trip"},
                "origin": {"type": "string", "description": "Origin city"},
                "destination": {"type": "string", "description": "Destination city"},
                "dates": {"type": "string", "description": "Tentative dates"},
                "notes": {"type": "string", "description": "Any notes"},
            },
            "required": ["trip_name", "origin", "destination", "dates"],
        },
    },
    {
        "name": "get_saved_trips",
        "description": "Get all saved trip ideas",
        "function": get_saved_trips,
        "parameters": {"type": "object", "properties": {}},
    },
]

SYSTEM_PROMPT = """You are a friendly travel assistant helping users plan and book their trips.

Your capabilities:
- Search for flights with flexible dates and classes
- Find and compare hotels
- Provide destination information and attractions
- Create day-by-day itineraries
- Compare prices across different dates
- Book flights and hotels
- Manage existing bookings
- Save trip ideas for later

Guidelines:
- Be enthusiastic about travel and destinations
- Proactively suggest the best deals
- Offer itinerary suggestions based on interests
- Consider budget when making recommendations
- Remind users about travel requirements (passport, visas, etc.)
- Be transparent that this is a demonstration system

Available city codes: NYC (New York), LAX (Los Angeles), CHI (Chicago), MIA (Miami),
SFO (San Francisco), SEA (Seattle), BOS (Boston), DEN (Denver), LAS (Las Vegas),
ATL (Atlanta), LON (London), PAR (Paris), TYO (Tokyo), SYD (Sydney)"""


# ============================================================================
# Main Application
# ============================================================================


async def main():
    """Run the Travel & Booking Agent."""
    print("=" * 60)
    print("✈️ Travel & Booking Agent")
    print("=" * 60)
    print("\nWelcome! I can help you plan your perfect trip:")
    print("  • Search for flights and hotels")
    print("  • Discover destinations")
    print("  • Create day-by-day itineraries")
    print("  • Compare prices and find deals")
    print("  • Book and manage your trips")
    print("\n💡 Example questions:")
    print('  "Find flights from NYC to Paris for next month"')
    print('  "What hotels are available in Tokyo?"')
    print('  "Create a 5-day itinerary for London"')
    print('  "Compare flight prices for different dates"')
    print("\nType 'quit' to exit")
    print("-" * 60)

    # Create agent
    agent = Agent(
        name="travel_agent",
        system_prompt=SYSTEM_PROMPT,
        tools=TRAVEL_TOOLS,
    )

    try:
        while True:
            user_input = input("\n✈️ You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                print("\n👋 Bon voyage! Happy travels!")
                break

            # Special commands
            if user_input.lower() == "destinations":
                print("\n🌍 Available Destinations:")
                for code, info in AIRPORTS.items():
                    print(f"  {code}: {info['name']}")
                continue

            if user_input.lower() == "bookings":
                bookings = get_bookings()
                if bookings["count"] == 0:
                    print("\n📋 No bookings yet.")
                else:
                    print(f"\n📋 Your Bookings ({bookings['count']}):")
                    for b in bookings["bookings"]:
                        print(f"  • {b['booking_id']}: {b['status']}")
                continue

            if user_input.lower() == "saved":
                trips = get_saved_trips()
                if trips["count"] == 0:
                    print("\n💾 No saved trips yet.")
                else:
                    print(f"\n💾 Saved Trips ({trips['count']}):")
                    for t in trips["trips"]:
                        print(f"  • {t['name']}: {t['origin']} → {t['destination']}")
                continue

            # Get response from agent
            response = await agent.chat_async(user_input)
            print(f"\n🤖 Agent: {response}")

    except KeyboardInterrupt:
        print("\n\n👋 Safe travels!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
