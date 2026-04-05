#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Patient Portal Assistant
========================

An AI assistant for patient portal operations including appointment scheduling,
prescription refills, test results explanation, and provider messaging.

Features:
- Appointment scheduling and management
- Prescription refill requests
- Test results viewing and explanation
- Secure messaging with providers
- Health record access

Run:
    python examples/47_healthcare_portal.py

IMPORTANT DISCLAIMERS:
    ⚠️  This is a DEMONSTRATION system with simulated data only.
    ⚠️  This is NOT a real healthcare system.
    ⚠️  This does NOT provide medical advice.
    ⚠️  Always consult qualified healthcare professionals for medical concerns.
    ⚠️  In case of emergency, call emergency services (911).
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Any

from agentic_brain import Agent

# ============================================================================
# Demo Healthcare Data
# ============================================================================

PATIENT_INFO = {
    "patient_id": "PAT-12345",
    "name": "Demo Patient",
    "date_of_birth": "1985-06-15",
    "primary_care_provider": "Dr. Sarah Johnson",
    "insurance": "Demo Health Insurance",
    "allergies": ["Penicillin", "Sulfa drugs"],
    "emergency_contact": "Emergency Contact (555-0100)",
}

PROVIDERS = {
    "DR001": {
        "name": "Dr. Sarah Johnson",
        "specialty": "Internal Medicine",
        "department": "Primary Care",
        "availability": ["Monday", "Tuesday", "Thursday", "Friday"],
    },
    "DR002": {
        "name": "Dr. Michael Chen",
        "specialty": "Cardiology",
        "department": "Heart Center",
        "availability": ["Monday", "Wednesday", "Friday"],
    },
    "DR003": {
        "name": "Dr. Emily Rodriguez",
        "specialty": "Dermatology",
        "department": "Skin Health",
        "availability": ["Tuesday", "Wednesday", "Thursday"],
    },
    "DR004": {
        "name": "Dr. James Wilson",
        "specialty": "Orthopedics",
        "department": "Bone & Joint Center",
        "availability": ["Monday", "Tuesday", "Thursday"],
    },
}

PRESCRIPTIONS = [
    {
        "id": "RX-001",
        "medication": "Lisinopril 10mg",
        "instructions": "Take 1 tablet by mouth once daily",
        "prescriber": "Dr. Sarah Johnson",
        "refills_remaining": 2,
        "last_filled": "2024-01-15",
        "pharmacy": "Demo Pharmacy - Main Street",
        "status": "Active",
    },
    {
        "id": "RX-002",
        "medication": "Metformin 500mg",
        "instructions": "Take 1 tablet by mouth twice daily with meals",
        "prescriber": "Dr. Sarah Johnson",
        "refills_remaining": 5,
        "last_filled": "2024-01-10",
        "pharmacy": "Demo Pharmacy - Main Street",
        "status": "Active",
    },
    {
        "id": "RX-003",
        "medication": "Vitamin D3 2000 IU",
        "instructions": "Take 1 capsule by mouth daily",
        "prescriber": "Dr. Sarah Johnson",
        "refills_remaining": 11,
        "last_filled": "2024-01-20",
        "pharmacy": "Demo Pharmacy - Main Street",
        "status": "Active",
    },
]

TEST_RESULTS = [
    {
        "id": "LAB-001",
        "test_name": "Complete Blood Count (CBC)",
        "date": "2024-01-28",
        "status": "Final",
        "ordering_provider": "Dr. Sarah Johnson",
        "results": [
            {
                "component": "White Blood Cells",
                "value": "7.2",
                "unit": "K/uL",
                "range": "4.5-11.0",
                "flag": "Normal",
            },
            {
                "component": "Red Blood Cells",
                "value": "4.8",
                "unit": "M/uL",
                "range": "4.5-5.5",
                "flag": "Normal",
            },
            {
                "component": "Hemoglobin",
                "value": "14.2",
                "unit": "g/dL",
                "range": "13.5-17.5",
                "flag": "Normal",
            },
            {
                "component": "Hematocrit",
                "value": "42",
                "unit": "%",
                "range": "38-50",
                "flag": "Normal",
            },
            {
                "component": "Platelets",
                "value": "245",
                "unit": "K/uL",
                "range": "150-400",
                "flag": "Normal",
            },
        ],
        "interpretation": "All values within normal limits.",
    },
    {
        "id": "LAB-002",
        "test_name": "Basic Metabolic Panel",
        "date": "2024-01-28",
        "status": "Final",
        "ordering_provider": "Dr. Sarah Johnson",
        "results": [
            {
                "component": "Glucose",
                "value": "105",
                "unit": "mg/dL",
                "range": "70-100",
                "flag": "High",
            },
            {
                "component": "Sodium",
                "value": "140",
                "unit": "mEq/L",
                "range": "136-145",
                "flag": "Normal",
            },
            {
                "component": "Potassium",
                "value": "4.2",
                "unit": "mEq/L",
                "range": "3.5-5.0",
                "flag": "Normal",
            },
            {
                "component": "Creatinine",
                "value": "0.9",
                "unit": "mg/dL",
                "range": "0.7-1.3",
                "flag": "Normal",
            },
        ],
        "interpretation": "Glucose slightly elevated. Continue monitoring.",
    },
    {
        "id": "LAB-003",
        "test_name": "Lipid Panel",
        "date": "2024-01-15",
        "status": "Final",
        "ordering_provider": "Dr. Michael Chen",
        "results": [
            {
                "component": "Total Cholesterol",
                "value": "195",
                "unit": "mg/dL",
                "range": "<200",
                "flag": "Normal",
            },
            {
                "component": "LDL Cholesterol",
                "value": "110",
                "unit": "mg/dL",
                "range": "<100",
                "flag": "High",
            },
            {
                "component": "HDL Cholesterol",
                "value": "55",
                "unit": "mg/dL",
                "range": ">40",
                "flag": "Normal",
            },
            {
                "component": "Triglycerides",
                "value": "150",
                "unit": "mg/dL",
                "range": "<150",
                "flag": "Borderline",
            },
        ],
        "interpretation": "LDL slightly elevated. Consider lifestyle modifications.",
    },
]

# Storage for appointments and messages
appointments = [
    {
        "id": "APT-001",
        "date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        "time": "10:00 AM",
        "provider": "Dr. Sarah Johnson",
        "type": "Annual Physical",
        "location": "Primary Care - Suite 200",
        "status": "Confirmed",
    },
]

messages = [
    {
        "id": "MSG-001",
        "date": "2024-01-25",
        "from": "Dr. Sarah Johnson",
        "subject": "Lab Results Review",
        "body": "Your recent lab results look good overall. Your glucose was slightly elevated - please continue monitoring and we'll discuss at your next appointment.",
        "read": True,
    },
]


# ============================================================================
# Healthcare Tools
# ============================================================================


def get_patient_summary() -> dict[str, Any]:
    """
    Get patient profile summary.

    Returns:
        Patient information summary
    """
    return {
        **PATIENT_INFO,
        "upcoming_appointments": len(
            [a for a in appointments if a["status"] == "Confirmed"]
        ),
        "active_prescriptions": len(
            [p for p in PRESCRIPTIONS if p["status"] == "Active"]
        ),
        "unread_messages": len([m for m in messages if not m["read"]]),
        "disclaimer": "This is simulated patient data for demonstration only.",
    }


def get_appointments(include_past: bool = False) -> dict[str, Any]:
    """
    Get scheduled appointments.

    Args:
        include_past: Include past appointments

    Returns:
        List of appointments
    """
    today = datetime.now().strftime("%Y-%m-%d")

    if include_past:
        appts = appointments
    else:
        appts = [a for a in appointments if a["date"] >= today]

    return {
        "appointments": appts,
        "count": len(appts),
        "next_appointment": appts[0] if appts else None,
    }


def schedule_appointment(
    provider_id: str,
    appointment_type: str,
    preferred_date: str,
    preferred_time: str,
    reason: str = "",
) -> dict[str, Any]:
    """
    Request to schedule an appointment.

    Args:
        provider_id: Provider ID (DR001, DR002, etc.)
        appointment_type: Type of visit (checkup, follow-up, consultation)
        preferred_date: Preferred date (YYYY-MM-DD)
        preferred_time: Preferred time (morning, afternoon, or specific time)
        reason: Reason for visit

    Returns:
        Appointment request confirmation
    """
    if provider_id.upper() not in PROVIDERS:
        return {
            "error": f"Provider {provider_id} not found",
            "available_providers": [
                {"id": pid, "name": p["name"], "specialty": p["specialty"]}
                for pid, p in PROVIDERS.items()
            ],
        }

    provider = PROVIDERS[provider_id.upper()]

    # Create appointment request
    appt_id = f"APT-{random.randint(100, 999)}"

    new_appointment = {
        "id": appt_id,
        "date": preferred_date,
        "time": preferred_time,
        "provider": provider["name"],
        "type": appointment_type,
        "location": f"{provider['department']} - Main Campus",
        "status": "Pending Confirmation",
        "reason": reason,
    }

    appointments.append(new_appointment)

    return {
        "success": True,
        "appointment": new_appointment,
        "message": "Appointment request submitted. You will receive confirmation within 24-48 hours.",
        "note": "This is a simulated appointment for demonstration purposes.",
    }


def cancel_appointment(appointment_id: str, reason: str = "") -> dict[str, Any]:
    """
    Cancel an appointment.

    Args:
        appointment_id: Appointment ID
        reason: Reason for cancellation

    Returns:
        Cancellation confirmation
    """
    for appt in appointments:
        if appt["id"] == appointment_id.upper():
            appt["status"] = "Cancelled"
            return {
                "success": True,
                "message": f"Appointment {appointment_id} has been cancelled.",
                "reschedule_info": "Please call or use this portal to reschedule if needed.",
            }

    return {"error": f"Appointment {appointment_id} not found"}


def get_prescriptions() -> dict[str, Any]:
    """
    Get active prescriptions.

    Returns:
        List of prescriptions
    """
    active = [p for p in PRESCRIPTIONS if p["status"] == "Active"]

    # Check for refill needed
    for p in active:
        if p["refills_remaining"] <= 1:
            p["refill_alert"] = "Low refills - contact provider for renewal"

    return {
        "prescriptions": active,
        "count": len(active),
        "pharmacy": "Demo Pharmacy - Main Street",
        "disclaimer": "This is simulated prescription data.",
    }


def request_refill(prescription_id: str, pharmacy_notes: str = "") -> dict[str, Any]:
    """
    Request a prescription refill.

    Args:
        prescription_id: Prescription ID (RX-001, etc.)
        pharmacy_notes: Optional notes for pharmacy

    Returns:
        Refill request confirmation
    """
    for rx in PRESCRIPTIONS:
        if rx["id"] == prescription_id.upper():
            if rx["refills_remaining"] <= 0:
                return {
                    "error": "No refills remaining",
                    "action_required": "Contact your provider for a new prescription.",
                }

            refill_id = f"REF-{random.randint(10000, 99999)}"

            return {
                "success": True,
                "refill_id": refill_id,
                "medication": rx["medication"],
                "pharmacy": rx["pharmacy"],
                "estimated_ready": (datetime.now() + timedelta(hours=4)).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "message": "Refill request submitted. Your pharmacy will notify you when ready.",
                "note": "This is a simulated refill request.",
            }

    return {"error": f"Prescription {prescription_id} not found"}


def get_test_results(result_id: str = None) -> dict[str, Any]:
    """
    Get test results.

    Args:
        result_id: Specific result ID, or None for all recent results

    Returns:
        Test results with explanations
    """
    if result_id:
        for result in TEST_RESULTS:
            if result["id"] == result_id.upper():
                return {
                    "result": result,
                    "disclaimer": "For a complete understanding of your results, please discuss with your healthcare provider.",
                }
        return {"error": f"Result {result_id} not found"}

    return {
        "results": TEST_RESULTS,
        "count": len(TEST_RESULTS),
        "disclaimer": "These are simulated test results for demonstration. Always consult your healthcare provider for interpretation.",
    }


def explain_test_result(result_id: str, component: str = None) -> dict[str, Any]:
    """
    Get explanation for test results.

    Args:
        result_id: Test result ID
        component: Specific component to explain

    Returns:
        Educational explanation (not medical advice)

    DISCLAIMER: This is general educational information only.
    """
    explanations = {
        "White Blood Cells": "White blood cells help fight infection. Normal levels indicate a healthy immune system.",
        "Red Blood Cells": "Red blood cells carry oxygen throughout your body.",
        "Hemoglobin": "Hemoglobin is the protein in red blood cells that carries oxygen.",
        "Glucose": "Glucose is your blood sugar level. Elevated levels may indicate diabetes risk.",
        "Total Cholesterol": "Total cholesterol is the overall amount of cholesterol in your blood.",
        "LDL Cholesterol": "LDL is often called 'bad' cholesterol. Lower levels are generally better.",
        "HDL Cholesterol": "HDL is 'good' cholesterol. Higher levels are generally protective.",
        "Triglycerides": "Triglycerides are a type of fat in your blood from foods you eat.",
    }

    for result in TEST_RESULTS:
        if result["id"] == result_id.upper():
            if component:
                for comp in result["results"]:
                    if component.lower() in comp["component"].lower():
                        return {
                            "component": comp,
                            "explanation": explanations.get(
                                comp["component"],
                                "Please consult your provider for interpretation.",
                            ),
                            "disclaimer": "⚠️ This is general educational information only. Consult your healthcare provider for personalized medical advice.",
                        }
                return {"error": f"Component '{component}' not found in this test"}

            return {
                "test_name": result["test_name"],
                "interpretation": result["interpretation"],
                "components_explained": {
                    c["component"]: explanations.get(c["component"], "Consult provider")
                    for c in result["results"]
                },
                "disclaimer": "⚠️ This is general educational information only. Always discuss results with your healthcare provider.",
            }

    return {"error": f"Result {result_id} not found"}


def get_messages(unread_only: bool = False) -> dict[str, Any]:
    """
    Get messages from healthcare providers.

    Args:
        unread_only: Show only unread messages

    Returns:
        List of messages
    """
    if unread_only:
        msgs = [m for m in messages if not m["read"]]
    else:
        msgs = messages

    return {
        "messages": msgs,
        "unread_count": len([m for m in messages if not m["read"]]),
        "total_count": len(messages),
    }


def send_message(
    provider_id: str,
    subject: str,
    message_body: str,
) -> dict[str, Any]:
    """
    Send a secure message to a healthcare provider.

    Args:
        provider_id: Provider ID
        subject: Message subject
        message_body: Message content

    Returns:
        Message confirmation

    Note: For urgent issues, call the office or emergency services.
    """
    if provider_id.upper() not in PROVIDERS:
        return {
            "error": f"Provider {provider_id} not found",
            "available_providers": list(PROVIDERS.keys()),
        }

    provider = PROVIDERS[provider_id.upper()]
    msg_id = f"MSG-{random.randint(100, 999)}"

    new_message = {
        "id": msg_id,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "to": provider["name"],
        "subject": subject,
        "body": message_body,
        "status": "Sent",
    }

    return {
        "success": True,
        "message_id": msg_id,
        "sent_to": provider["name"],
        "response_time": "Typically 2-3 business days",
        "urgent_note": "⚠️ For urgent medical concerns, please call the office directly or go to the emergency room.",
    }


def get_health_education(topic: str) -> dict[str, Any]:
    """
    Get health education information.

    Args:
        topic: Health topic (diabetes, heart health, nutrition, exercise, etc.)

    Returns:
        Educational content

    DISCLAIMER: This is general health information, not medical advice.
    """
    topics = {
        "diabetes": {
            "overview": "Diabetes is a condition that affects how your body uses blood sugar (glucose).",
            "key_points": [
                "Monitor blood sugar levels as recommended",
                "Maintain a healthy diet and exercise regularly",
                "Take medications as prescribed",
                "Attend regular check-ups",
            ],
            "warning_signs": [
                "Increased thirst",
                "Frequent urination",
                "Fatigue",
                "Blurred vision",
            ],
        },
        "heart_health": {
            "overview": "Heart health involves maintaining a healthy cardiovascular system.",
            "key_points": [
                "Maintain healthy cholesterol and blood pressure",
                "Exercise regularly (150 minutes/week recommended)",
                "Eat a heart-healthy diet",
                "Avoid smoking and limit alcohol",
            ],
            "warning_signs": [
                "Chest pain",
                "Shortness of breath",
                "Irregular heartbeat",
            ],
        },
        "nutrition": {
            "overview": "Good nutrition is fundamental to overall health.",
            "key_points": [
                "Eat plenty of fruits and vegetables",
                "Choose whole grains over refined grains",
                "Limit processed foods and added sugars",
                "Stay hydrated with water",
            ],
            "tips": [
                "Read nutrition labels",
                "Plan meals ahead",
                "Practice portion control",
            ],
        },
        "exercise": {
            "overview": "Regular physical activity is essential for health.",
            "key_points": [
                "Aim for 150 minutes of moderate activity per week",
                "Include strength training 2+ times per week",
                "Find activities you enjoy",
                "Start slowly and increase gradually",
            ],
            "benefits": [
                "Improved heart health",
                "Better mood",
                "Weight management",
                "Better sleep",
            ],
        },
    }

    topic_lower = topic.lower().replace(" ", "_")

    if topic_lower in topics:
        return {
            "topic": topic,
            **topics[topic_lower],
            "disclaimer": "⚠️ This is general health information for educational purposes only. It is not medical advice. Always consult your healthcare provider for personalized recommendations.",
        }

    return {
        "available_topics": list(topics.keys()),
        "message": f"Topic '{topic}' not found. Choose from available topics.",
        "disclaimer": "For specific health questions, please consult your healthcare provider.",
    }


def get_providers(specialty: str = None) -> dict[str, Any]:
    """
    Get list of available providers.

    Args:
        specialty: Filter by specialty

    Returns:
        List of providers
    """
    providers_list = []

    for pid, prov in PROVIDERS.items():
        if specialty and specialty.lower() not in prov["specialty"].lower():
            continue
        providers_list.append(
            {
                "id": pid,
                **prov,
            }
        )

    return {
        "providers": providers_list,
        "count": len(providers_list),
    }


# ============================================================================
# Agent Configuration
# ============================================================================

HEALTHCARE_TOOLS = [
    {
        "name": "get_patient_summary",
        "description": "Get patient profile summary with key information",
        "function": get_patient_summary,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_appointments",
        "description": "Get scheduled appointments",
        "function": get_appointments,
        "parameters": {
            "type": "object",
            "properties": {
                "include_past": {
                    "type": "boolean",
                    "description": "Include past appointments",
                },
            },
        },
    },
    {
        "name": "schedule_appointment",
        "description": "Request to schedule an appointment with a provider",
        "function": schedule_appointment,
        "parameters": {
            "type": "object",
            "properties": {
                "provider_id": {"type": "string", "description": "Provider ID"},
                "appointment_type": {"type": "string", "description": "Type of visit"},
                "preferred_date": {
                    "type": "string",
                    "description": "Preferred date (YYYY-MM-DD)",
                },
                "preferred_time": {"type": "string", "description": "Preferred time"},
                "reason": {"type": "string", "description": "Reason for visit"},
            },
            "required": [
                "provider_id",
                "appointment_type",
                "preferred_date",
                "preferred_time",
            ],
        },
    },
    {
        "name": "cancel_appointment",
        "description": "Cancel an appointment",
        "function": cancel_appointment,
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string", "description": "Appointment ID"},
                "reason": {"type": "string", "description": "Reason for cancellation"},
            },
            "required": ["appointment_id"],
        },
    },
    {
        "name": "get_prescriptions",
        "description": "Get active prescriptions",
        "function": get_prescriptions,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "request_refill",
        "description": "Request a prescription refill",
        "function": request_refill,
        "parameters": {
            "type": "object",
            "properties": {
                "prescription_id": {"type": "string", "description": "Prescription ID"},
                "pharmacy_notes": {
                    "type": "string",
                    "description": "Notes for pharmacy",
                },
            },
            "required": ["prescription_id"],
        },
    },
    {
        "name": "get_test_results",
        "description": "Get test results",
        "function": get_test_results,
        "parameters": {
            "type": "object",
            "properties": {
                "result_id": {"type": "string", "description": "Specific result ID"},
            },
        },
    },
    {
        "name": "explain_test_result",
        "description": "Get educational explanation for test results (not medical advice)",
        "function": explain_test_result,
        "parameters": {
            "type": "object",
            "properties": {
                "result_id": {"type": "string", "description": "Test result ID"},
                "component": {"type": "string", "description": "Specific component"},
            },
            "required": ["result_id"],
        },
    },
    {
        "name": "get_messages",
        "description": "Get messages from healthcare providers",
        "function": get_messages,
        "parameters": {
            "type": "object",
            "properties": {
                "unread_only": {"type": "boolean", "description": "Show only unread"},
            },
        },
    },
    {
        "name": "send_message",
        "description": "Send a secure message to a healthcare provider",
        "function": send_message,
        "parameters": {
            "type": "object",
            "properties": {
                "provider_id": {"type": "string", "description": "Provider ID"},
                "subject": {"type": "string", "description": "Message subject"},
                "message_body": {"type": "string", "description": "Message content"},
            },
            "required": ["provider_id", "subject", "message_body"],
        },
    },
    {
        "name": "get_health_education",
        "description": "Get health education information on a topic",
        "function": get_health_education,
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Health topic"},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "get_providers",
        "description": "Get list of available healthcare providers",
        "function": get_providers,
        "parameters": {
            "type": "object",
            "properties": {
                "specialty": {"type": "string", "description": "Filter by specialty"},
            },
        },
    },
]

SYSTEM_PROMPT = """You are a patient portal assistant helping patients navigate their healthcare information.

Your capabilities:
- View and manage appointments
- Access prescription information and request refills
- View test results with general explanations
- Send messages to healthcare providers
- Provide general health education

⚠️ CRITICAL GUIDELINES:
1. This is a DEMONSTRATION system with SIMULATED data only
2. NEVER provide specific medical advice or diagnoses
3. Always recommend consulting healthcare providers for medical questions
4. For emergencies, direct patients to call 911 or go to the ER
5. Clearly state that explanations are educational, not medical advice
6. Be empathetic and supportive

Standard disclaimers to include:
- "This is general information, not medical advice"
- "Please consult your healthcare provider for personalized guidance"
- "For urgent concerns, contact your provider's office or emergency services"

Available providers: DR001 (Internal Medicine), DR002 (Cardiology), DR003 (Dermatology), DR004 (Orthopedics)"""


# ============================================================================
# Main Application
# ============================================================================


async def main():
    """Run the Patient Portal Assistant."""
    print("=" * 60)
    print("🏥 Patient Portal Assistant")
    print("=" * 60)
    print("\n⚠️  IMPORTANT NOTICES:")
    print("    • This is a DEMONSTRATION with simulated data")
    print("    • This is NOT a real healthcare system")
    print("    • This does NOT provide medical advice")
    print("    • For emergencies, call 911")
    print("\nI can help you with:")
    print("  • Viewing and scheduling appointments")
    print("  • Prescription refill requests")
    print("  • Viewing test results")
    print("  • Messaging your provider")
    print("  • General health information")
    print("\n💡 Example questions:")
    print('  "Show my upcoming appointments"')
    print('  "What are my current prescriptions?"')
    print('  "Show my recent lab results"')
    print('  "Tell me about heart health"')
    print("\nType 'quit' to exit")
    print("-" * 60)

    # Create agent
    agent = Agent(
        name="healthcare_assistant",
        system_prompt=SYSTEM_PROMPT,
        tools=HEALTHCARE_TOOLS,
    )

    try:
        while True:
            user_input = input("\n🏥 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                print("\n👋 Thank you for using the Patient Portal. Stay healthy!")
                break

            # Emergency check
            emergency_words = [
                "emergency",
                "chest pain",
                "can't breathe",
                "severe pain",
                "heart attack",
                "stroke",
            ]
            if any(word in user_input.lower() for word in emergency_words):
                print("\n🚨 EMERGENCY NOTICE 🚨")
                print("If you are experiencing a medical emergency:")
                print("  • Call 911 immediately")
                print("  • Go to the nearest emergency room")
                print("  • Do not delay seeking emergency care")
                print("-" * 40)

            # Special commands
            if user_input.lower() == "providers":
                providers = get_providers()
                print("\n👨‍⚕️ Available Providers:")
                for p in providers["providers"]:
                    print(f"  {p['id']}: {p['name']} - {p['specialty']}")
                continue

            if user_input.lower() == "prescriptions":
                rxs = get_prescriptions()
                print("\n💊 Your Prescriptions:")
                for rx in rxs["prescriptions"]:
                    print(f"  {rx['id']}: {rx['medication']}")
                continue

            # Get response from agent
            response = await agent.chat_async(user_input)
            print(f"\n🤖 Assistant: {response}")

    except KeyboardInterrupt:
        print("\n\n👋 Take care!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
