#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Automotive Service Advisor
==========================

An AI assistant for automotive service operations including service scheduling,
maintenance reminders, issue diagnosis, and parts lookup.

Features:
- Service appointment scheduling
- Maintenance schedule tracking
- Basic issue diagnosis
- Parts information and pricing
- Service history tracking

Run:
    python examples/49_automotive.py

Note:
    This is a demonstration with simulated vehicle data.
    For actual vehicle issues, always consult a qualified mechanic.
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Any

from agentic_brain import Agent

# ============================================================================
# Demo Automotive Data
# ============================================================================

SERVICE_CENTER_INFO = {
    "name": "AutoCare Service Center",
    "address": "456 Auto Drive, Service City",
    "phone": "(555) AUTO-CARE",
    "hours": {
        "Monday-Friday": "7:00 AM - 6:00 PM",
        "Saturday": "8:00 AM - 4:00 PM",
        "Sunday": "Closed",
    },
    "services": [
        "Oil Change",
        "Brake Service",
        "Tire Service",
        "Engine Diagnostics",
        "Transmission",
        "A/C Service",
        "Scheduled Maintenance",
    ],
}

CUSTOMER_VEHICLE = {
    "vehicle_id": "VEH-001",
    "year": 2021,
    "make": "Honda",
    "model": "Accord",
    "trim": "EX-L",
    "vin": "1HGCV********1234",
    "mileage": 45000,
    "color": "Silver",
    "engine": "1.5L Turbo 4-Cylinder",
    "transmission": "CVT Automatic",
    "last_service_date": "2024-01-15",
    "last_service_mileage": 42000,
}

MAINTENANCE_SCHEDULE = {
    "oil_change": {"interval_miles": 5000, "interval_months": 6, "base_cost": 59.99},
    "tire_rotation": {"interval_miles": 7500, "interval_months": 6, "base_cost": 29.99},
    "air_filter": {"interval_miles": 15000, "interval_months": 12, "base_cost": 45.00},
    "cabin_filter": {
        "interval_miles": 15000,
        "interval_months": 12,
        "base_cost": 55.00,
    },
    "brake_inspection": {
        "interval_miles": 15000,
        "interval_months": 12,
        "base_cost": 0,
    },
    "coolant_flush": {
        "interval_miles": 30000,
        "interval_months": 24,
        "base_cost": 149.99,
    },
    "transmission_fluid": {
        "interval_miles": 60000,
        "interval_months": 48,
        "base_cost": 189.99,
    },
    "spark_plugs": {
        "interval_miles": 60000,
        "interval_months": 48,
        "base_cost": 199.99,
    },
    "brake_fluid": {"interval_miles": 30000, "interval_months": 24, "base_cost": 99.99},
    "timing_belt": {
        "interval_miles": 100000,
        "interval_months": 84,
        "base_cost": 799.99,
    },
}

SERVICE_HISTORY = [
    {
        "date": "2024-01-15",
        "mileage": 42000,
        "service": "Oil Change",
        "cost": 64.99,
        "notes": "Synthetic oil",
    },
    {
        "date": "2023-10-05",
        "mileage": 37500,
        "service": "Tire Rotation",
        "cost": 29.99,
        "notes": "Tires in good condition",
    },
    {
        "date": "2023-07-20",
        "mileage": 32000,
        "service": "Oil Change + Air Filter",
        "cost": 109.99,
        "notes": "Replaced air filter",
    },
    {
        "date": "2023-04-10",
        "mileage": 27000,
        "service": "Brake Inspection",
        "cost": 0,
        "notes": "Pads at 60%, no action needed",
    },
    {
        "date": "2023-01-15",
        "mileage": 22000,
        "service": "Oil Change + Tire Rotation",
        "cost": 89.98,
        "notes": "Regular maintenance",
    },
]

COMMON_ISSUES = {
    "check_engine_light": {
        "symptoms": ["Check engine light on", "Engine light illuminated", "MIL on"],
        "possible_causes": [
            "Loose gas cap",
            "Oxygen sensor",
            "Catalytic converter",
            "Mass airflow sensor",
            "Spark plugs",
        ],
        "urgency": "medium",
        "recommendation": "Diagnostic scan recommended to read trouble codes",
        "estimated_diagnosis_cost": 99.99,
    },
    "brakes_squeaking": {
        "symptoms": ["Squeaking brakes", "Brake noise", "Squealing when braking"],
        "possible_causes": [
            "Worn brake pads",
            "Glazed rotors",
            "Dust buildup",
            "Brake hardware issue",
        ],
        "urgency": "high",
        "recommendation": "Brake inspection recommended - safety critical",
        "estimated_diagnosis_cost": 0,
    },
    "battery_issues": {
        "symptoms": [
            "Car won't start",
            "Slow cranking",
            "Battery light",
            "Electrical issues",
        ],
        "possible_causes": [
            "Dead battery",
            "Alternator failure",
            "Corroded terminals",
            "Parasitic drain",
        ],
        "urgency": "high",
        "recommendation": "Battery and charging system test",
        "estimated_diagnosis_cost": 49.99,
    },
    "vibration": {
        "symptoms": ["Steering wheel vibrates", "Car shakes", "Vibration at speed"],
        "possible_causes": [
            "Unbalanced tires",
            "Worn tires",
            "Alignment issue",
            "Worn suspension",
        ],
        "urgency": "medium",
        "recommendation": "Tire balance and suspension inspection",
        "estimated_diagnosis_cost": 49.99,
    },
    "ac_not_cold": {
        "symptoms": ["AC not cooling", "Warm air from AC", "AC not cold"],
        "possible_causes": [
            "Low refrigerant",
            "Compressor issue",
            "Condenser problem",
            "Electrical issue",
        ],
        "urgency": "low",
        "recommendation": "A/C system inspection and recharge",
        "estimated_diagnosis_cost": 79.99,
    },
    "oil_leak": {
        "symptoms": ["Oil spots under car", "Oil smell", "Low oil", "Oil leak"],
        "possible_causes": [
            "Valve cover gasket",
            "Oil pan gasket",
            "Drain plug",
            "Oil filter",
        ],
        "urgency": "medium",
        "recommendation": "Oil leak inspection",
        "estimated_diagnosis_cost": 69.99,
    },
    "transmission": {
        "symptoms": [
            "Rough shifting",
            "Slipping gears",
            "Transmission hesitation",
            "Grinding noise",
        ],
        "possible_causes": [
            "Low fluid",
            "Worn clutches",
            "Solenoid issue",
            "Torque converter",
        ],
        "urgency": "high",
        "recommendation": "Transmission diagnostic - do not delay",
        "estimated_diagnosis_cost": 129.99,
    },
}

PARTS_CATALOG = {
    "oil_filter": {
        "part_number": "HND-OF-001",
        "name": "Oil Filter - Accord",
        "price": 12.99,
        "in_stock": True,
    },
    "air_filter": {
        "part_number": "HND-AF-001",
        "name": "Engine Air Filter - Accord",
        "price": 24.99,
        "in_stock": True,
    },
    "cabin_filter": {
        "part_number": "HND-CF-001",
        "name": "Cabin Air Filter - Accord",
        "price": 34.99,
        "in_stock": True,
    },
    "brake_pads_front": {
        "part_number": "HND-BP-F01",
        "name": "Front Brake Pads - Accord",
        "price": 89.99,
        "in_stock": True,
    },
    "brake_pads_rear": {
        "part_number": "HND-BP-R01",
        "name": "Rear Brake Pads - Accord",
        "price": 79.99,
        "in_stock": True,
    },
    "brake_rotors_front": {
        "part_number": "HND-BR-F01",
        "name": "Front Brake Rotors (pair) - Accord",
        "price": 149.99,
        "in_stock": False,
    },
    "spark_plugs": {
        "part_number": "HND-SP-001",
        "name": "Spark Plugs (set of 4) - Accord Turbo",
        "price": 59.99,
        "in_stock": True,
    },
    "battery": {
        "part_number": "BAT-51R-H7",
        "name": "Battery Group 51R - Honda",
        "price": 189.99,
        "in_stock": True,
    },
    "wiper_blades": {
        "part_number": "WIP-24-19",
        "name": "Wiper Blades Set 24/19 inch",
        "price": 39.99,
        "in_stock": True,
    },
    "synthetic_oil": {
        "part_number": "OIL-0W20-5Q",
        "name": "0W-20 Full Synthetic Oil (5 quarts)",
        "price": 34.99,
        "in_stock": True,
    },
}

# Storage for appointments
scheduled_services = []


# ============================================================================
# Automotive Tools
# ============================================================================


def get_service_center_info() -> dict[str, Any]:
    """
    Get service center information.

    Returns:
        Service center details including hours and services
    """
    return SERVICE_CENTER_INFO


def get_vehicle_info() -> dict[str, Any]:
    """
    Get customer's vehicle information.

    Returns:
        Vehicle details
    """
    return {
        **CUSTOMER_VEHICLE,
        "ownership_years": datetime.now().year - CUSTOMER_VEHICLE["year"],
    }


def get_service_history() -> dict[str, Any]:
    """
    Get vehicle service history.

    Returns:
        List of past services
    """
    total_spent = sum(s["cost"] for s in SERVICE_HISTORY)

    return {
        "vehicle": f"{CUSTOMER_VEHICLE['year']} {CUSTOMER_VEHICLE['make']} {CUSTOMER_VEHICLE['model']}",
        "service_history": SERVICE_HISTORY,
        "total_services": len(SERVICE_HISTORY),
        "total_spent": round(total_spent, 2),
    }


def check_maintenance_due() -> dict[str, Any]:
    """
    Check what maintenance is due or upcoming.

    Returns:
        List of due and upcoming maintenance items
    """
    current_mileage = CUSTOMER_VEHICLE["mileage"]
    last_service_mileage = CUSTOMER_VEHICLE["last_service_mileage"]
    miles_since_service = current_mileage - last_service_mileage

    due_now = []
    upcoming = []

    for service, schedule in MAINTENANCE_SCHEDULE.items():
        service_name = service.replace("_", " ").title()

        if miles_since_service >= schedule["interval_miles"]:
            due_now.append(
                {
                    "service": service_name,
                    "reason": f"Due every {schedule['interval_miles']:,} miles",
                    "estimated_cost": schedule["base_cost"],
                    "priority": "high",
                }
            )
        elif (
            current_mileage % schedule["interval_miles"]
            > schedule["interval_miles"] * 0.8
        ):
            miles_until = schedule["interval_miles"] - (
                current_mileage % schedule["interval_miles"]
            )
            upcoming.append(
                {
                    "service": service_name,
                    "due_at": f"{current_mileage + miles_until:,} miles",
                    "miles_remaining": miles_until,
                    "estimated_cost": schedule["base_cost"],
                }
            )

    return {
        "current_mileage": f"{current_mileage:,}",
        "miles_since_last_service": f"{miles_since_service:,}",
        "due_now": due_now,
        "upcoming": upcoming[:5],
        "recommendation": (
            "Oil change recommended"
            if miles_since_service >= 3000
            else "Vehicle is up to date on maintenance"
        ),
    }


def diagnose_issue(symptoms: str) -> dict[str, Any]:
    """
    Get preliminary diagnosis based on symptoms.

    Args:
        symptoms: Description of the issue or symptoms

    Returns:
        Possible causes and recommendations

    Note: This is a preliminary guide only. Professional inspection recommended.
    """
    symptoms_lower = symptoms.lower()

    for issue_key, issue_data in COMMON_ISSUES.items():
        for symptom in issue_data["symptoms"]:
            if symptom.lower() in symptoms_lower or any(
                word in symptoms_lower for word in symptom.lower().split()
            ):
                return {
                    "matched_issue": issue_key.replace("_", " ").title(),
                    "possible_causes": issue_data["possible_causes"],
                    "urgency": issue_data["urgency"],
                    "recommendation": issue_data["recommendation"],
                    "estimated_diagnosis_cost": issue_data["estimated_diagnosis_cost"],
                    "disclaimer": "⚠️ This is a preliminary assessment only. A professional inspection is recommended for accurate diagnosis.",
                }

    return {
        "message": "I couldn't identify a specific issue from your description.",
        "recommendation": "Please schedule a diagnostic appointment for a professional inspection.",
        "contact": SERVICE_CENTER_INFO["phone"],
        "common_issues_we_handle": list(COMMON_ISSUES.keys()),
    }


def get_service_estimate(service_type: str) -> dict[str, Any]:
    """
    Get an estimate for a specific service.

    Args:
        service_type: Type of service (oil_change, brake_service, tire_rotation, etc.)

    Returns:
        Service details and estimate
    """
    service_estimates = {
        "oil_change": {
            "service": "Oil Change",
            "includes": [
                "Up to 5 quarts synthetic oil",
                "Oil filter",
                "Multi-point inspection",
            ],
            "base_price": 59.99,
            "time_estimate": "30-45 minutes",
        },
        "brake_service": {
            "service": "Brake Pad Replacement",
            "includes": [
                "New brake pads",
                "Rotor inspection",
                "Brake fluid check",
                "Road test",
            ],
            "base_price": 199.99,
            "per_axle": True,
            "time_estimate": "1-2 hours per axle",
        },
        "tire_rotation": {
            "service": "Tire Rotation",
            "includes": [
                "Rotate all 4 tires",
                "Tire pressure adjustment",
                "Visual inspection",
            ],
            "base_price": 29.99,
            "time_estimate": "20-30 minutes",
        },
        "alignment": {
            "service": "Wheel Alignment",
            "includes": [
                "Four-wheel alignment",
                "Steering inspection",
                "Before/after printout",
            ],
            "base_price": 99.99,
            "time_estimate": "45-60 minutes",
        },
        "diagnostic": {
            "service": "Check Engine Diagnostic",
            "includes": [
                "OBD-II scan",
                "Code retrieval",
                "Preliminary diagnosis",
                "Repair estimate",
            ],
            "base_price": 99.99,
            "note": "Diagnostic fee may be waived with repair",
            "time_estimate": "30-60 minutes",
        },
        "ac_service": {
            "service": "A/C Service",
            "includes": ["System inspection", "Refrigerant recharge", "Leak check"],
            "base_price": 149.99,
            "time_estimate": "45-60 minutes",
        },
        "battery": {
            "service": "Battery Replacement",
            "includes": ["New battery", "Terminal cleaning", "Charging system check"],
            "base_price": 189.99,
            "note": "Price includes battery",
            "time_estimate": "15-30 minutes",
        },
        "transmission_service": {
            "service": "Transmission Fluid Service",
            "includes": [
                "Drain and fill",
                "New transmission fluid",
                "Filter inspection",
            ],
            "base_price": 189.99,
            "time_estimate": "1 hour",
        },
    }

    service_key = service_type.lower().replace(" ", "_").replace("-", "_")

    if service_key in service_estimates:
        return {
            **service_estimates[service_key],
            "vehicle": f"{CUSTOMER_VEHICLE['year']} {CUSTOMER_VEHICLE['make']} {CUSTOMER_VEHICLE['model']}",
            "disclaimer": "Prices may vary. Final quote provided after inspection.",
        }

    return {
        "error": f"Service '{service_type}' not found",
        "available_services": list(service_estimates.keys()),
    }


def lookup_part(part_type: str) -> dict[str, Any]:
    """
    Look up parts information and pricing.

    Args:
        part_type: Type of part (oil_filter, brake_pads, battery, etc.)

    Returns:
        Part details and availability
    """
    part_key = part_type.lower().replace(" ", "_").replace("-", "_")

    # Try direct match
    if part_key in PARTS_CATALOG:
        part = PARTS_CATALOG[part_key]
        return {
            "part": part,
            "vehicle_fit": f"{CUSTOMER_VEHICLE['year']} {CUSTOMER_VEHICLE['make']} {CUSTOMER_VEHICLE['model']}",
            "availability": (
                "In Stock" if part["in_stock"] else "Special Order (2-3 days)"
            ),
        }

    # Try partial match
    matches = []
    for key, part in PARTS_CATALOG.items():
        if part_type.lower() in key or part_type.lower() in part["name"].lower():
            matches.append(part)

    if matches:
        return {
            "matches": matches,
            "vehicle": f"{CUSTOMER_VEHICLE['year']} {CUSTOMER_VEHICLE['make']} {CUSTOMER_VEHICLE['model']}",
        }

    return {
        "error": f"Part '{part_type}' not found",
        "available_parts": list(PARTS_CATALOG.keys()),
    }


def schedule_service(
    service_type: str,
    preferred_date: str,
    preferred_time: str,
    name: str,
    phone: str,
    notes: str = "",
) -> dict[str, Any]:
    """
    Schedule a service appointment.

    Args:
        service_type: Type of service
        preferred_date: Preferred date (YYYY-MM-DD)
        preferred_time: Preferred time (morning, afternoon, or specific time)
        name: Customer name
        phone: Contact phone
        notes: Additional notes or concerns

    Returns:
        Appointment confirmation
    """
    appointment_id = f"SVC{random.randint(10000, 99999)}"

    appointment = {
        "appointment_id": appointment_id,
        "service": service_type,
        "vehicle": f"{CUSTOMER_VEHICLE['year']} {CUSTOMER_VEHICLE['make']} {CUSTOMER_VEHICLE['model']}",
        "date": preferred_date,
        "time": preferred_time,
        "customer": name,
        "phone": phone,
        "notes": notes,
        "status": "Confirmed",
        "created_at": datetime.now().isoformat(),
    }

    scheduled_services.append(appointment)

    return {
        "success": True,
        "appointment": appointment,
        "message": f"Your {service_type} appointment is confirmed for {preferred_date} at {preferred_time}.",
        "reminders": [
            "Please arrive 10 minutes early",
            "Bring your driver's license",
            "We'll contact you with updates",
        ],
        "cancellation_policy": "Please call at least 24 hours in advance to reschedule or cancel.",
    }


def get_scheduled_services() -> dict[str, Any]:
    """
    Get scheduled service appointments.

    Returns:
        List of scheduled appointments
    """
    return {
        "appointments": scheduled_services,
        "count": len(scheduled_services),
    }


def cancel_service(appointment_id: str) -> dict[str, Any]:
    """
    Cancel a service appointment.

    Args:
        appointment_id: Appointment ID

    Returns:
        Cancellation confirmation
    """
    for appt in scheduled_services:
        if appt["appointment_id"] == appointment_id.upper():
            appt["status"] = "Cancelled"
            return {
                "success": True,
                "message": f"Appointment {appointment_id} has been cancelled.",
                "reschedule": "Would you like to reschedule for another time?",
            }

    return {"error": f"Appointment {appointment_id} not found"}


def get_recall_info() -> dict[str, Any]:
    """
    Check for any recalls on the vehicle.

    Returns:
        Recall information
    """
    # Simulated - in production, would check NHTSA database
    return {
        "vehicle": f"{CUSTOMER_VEHICLE['year']} {CUSTOMER_VEHICLE['make']} {CUSTOMER_VEHICLE['model']}",
        "open_recalls": [],
        "message": "No open recalls found for your vehicle.",
        "note": "For complete recall information, visit NHTSA.gov or your dealer.",
        "last_checked": datetime.now().strftime("%Y-%m-%d"),
    }


def calculate_tire_life(current_tread_depth: float = 6.0) -> dict[str, Any]:
    """
    Estimate remaining tire life.

    Args:
        current_tread_depth: Current tread depth in 32nds of an inch (new = 10/32, min = 2/32)

    Returns:
        Tire life estimate
    """
    new_tread = 10.0  # 10/32 inch when new
    min_tread = 2.0  # 2/32 inch minimum safe

    if current_tread_depth <= min_tread:
        return {
            "status": "REPLACE NOW",
            "remaining": 0,
            "urgent": True,
            "message": "Tires are at or below minimum safe tread depth. Replace immediately.",
        }

    usable_tread = new_tread - min_tread
    remaining_tread = current_tread_depth - min_tread
    percentage_remaining = (remaining_tread / usable_tread) * 100

    avg_miles_per_year = 12000
    total_tire_miles = 50000
    miles_remaining = total_tire_miles * (remaining_tread / usable_tread)
    months_remaining = (miles_remaining / avg_miles_per_year) * 12

    status = (
        "Good"
        if percentage_remaining > 50
        else "Fair" if percentage_remaining > 25 else "Replace Soon"
    )

    return {
        "current_tread": f"{current_tread_depth}/32 inch",
        "minimum_safe": f"{min_tread}/32 inch",
        "percentage_remaining": round(percentage_remaining, 1),
        "estimated_miles_remaining": round(miles_remaining, 0),
        "estimated_months_remaining": round(months_remaining, 0),
        "status": status,
        "recommendation": (
            "Schedule tire replacement"
            if status == "Replace Soon"
            else "Continue monitoring"
        ),
    }


# ============================================================================
# Agent Configuration
# ============================================================================

AUTOMOTIVE_TOOLS = [
    {
        "name": "get_service_center_info",
        "description": "Get service center information including hours and services offered",
        "function": get_service_center_info,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_vehicle_info",
        "description": "Get customer's vehicle information",
        "function": get_vehicle_info,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_service_history",
        "description": "Get vehicle service history",
        "function": get_service_history,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "check_maintenance_due",
        "description": "Check what maintenance is due or upcoming based on mileage",
        "function": check_maintenance_due,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "diagnose_issue",
        "description": "Get preliminary diagnosis based on symptoms described",
        "function": diagnose_issue,
        "parameters": {
            "type": "object",
            "properties": {
                "symptoms": {
                    "type": "string",
                    "description": "Description of the issue or symptoms",
                },
            },
            "required": ["symptoms"],
        },
    },
    {
        "name": "get_service_estimate",
        "description": "Get an estimate for a specific service",
        "function": get_service_estimate,
        "parameters": {
            "type": "object",
            "properties": {
                "service_type": {"type": "string", "description": "Type of service"},
            },
            "required": ["service_type"],
        },
    },
    {
        "name": "lookup_part",
        "description": "Look up parts information, pricing, and availability",
        "function": lookup_part,
        "parameters": {
            "type": "object",
            "properties": {
                "part_type": {"type": "string", "description": "Type of part"},
            },
            "required": ["part_type"],
        },
    },
    {
        "name": "schedule_service",
        "description": "Schedule a service appointment",
        "function": schedule_service,
        "parameters": {
            "type": "object",
            "properties": {
                "service_type": {"type": "string", "description": "Type of service"},
                "preferred_date": {
                    "type": "string",
                    "description": "Preferred date (YYYY-MM-DD)",
                },
                "preferred_time": {"type": "string", "description": "Preferred time"},
                "name": {"type": "string", "description": "Customer name"},
                "phone": {"type": "string", "description": "Contact phone"},
                "notes": {"type": "string", "description": "Additional notes"},
            },
            "required": [
                "service_type",
                "preferred_date",
                "preferred_time",
                "name",
                "phone",
            ],
        },
    },
    {
        "name": "get_scheduled_services",
        "description": "Get scheduled service appointments",
        "function": get_scheduled_services,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "cancel_service",
        "description": "Cancel a service appointment",
        "function": cancel_service,
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string", "description": "Appointment ID"},
            },
            "required": ["appointment_id"],
        },
    },
    {
        "name": "get_recall_info",
        "description": "Check for any recalls on the vehicle",
        "function": get_recall_info,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "calculate_tire_life",
        "description": "Estimate remaining tire life based on tread depth",
        "function": calculate_tire_life,
        "parameters": {
            "type": "object",
            "properties": {
                "current_tread_depth": {
                    "type": "number",
                    "description": "Current tread depth in 32nds of an inch",
                },
            },
        },
    },
]

SYSTEM_PROMPT = """You are a friendly automotive service advisor at AutoCare Service Center.

Your capabilities:
- Check vehicle information and service history
- Identify what maintenance is due
- Provide preliminary diagnoses for issues
- Give service estimates
- Look up parts and pricing
- Schedule service appointments
- Check for vehicle recalls

Guidelines:
- Be helpful and knowledgeable about automotive service
- Always recommend professional inspection for complex issues
- Prioritize safety-critical items (brakes, tires, steering)
- Explain services in clear, non-technical terms
- Be transparent about pricing and what's included
- Never diagnose definitively - recommend inspection

Vehicle on file: 2021 Honda Accord EX-L with 45,000 miles

Services we offer: Oil Change, Brake Service, Tire Service, Engine Diagnostics,
Transmission Service, A/C Service, Scheduled Maintenance, and more.

Remember: Safety first! Always recommend professional inspection for any safety concerns."""


# ============================================================================
# Main Application
# ============================================================================


async def main():
    """Run the Automotive Service Advisor."""
    print("=" * 60)
    print("🚗 AutoCare Service Center - Service Advisor")
    print("=" * 60)
    print("\nWelcome! I can help you with:")
    print("  • Check your maintenance schedule")
    print("  • Diagnose vehicle issues")
    print("  • Get service estimates")
    print("  • Schedule service appointments")
    print("  • Look up parts and pricing")
    print("\n💡 Example questions:")
    print('  "Is my car due for any maintenance?"')
    print('  "My check engine light is on"')
    print('  "How much for an oil change?"')
    print('  "I need to schedule brake service"')
    print("\nType 'quit' to exit")
    print("-" * 60)

    # Create agent
    agent = Agent(
        name="service_advisor",
        system_prompt=SYSTEM_PROMPT,
        tools=AUTOMOTIVE_TOOLS,
    )

    try:
        while True:
            user_input = input("\n🚗 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                print("\n👋 Thanks for choosing AutoCare Service Center!")
                print("Drive safe!")
                break

            # Special commands
            if user_input.lower() == "vehicle":
                vehicle = get_vehicle_info()
                print("\n🚙 Your Vehicle:")
                print(
                    f"  {vehicle['year']} {vehicle['make']} {vehicle['model']} {vehicle['trim']}"
                )
                print(f"  Mileage: {vehicle['mileage']:,}")
                continue

            if user_input.lower() == "history":
                history = get_service_history()
                print("\n📋 Service History:")
                for s in history["service_history"][:5]:
                    print(f"  {s['date']}: {s['service']} - ${s['cost']:.2f}")
                continue

            if user_input.lower() == "hours":
                info = get_service_center_info()
                print("\n⏰ Hours:")
                for day, hours in info["hours"].items():
                    print(f"  {day}: {hours}")
                continue

            # Get response from agent
            response = await agent.chat_async(user_input)
            print(f"\n🔧 Advisor: {response}")

    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
