#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Insurance Claims Assistant
==========================

An AI assistant for insurance operations including claims filing,
status tracking, coverage questions, and document management.

Features:
- Claims filing and submission
- Claim status tracking
- Coverage information and questions
- Document upload management
- Policy information

Run:
    python examples/50_insurance.py

DISCLAIMER:
    This is a demonstration system with simulated data.
    Not connected to actual insurance systems.
    For actual insurance matters, contact your insurance provider directly.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any
import random

from agentic_brain import Agent

# ============================================================================
# Demo Insurance Data
# ============================================================================

POLICY_INFO = {
    "policy_number": "POL-2024-123456",
    "type": "Homeowners Insurance",
    "status": "Active",
    "effective_date": "2024-01-01",
    "expiration_date": "2025-01-01",
    "premium": {
        "annual": 1850.00,
        "monthly": 154.17,
        "payment_method": "Auto-pay",
        "next_payment": "2024-02-15",
    },
    "insured": {
        "name": "Demo Policyholder",
        "address": "123 Insurance Lane, Coverage City, ST 12345",
        "phone": "(555) 123-4567",
        "email": "demo@insurance-example.com",
    },
    "coverages": {
        "dwelling": {"limit": 350000, "deductible": 1000},
        "personal_property": {"limit": 175000, "deductible": 1000},
        "liability": {"limit": 300000, "deductible": 0},
        "medical_payments": {"limit": 5000, "deductible": 0},
        "additional_living_expenses": {"limit": 70000, "deductible": 0},
    },
    "discounts": ["Multi-policy", "Claims-free", "Security system", "New home"],
}

AUTO_POLICY = {
    "policy_number": "AUTO-2024-789012",
    "type": "Auto Insurance",
    "status": "Active",
    "vehicles": [
        {
            "year": 2022,
            "make": "Honda",
            "model": "Accord",
            "vin": "1HGC********1234",
            "coverages": {
                "liability": "100/300/100",
                "collision": {"deductible": 500},
                "comprehensive": {"deductible": 250},
                "uninsured_motorist": "100/300",
            },
        },
    ],
    "premium": {
        "six_month": 680.00,
        "monthly": 113.33,
    },
    "drivers": ["Demo Policyholder"],
}

CLAIM_TYPES = {
    "water_damage": {
        "description": "Water damage from burst pipes, leaks, or flooding",
        "typical_process_days": 14,
        "documents_needed": [
            "Photos of damage",
            "Repair estimates",
            "Incident description",
        ],
    },
    "theft": {
        "description": "Theft of personal property or break-in",
        "typical_process_days": 21,
        "documents_needed": [
            "Police report",
            "List of stolen items",
            "Proof of ownership",
            "Photos",
        ],
    },
    "fire": {
        "description": "Fire damage to property",
        "typical_process_days": 30,
        "documents_needed": [
            "Fire department report",
            "Photos of damage",
            "Inventory of damaged items",
        ],
    },
    "wind_hail": {
        "description": "Damage from windstorms or hail",
        "typical_process_days": 14,
        "documents_needed": ["Photos of damage", "Weather reports", "Repair estimates"],
    },
    "auto_collision": {
        "description": "Vehicle collision or accident",
        "typical_process_days": 10,
        "documents_needed": [
            "Police report",
            "Photos of damage",
            "Other driver info",
            "Repair estimates",
        ],
    },
    "auto_comprehensive": {
        "description": "Non-collision auto damage (theft, vandalism, weather)",
        "typical_process_days": 14,
        "documents_needed": [
            "Police report if applicable",
            "Photos",
            "Description of incident",
        ],
    },
    "liability": {
        "description": "Someone injured on your property or by your vehicle",
        "typical_process_days": 45,
        "documents_needed": [
            "Incident report",
            "Medical records",
            "Witness statements",
        ],
    },
}

# Storage for claims
claims = [
    {
        "claim_number": "CLM-2023-001234",
        "type": "water_damage",
        "description": "Burst pipe in upstairs bathroom caused water damage to ceiling and floor",
        "date_filed": "2023-11-15",
        "date_of_loss": "2023-11-14",
        "status": "Closed - Paid",
        "amount_paid": 8750.00,
        "adjuster": "John Smith",
        "documents": ["Photos uploaded", "Plumber invoice", "Repair estimate"],
    },
]

pending_documents = []


# ============================================================================
# Insurance Tools
# ============================================================================


def get_policy_summary() -> dict[str, Any]:
    """
    Get summary of all policies.

    Returns:
        Policy information summary
    """
    return {
        "homeowners": {
            "policy_number": POLICY_INFO["policy_number"],
            "status": POLICY_INFO["status"],
            "dwelling_coverage": f"${POLICY_INFO['coverages']['dwelling']['limit']:,}",
            "deductible": f"${POLICY_INFO['coverages']['dwelling']['deductible']:,}",
            "annual_premium": f"${POLICY_INFO['premium']['annual']:,.2f}",
        },
        "auto": {
            "policy_number": AUTO_POLICY["policy_number"],
            "status": AUTO_POLICY["status"],
            "vehicles": len(AUTO_POLICY["vehicles"]),
            "six_month_premium": f"${AUTO_POLICY['premium']['six_month']:,.2f}",
        },
        "disclaimer": "This is simulated policy data for demonstration purposes.",
    }


def get_policy_details(policy_type: str) -> dict[str, Any]:
    """
    Get detailed information about a specific policy.

    Args:
        policy_type: Type of policy (homeowners, auto)

    Returns:
        Detailed policy information
    """
    policy_type = policy_type.lower()

    if "home" in policy_type:
        return {
            "policy": POLICY_INFO,
            "claim_count": len([c for c in claims if c["status"] != "Closed - Paid"]),
        }
    elif "auto" in policy_type:
        return {
            "policy": AUTO_POLICY,
        }
    else:
        return {
            "error": f"Policy type '{policy_type}' not found",
            "available_types": ["homeowners", "auto"],
        }


def check_coverage(coverage_question: str) -> dict[str, Any]:
    """
    Answer coverage questions.

    Args:
        coverage_question: Question about coverage

    Returns:
        Coverage information

    DISCLAIMER: This is general information. Check your policy for specifics.
    """
    question_lower = coverage_question.lower()

    # Check for common coverage questions
    if "flood" in question_lower:
        return {
            "question": coverage_question,
            "answer": "Standard homeowners insurance typically does NOT cover flood damage. Flood insurance is a separate policy available through the National Flood Insurance Program (NFIP) or private insurers.",
            "recommendation": "Contact us to discuss flood insurance options.",
            "disclaimer": "Coverage varies by policy. Review your specific policy or contact your agent.",
        }

    if "earthquake" in question_lower:
        return {
            "question": coverage_question,
            "answer": "Standard homeowners insurance typically does NOT cover earthquake damage. Earthquake coverage is usually a separate policy or endorsement.",
            "recommendation": "Contact us about earthquake coverage options.",
            "disclaimer": "Coverage varies by policy. Review your specific policy or contact your agent.",
        }

    if "deductible" in question_lower:
        return {
            "question": coverage_question,
            "homeowners_deductible": f"${POLICY_INFO['coverages']['dwelling']['deductible']:,}",
            "auto_collision_deductible": f"${AUTO_POLICY['vehicles'][0]['coverages']['collision']['deductible']:,}",
            "auto_comprehensive_deductible": f"${AUTO_POLICY['vehicles'][0]['coverages']['comprehensive']['deductible']:,}",
            "note": "The deductible is what you pay out-of-pocket before insurance coverage kicks in.",
            "disclaimer": "Verify deductibles in your policy documents.",
        }

    if "personal property" in question_lower or "belongings" in question_lower:
        return {
            "question": coverage_question,
            "coverage_limit": f"${POLICY_INFO['coverages']['personal_property']['limit']:,}",
            "covers": "Personal belongings inside your home (furniture, electronics, clothing, etc.)",
            "special_limits": "Jewelry, art, and collectibles may have sub-limits. Consider scheduling valuable items.",
            "disclaimer": "Coverage limits and exclusions vary. Check your policy.",
        }

    if "liability" in question_lower:
        return {
            "question": coverage_question,
            "homeowners_liability": f"${POLICY_INFO['coverages']['liability']['limit']:,}",
            "auto_liability": AUTO_POLICY["vehicles"][0]["coverages"]["liability"],
            "covers": "Protection if someone is injured on your property or in an accident you cause",
            "disclaimer": "Coverage limits and exclusions vary. Check your policy.",
        }

    return {
        "question": coverage_question,
        "answer": "For specific coverage questions, please review your policy documents or contact your agent directly.",
        "policy_documents": "Available in your online account",
        "agent_phone": "(555) INSURE-1",
        "disclaimer": "This is general information. Your specific coverage depends on your policy terms.",
    }


def file_claim(
    claim_type: str,
    date_of_loss: str,
    description: str,
    estimated_damage: float = None,
) -> dict[str, Any]:
    """
    File a new insurance claim.

    Args:
        claim_type: Type of claim (water_damage, theft, fire, etc.)
        date_of_loss: Date the incident occurred (YYYY-MM-DD)
        description: Description of what happened
        estimated_damage: Estimated damage amount

    Returns:
        Claim filing confirmation
    """
    claim_type_key = claim_type.lower().replace(" ", "_").replace("-", "_")

    if claim_type_key not in CLAIM_TYPES:
        return {
            "error": f"Claim type '{claim_type}' not recognized",
            "available_types": list(CLAIM_TYPES.keys()),
        }

    claim_info = CLAIM_TYPES[claim_type_key]
    claim_number = f"CLM-{datetime.now().year}-{random.randint(100000, 999999)}"

    new_claim = {
        "claim_number": claim_number,
        "type": claim_type_key,
        "description": description,
        "date_filed": datetime.now().strftime("%Y-%m-%d"),
        "date_of_loss": date_of_loss,
        "estimated_damage": estimated_damage,
        "status": "Submitted - Under Review",
        "adjuster": "To be assigned",
        "documents": [],
    }

    claims.append(new_claim)

    return {
        "success": True,
        "claim_number": claim_number,
        "claim": new_claim,
        "next_steps": [
            "An adjuster will be assigned within 24-48 hours",
            "You will receive a call to discuss the claim",
            "Please gather the following documents: "
            + ", ".join(claim_info["documents_needed"]),
        ],
        "typical_timeline": f"{claim_info['typical_process_days']} days for this type of claim",
        "important": "Do not dispose of damaged items until inspected by adjuster.",
        "disclaimer": "This is a simulated claim filing for demonstration.",
    }


def get_claim_status(claim_number: str = None) -> dict[str, Any]:
    """
    Get status of claims.

    Args:
        claim_number: Specific claim number, or None for all claims

    Returns:
        Claim status information
    """
    if claim_number:
        for claim in claims:
            if claim["claim_number"] == claim_number.upper():
                return {"claim": claim}
        return {"error": f"Claim {claim_number} not found"}

    # Return all claims
    open_claims = [c for c in claims if "Closed" not in c["status"]]
    closed_claims = [c for c in claims if "Closed" in c["status"]]

    return {
        "open_claims": open_claims,
        "closed_claims": closed_claims[-5:] if closed_claims else [],
        "total_claims": len(claims),
    }


def upload_document(
    claim_number: str, document_type: str, description: str
) -> dict[str, Any]:
    """
    Upload a document for a claim.

    Args:
        claim_number: Claim number
        document_type: Type of document (photo, invoice, estimate, police_report, etc.)
        description: Description of the document

    Returns:
        Upload confirmation
    """
    for claim in claims:
        if claim["claim_number"] == claim_number.upper():
            doc_id = f"DOC-{random.randint(10000, 99999)}"

            document = {
                "doc_id": doc_id,
                "claim_number": claim_number.upper(),
                "type": document_type,
                "description": description,
                "uploaded_at": datetime.now().isoformat(),
                "status": "Received",
            }

            claim["documents"].append(f"{document_type}: {description}")
            pending_documents.append(document)

            return {
                "success": True,
                "document_id": doc_id,
                "message": f"Document uploaded successfully to claim {claim_number}",
                "claim_documents": claim["documents"],
            }

    return {"error": f"Claim {claim_number} not found"}


def get_required_documents(claim_number: str) -> dict[str, Any]:
    """
    Get list of required documents for a claim.

    Args:
        claim_number: Claim number

    Returns:
        Required documents checklist
    """
    for claim in claims:
        if claim["claim_number"] == claim_number.upper():
            claim_type = claim["type"]
            if claim_type in CLAIM_TYPES:
                required = CLAIM_TYPES[claim_type]["documents_needed"]
                uploaded = claim["documents"]

                return {
                    "claim_number": claim_number,
                    "claim_type": claim_type.replace("_", " ").title(),
                    "required_documents": required,
                    "uploaded_documents": uploaded,
                    "missing": [
                        d
                        for d in required
                        if not any(d.lower() in u.lower() for u in uploaded)
                    ],
                }

    return {"error": f"Claim {claim_number} not found"}


def estimate_payout(claim_number: str) -> dict[str, Any]:
    """
    Get estimated payout information for a claim.

    Args:
        claim_number: Claim number

    Returns:
        Payout estimate information

    DISCLAIMER: This is an estimate only. Final payout determined by adjuster.
    """
    for claim in claims:
        if claim["claim_number"] == claim_number.upper():
            estimated = claim.get("estimated_damage", 0)

            if not estimated:
                return {
                    "claim_number": claim_number,
                    "message": "No damage estimate provided. Adjuster will assess damage.",
                    "next_step": "Wait for adjuster inspection",
                }

            deductible = POLICY_INFO["coverages"]["dwelling"]["deductible"]
            estimated_payout = max(0, estimated - deductible)

            return {
                "claim_number": claim_number,
                "estimated_damage": f"${estimated:,.2f}",
                "deductible": f"${deductible:,.2f}",
                "estimated_payout": f"${estimated_payout:,.2f}",
                "disclaimer": "⚠️ This is an ESTIMATE only. Final payout will be determined by the claims adjuster after inspection. Actual payment may be higher or lower.",
                "factors": [
                    "Final damage assessment",
                    "Coverage limits",
                    "Depreciation (if applicable)",
                    "Policy exclusions",
                ],
            }

    return {"error": f"Claim {claim_number} not found"}


def get_claim_types() -> dict[str, Any]:
    """
    Get information about different claim types.

    Returns:
        Available claim types and what they cover
    """
    types_info = []
    for key, info in CLAIM_TYPES.items():
        types_info.append(
            {
                "type": key.replace("_", " ").title(),
                "description": info["description"],
                "typical_timeline": f"{info['typical_process_days']} days",
            }
        )

    return {
        "claim_types": types_info,
        "emergency_claims": "For emergencies, call our 24/7 claims line: 1-800-CLAIMS-1",
    }


def get_payment_info() -> dict[str, Any]:
    """
    Get payment and billing information.

    Returns:
        Payment details
    """
    return {
        "homeowners_policy": {
            "annual_premium": POLICY_INFO["premium"]["annual"],
            "monthly_payment": POLICY_INFO["premium"]["monthly"],
            "payment_method": POLICY_INFO["premium"]["payment_method"],
            "next_payment_date": POLICY_INFO["premium"]["next_payment"],
        },
        "auto_policy": {
            "six_month_premium": AUTO_POLICY["premium"]["six_month"],
            "monthly_payment": AUTO_POLICY["premium"]["monthly"],
        },
        "payment_options": [
            "Auto-pay (current method)",
            "Online payment",
            "Phone payment",
            "Mail check",
        ],
    }


def request_id_card(policy_type: str = "auto") -> dict[str, Any]:
    """
    Request insurance ID cards.

    Args:
        policy_type: Type of policy (auto, homeowners)

    Returns:
        ID card request confirmation
    """
    return {
        "success": True,
        "policy_type": policy_type,
        "delivery_methods": {
            "email": "Sent immediately to your email on file",
            "mail": "Physical card mailed within 5-7 business days",
            "app": "Available instantly in mobile app",
        },
        "message": "Your ID card has been sent to your email.",
        "note": "You can also access your ID card anytime in your online account or mobile app.",
    }


def contact_adjuster(claim_number: str, message: str) -> dict[str, Any]:
    """
    Send a message to the claims adjuster.

    Args:
        claim_number: Claim number
        message: Message to send

    Returns:
        Message confirmation
    """
    for claim in claims:
        if claim["claim_number"] == claim_number.upper():
            if claim["adjuster"] == "To be assigned":
                return {
                    "message": "An adjuster has not been assigned yet. One will contact you within 24-48 hours.",
                    "urgent": "For urgent matters, call our claims line: 1-800-CLAIMS-1",
                }

            return {
                "success": True,
                "claim_number": claim_number,
                "adjuster": claim["adjuster"],
                "message_sent": message,
                "response_time": "Your adjuster will respond within 1-2 business days",
                "direct_line": "You can also reach your adjuster directly at the number in your claim packet",
            }

    return {"error": f"Claim {claim_number} not found"}


# ============================================================================
# Agent Configuration
# ============================================================================

INSURANCE_TOOLS = [
    {
        "name": "get_policy_summary",
        "description": "Get summary of all insurance policies",
        "function": get_policy_summary,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_policy_details",
        "description": "Get detailed information about a specific policy",
        "function": get_policy_details,
        "parameters": {
            "type": "object",
            "properties": {
                "policy_type": {
                    "type": "string",
                    "description": "Type of policy (homeowners, auto)",
                },
            },
            "required": ["policy_type"],
        },
    },
    {
        "name": "check_coverage",
        "description": "Answer questions about coverage",
        "function": check_coverage,
        "parameters": {
            "type": "object",
            "properties": {
                "coverage_question": {
                    "type": "string",
                    "description": "Question about coverage",
                },
            },
            "required": ["coverage_question"],
        },
    },
    {
        "name": "file_claim",
        "description": "File a new insurance claim",
        "function": file_claim,
        "parameters": {
            "type": "object",
            "properties": {
                "claim_type": {"type": "string", "description": "Type of claim"},
                "date_of_loss": {
                    "type": "string",
                    "description": "Date of incident (YYYY-MM-DD)",
                },
                "description": {
                    "type": "string",
                    "description": "Description of what happened",
                },
                "estimated_damage": {
                    "type": "number",
                    "description": "Estimated damage amount",
                },
            },
            "required": ["claim_type", "date_of_loss", "description"],
        },
    },
    {
        "name": "get_claim_status",
        "description": "Get status of claims",
        "function": get_claim_status,
        "parameters": {
            "type": "object",
            "properties": {
                "claim_number": {
                    "type": "string",
                    "description": "Specific claim number",
                },
            },
        },
    },
    {
        "name": "upload_document",
        "description": "Upload a document for a claim",
        "function": upload_document,
        "parameters": {
            "type": "object",
            "properties": {
                "claim_number": {"type": "string", "description": "Claim number"},
                "document_type": {"type": "string", "description": "Type of document"},
                "description": {
                    "type": "string",
                    "description": "Document description",
                },
            },
            "required": ["claim_number", "document_type", "description"],
        },
    },
    {
        "name": "get_required_documents",
        "description": "Get list of required documents for a claim",
        "function": get_required_documents,
        "parameters": {
            "type": "object",
            "properties": {
                "claim_number": {"type": "string", "description": "Claim number"},
            },
            "required": ["claim_number"],
        },
    },
    {
        "name": "estimate_payout",
        "description": "Get estimated payout information for a claim",
        "function": estimate_payout,
        "parameters": {
            "type": "object",
            "properties": {
                "claim_number": {"type": "string", "description": "Claim number"},
            },
            "required": ["claim_number"],
        },
    },
    {
        "name": "get_claim_types",
        "description": "Get information about different claim types",
        "function": get_claim_types,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_payment_info",
        "description": "Get payment and billing information",
        "function": get_payment_info,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "request_id_card",
        "description": "Request insurance ID cards",
        "function": request_id_card,
        "parameters": {
            "type": "object",
            "properties": {
                "policy_type": {
                    "type": "string",
                    "description": "Policy type (auto, homeowners)",
                },
            },
        },
    },
    {
        "name": "contact_adjuster",
        "description": "Send a message to the claims adjuster",
        "function": contact_adjuster,
        "parameters": {
            "type": "object",
            "properties": {
                "claim_number": {"type": "string", "description": "Claim number"},
                "message": {"type": "string", "description": "Message to send"},
            },
            "required": ["claim_number", "message"],
        },
    },
]

SYSTEM_PROMPT = """You are a helpful insurance claims assistant.

Your capabilities:
- View policy information and coverage details
- Answer coverage questions
- File new claims
- Track claim status
- Help with document uploads
- Explain the claims process

Guidelines:
- Be empathetic - filing claims is stressful
- Explain processes clearly
- Always mention this is a demonstration system
- For actual claims, recommend contacting the insurance company
- Never promise specific payouts - final amounts are determined by adjusters
- Prioritize emergency situations (fire, major damage, injuries)

IMPORTANT DISCLAIMERS to include:
- "This is simulated data for demonstration purposes"
- "Actual coverage depends on your specific policy terms"
- "Final claim amounts are determined by adjusters"
- "Contact your insurance company for actual policy questions"

Available policies: Homeowners (POL-2024-123456), Auto (AUTO-2024-789012)
Claim types: water_damage, theft, fire, wind_hail, auto_collision, auto_comprehensive, liability

For emergencies: Direct customers to 24/7 claims line: 1-800-CLAIMS-1"""


# ============================================================================
# Main Application
# ============================================================================


async def main():
    """Run the Insurance Claims Assistant."""
    print("=" * 60)
    print("🛡️ Insurance Claims Assistant")
    print("=" * 60)
    print("\n⚠️  DEMO MODE - Simulated data only")
    print("    For actual insurance matters, contact your provider\n")
    print("I can help you with:")
    print("  • View your policy information")
    print("  • File and track claims")
    print("  • Answer coverage questions")
    print("  • Upload documents for claims")
    print("\n💡 Example questions:")
    print('  "Show me my policies"')
    print('  "Am I covered for flood damage?"')
    print('  "I need to file a claim"')
    print('  "What\'s the status of my claim?"')
    print("\n🚨 For emergencies: 1-800-CLAIMS-1 (24/7)")
    print("\nType 'quit' to exit")
    print("-" * 60)

    # Create agent
    agent = Agent(
        name="insurance_assistant",
        system_prompt=SYSTEM_PROMPT,
        tools=INSURANCE_TOOLS,
    )

    try:
        while True:
            user_input = input("\n🛡️ You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                print("\n👋 Thank you for contacting us!")
                print("Remember: For emergencies, call 1-800-CLAIMS-1")
                break

            # Special commands
            if user_input.lower() == "policies":
                summary = get_policy_summary()
                print("\n📋 Your Policies:")
                print(f"  Homeowners: {summary['homeowners']['policy_number']}")
                print(f"    Coverage: {summary['homeowners']['dwelling_coverage']}")
                print(f"  Auto: {summary['auto']['policy_number']}")
                print(f"    Vehicles: {summary['auto']['vehicles']}")
                continue

            if user_input.lower() == "claims":
                status = get_claim_status()
                print(f"\n📋 Claims Summary:")
                print(f"  Open claims: {len(status['open_claims'])}")
                print(f"  Total claims: {status['total_claims']}")
                continue

            if user_input.lower() == "types":
                types = get_claim_types()
                print("\n📋 Claim Types:")
                for t in types["claim_types"]:
                    print(f"  • {t['type']}: {t['typical_timeline']}")
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
