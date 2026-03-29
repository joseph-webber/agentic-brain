# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Legal Disclaimers Module for Agentic Brain

Standard Australian-compliant disclaimers for various use cases.
Based on LegalVision Australia guidelines and Australian Consumer Law.

Usage:
    from agentic_brain.legal import MEDICAL_DISCLAIMER, FINANCIAL_DISCLAIMER
    from agentic_brain.legal import get_disclaimer, DisclaimerType

    # Get specific disclaimer
    disclaimer = get_disclaimer(DisclaimerType.MEDICAL)

    # Use in chatbot
    response = f"{disclaimer}\\n\\n{actual_response}"

IMPORTANT:
    These disclaimers provide a baseline. Consult a qualified Australian
    legal practitioner for advice specific to your circumstances.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

__all__ = [
    # Enums
    "DisclaimerType",
    # Constants
    "MEDICAL_DISCLAIMER",
    "FINANCIAL_DISCLAIMER",
    "LEGAL_DISCLAIMER",
    "NDIS_DISCLAIMER",
    "DEFENCE_DISCLAIMER",
    "AI_DISCLAIMER",
    "GENERAL_DISCLAIMER",
    "ACL_CONSUMER_RIGHTS",
    "PRIVACY_COLLECTION_NOTICE",
    # Functions
    "get_disclaimer",
    "get_acl_notice",
    "format_disclaimer",
    "get_privacy_notice",
]


class DisclaimerType(Enum):
    """Types of legal disclaimers available."""

    MEDICAL = "medical"
    HEALTHCARE = "medical"  # Alias
    FINANCIAL = "financial"
    INVESTMENT = "financial"  # Alias
    LEGAL = "legal"
    NDIS = "ndis"
    DISABILITY = "ndis"  # Alias
    DEFENCE = "defence"
    GOVERNMENT = "defence"  # Alias
    AI = "ai"
    ML = "ai"  # Alias
    GENERAL = "general"


# ══════════════════════════════════════════════════════════════════════════════
# MEDICAL / HEALTHCARE DISCLAIMER
# ══════════════════════════════════════════════════════════════════════════════

MEDICAL_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                     ⚠️  IMPORTANT MEDICAL DISCLAIMER  ⚠️                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This software is NOT a substitute for professional medical advice,         ║
║  diagnosis, or treatment.                                                   ║
║                                                                              ║
║  • This is an AI triage SUPPORT tool only                                   ║
║  • All outputs must be reviewed by qualified healthcare professionals       ║
║  • Never delay seeking medical advice because of this software              ║
║  • In emergency, call 000 (Triple Zero) immediately                         ║
║  • This software does not create a doctor-patient relationship              ║
║                                                                              ║
║  The developers, contributors, and deployers of this software accept        ║
║  no liability for any decisions made based on its outputs.                  ║
║                                                                              ║
║  REGULATORY STATUS:                                                          ║
║  This software is not registered as a medical device with the TGA           ║
║  (Therapeutic Goods Administration). It is intended as a decision           ║
║  support tool only, not for primary diagnosis.                              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""".strip()


# ══════════════════════════════════════════════════════════════════════════════
# FINANCIAL SERVICES DISCLAIMER
# ══════════════════════════════════════════════════════════════════════════════

FINANCIAL_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                   ⚠️  IMPORTANT FINANCIAL DISCLAIMER  ⚠️                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This software provides GENERAL INFORMATION ONLY.                            ║
║  It is NOT personal financial advice.                                        ║
║                                                                              ║
║  • We do not hold an Australian Financial Services Licence (AFSL)           ║
║  • We are not authorised to provide personal financial advice               ║
║  • This information does not consider your personal circumstances           ║
║  • You should seek advice from a licensed financial adviser                 ║
║  • Past performance is not indicative of future results                     ║
║                                                                              ║
║  CREDIT PRODUCTS:                                                            ║
║  If credit products are mentioned, we are not licensed credit providers     ║
║  under the National Consumer Credit Protection Act 2009.                    ║
║                                                                              ║
║  CRYPTOCURRENCY:                                                             ║
║  Cryptocurrency is highly volatile and speculative. You may lose all        ║
║  invested capital. This is not investment advice.                           ║
║                                                                              ║
║  The developers accept no liability for financial decisions made based      ║
║  on information provided by this software.                                  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""".strip()


# ══════════════════════════════════════════════════════════════════════════════
# LEGAL INFORMATION DISCLAIMER
# ══════════════════════════════════════════════════════════════════════════════

LEGAL_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                     ⚠️  IMPORTANT LEGAL DISCLAIMER  ⚠️                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This software provides GENERAL LEGAL INFORMATION ONLY.                      ║
║  It is NOT legal advice and should not be relied upon as such.              ║
║                                                                              ║
║  • We are not a law firm or legal practice                                  ║
║  • Information may not reflect current law                                  ║
║  • Laws vary by jurisdiction - verify local requirements                    ║
║  • This information does not create a lawyer-client relationship            ║
║  • For legal advice, consult a qualified Australian legal practitioner      ║
║                                                                              ║
║  STATUTE OF LIMITATIONS:                                                     ║
║  Legal time limits apply to many matters. Delays in seeking advice may      ║
║  affect your legal rights.                                                  ║
║                                                                              ║
║  The developers accept no liability for any actions taken based on          ║
║  legal information provided by this software.                               ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""".strip()


# ══════════════════════════════════════════════════════════════════════════════
# NDIS PROVIDER DISCLAIMER
# ══════════════════════════════════════════════════════════════════════════════

NDIS_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                     ⚠️  IMPORTANT NDIS DISCLAIMER  ⚠️                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This software is a MANAGEMENT SUPPORT TOOL only.                            ║
║                                                                              ║
║  • This software does not replace qualified NDIS plan management            ║
║  • All service agreements require proper NDIS-compliant documentation       ║
║  • Pricing information may not reflect current NDIS Price Guide             ║
║  • Always verify information with the official NDIS Price Guide             ║
║  • Service bookings should be confirmed through official myplace portal     ║
║                                                                              ║
║  QUALITY & SAFEGUARDS:                                                       ║
║  This software does not replace NDIS Quality and Safeguards Commission      ║
║  compliance obligations. Providers must maintain separate compliance        ║
║  with all NDIS Practice Standards.                                          ║
║                                                                              ║
║  REPORTABLE INCIDENTS:                                                       ║
║  Providers must report incidents to the NDIS Commission directly.           ║
║  This software does not constitute incident reporting.                      ║
║                                                                              ║
║  PRIVACY:                                                                    ║
║  NDIS participant information is subject to the Privacy Act 1988 and        ║
║  NDIS-specific privacy requirements. Ensure appropriate data handling.      ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""".strip()


# ══════════════════════════════════════════════════════════════════════════════
# DEFENCE / GOVERNMENT DISCLAIMER
# ══════════════════════════════════════════════════════════════════════════════

DEFENCE_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                   ⚠️  DEFENCE SECURITY DISCLAIMER  ⚠️                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This software is provided for DEMONSTRATION PURPOSES ONLY.                  ║
║                                                                              ║
║  SECURITY CLASSIFICATION:                                                    ║
║  • This software has NOT been security assessed by AGSVA or ASD             ║
║  • This software is NOT approved for classified information                 ║
║  • Do NOT process OFFICIAL, PROTECTED, or CLASSIFIED data                   ║
║                                                                              ║
║  COMPLIANCE REQUIREMENTS:                                                    ║
║  • Defence applications require ISM compliance assessment                    ║
║  • ITAR/EAR restrictions may apply to certain use cases                     ║
║  • AUKUS information handling requires specific approvals                   ║
║  • Essential Eight security controls should be implemented                  ║
║                                                                              ║
║  EXPORT CONTROLS:                                                            ║
║  This software may be subject to export control regulations. Users are      ║
║  responsible for compliance with Defence Trade Controls Act 2012.           ║
║                                                                              ║
║  For operational deployment, obtain appropriate security accreditation      ║
║  through your organisation's security authority.                            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""".strip()


# ══════════════════════════════════════════════════════════════════════════════
# AI / MACHINE LEARNING DISCLAIMER
# ══════════════════════════════════════════════════════════════════════════════

AI_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                  ⚠️  ARTIFICIAL INTELLIGENCE DISCLAIMER  ⚠️                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This software uses artificial intelligence and machine learning.            ║
║                                                                              ║
║  IMPORTANT LIMITATIONS:                                                      ║
║  • AI outputs may contain errors, hallucinations, or inaccuracies           ║
║  • AI does not understand context the way humans do                         ║
║  • Outputs should be verified by qualified humans before reliance           ║
║  • AI may produce different outputs for similar inputs                      ║
║  • AI training data has a knowledge cutoff date                             ║
║                                                                              ║
║  BIAS AND FAIRNESS:                                                          ║
║  • AI systems may reflect biases present in training data                   ║
║  • Critical decisions should not rely solely on AI outputs                  ║
║  • Human oversight is recommended for consequential decisions               ║
║                                                                              ║
║  DATA USAGE:                                                                 ║
║  • Inputs may be processed by third-party AI services                       ║
║  • Do not input sensitive personal information unless documented            ║
║  • Review data handling policies of underlying AI providers                 ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""".strip()


# ══════════════════════════════════════════════════════════════════════════════
# GENERAL DISCLAIMER
# ══════════════════════════════════════════════════════════════════════════════

GENERAL_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                       ⚠️  GENERAL DISCLAIMER  ⚠️                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This software is provided "AS IS" without warranty of any kind.            ║
║                                                                              ║
║  TO THE MAXIMUM EXTENT PERMITTED BY LAW:                                     ║
║  • We make no representations or warranties about accuracy                  ║
║  • We disclaim all implied warranties of merchantability                    ║
║  • We disclaim all implied warranties of fitness for purpose                ║
║  • We are not liable for any consequential damages                          ║
║                                                                              ║
║  AUSTRALIAN CONSUMER LAW:                                                    ║
║  Our goods and services come with guarantees that cannot be excluded        ║
║  under the Australian Consumer Law. Nothing in this disclaimer affects      ║
║  any rights you may have under that law.                                    ║
║                                                                              ║
║  Use this software at your own risk. Always verify outputs before           ║
║  relying on them for important decisions.                                   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""".strip()


# ══════════════════════════════════════════════════════════════════════════════
# AUSTRALIAN CONSUMER LAW - MANDATORY NOTICE
# ══════════════════════════════════════════════════════════════════════════════

ACL_CONSUMER_RIGHTS = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                     AUSTRALIAN CONSUMER LAW RIGHTS                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Our goods and services come with guarantees that cannot be excluded        ║
║  under the Australian Consumer Law.                                         ║
║                                                                              ║
║  For major failures with the service, you are entitled:                     ║
║  • to cancel your service contract with us; and                             ║
║  • to a refund for the unused portion, or to compensation for its           ║
║    reduced value.                                                           ║
║                                                                              ║
║  You are also entitled to choose a refund or replacement for major          ║
║  failures with goods.                                                       ║
║                                                                              ║
║  If a failure with the goods or a service does not amount to a major        ║
║  failure, you are entitled to have the failure rectified in a reasonable    ║
║  time. If this is not done you are entitled to a refund for the goods       ║
║  and to cancel the contract for the service and obtain a refund of any      ║
║  unused portion.                                                            ║
║                                                                              ║
║  You are also entitled to be compensated for any other reasonably           ║
║  foreseeable loss or damage from a failure in the goods or service.         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""".strip()


# ══════════════════════════════════════════════════════════════════════════════
# PRIVACY COLLECTION NOTICE
# ══════════════════════════════════════════════════════════════════════════════

PRIVACY_COLLECTION_NOTICE = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                      PRIVACY COLLECTION NOTICE                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  We collect personal information to provide this service.                   ║
║                                                                              ║
║  WHAT WE COLLECT:                                                            ║
║  • Information you provide (name, email, messages)                          ║
║  • Technical information (IP address, device type)                          ║
║  • Usage information (features used, interactions)                          ║
║                                                                              ║
║  HOW WE USE IT:                                                              ║
║  • To provide and improve the service                                       ║
║  • To communicate with you                                                  ║
║  • To comply with legal obligations                                         ║
║                                                                              ║
║  YOUR RIGHTS:                                                                ║
║  • Access your information                                                  ║
║  • Request correction of errors                                             ║
║  • Complain to the OAIC if you're unhappy                                   ║
║                                                                              ║
║  See our full Privacy Policy for details.                                   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""".strip()


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

_DISCLAIMER_MAP = {
    DisclaimerType.MEDICAL: MEDICAL_DISCLAIMER,
    DisclaimerType.FINANCIAL: FINANCIAL_DISCLAIMER,
    DisclaimerType.LEGAL: LEGAL_DISCLAIMER,
    DisclaimerType.NDIS: NDIS_DISCLAIMER,
    DisclaimerType.DEFENCE: DEFENCE_DISCLAIMER,
    DisclaimerType.AI: AI_DISCLAIMER,
    DisclaimerType.GENERAL: GENERAL_DISCLAIMER,
}


def get_disclaimer(disclaimer_type: DisclaimerType, compact: bool = False) -> str:
    """
    Get a specific disclaimer by type.

    Args:
        disclaimer_type: Type of disclaimer to retrieve
        compact: If True, return a single-line version

    Returns:
        The disclaimer text

    Example:
        >>> disclaimer = get_disclaimer(DisclaimerType.MEDICAL)
        >>> print(disclaimer)
    """
    disclaimer = _DISCLAIMER_MAP.get(disclaimer_type, GENERAL_DISCLAIMER)

    if compact:
        # Extract just the key warning
        lines = disclaimer.split("\n")
        # Find the first content line after the header
        for line in lines:
            if "NOT" in line or "ONLY" in line:
                return line.strip("║ \n")
        return "See full disclaimer for important limitations."

    return disclaimer


def get_acl_notice() -> str:
    """
    Get the mandatory Australian Consumer Law notice.

    This notice CANNOT be excluded and must be provided to consumers.

    Returns:
        ACL consumer rights notice
    """
    return ACL_CONSUMER_RIGHTS


def get_privacy_notice(
    company_name: Optional[str] = None, contact_email: Optional[str] = None
) -> str:
    """
    Get privacy collection notice with optional customisation.

    Args:
        company_name: Name to include in notice
        contact_email: Contact email for privacy inquiries

    Returns:
        Privacy collection notice
    """
    notice = PRIVACY_COLLECTION_NOTICE

    if company_name:
        notice = notice.replace(
            "We collect personal information",
            f"{company_name} collects personal information",
        )

    if contact_email:
        notice = notice.replace(
            "See our full Privacy Policy for details.",
            f"See our full Privacy Policy for details.\nContact: {contact_email}",
        )

    return notice


def format_disclaimer(
    disclaimer_type: DisclaimerType,
    format: str = "text",
    include_timestamp: bool = False,
) -> str:
    """
    Format a disclaimer for different output formats.

    Args:
        disclaimer_type: Type of disclaimer
        format: Output format - 'text', 'html', 'markdown'
        include_timestamp: Add timestamp to disclaimer

    Returns:
        Formatted disclaimer
    """
    disclaimer = get_disclaimer(disclaimer_type)

    if include_timestamp:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S AEST")
        disclaimer = f"{disclaimer}\n\nDisclaimer shown: {timestamp}"

    if format == "html":
        # Convert box drawing to HTML
        html = disclaimer.replace("╔", "<div class='disclaimer'>")
        html = html.replace("╚", "</div>")
        html = html.replace("╠", "<hr>")
        html = html.replace("║", "")
        html = html.replace("═", "")
        html = html.replace("╗", "")
        html = html.replace("╝", "")
        html = html.replace("\n", "<br>")
        return f"<div class='disclaimer-box'>{html}</div>"

    elif format == "markdown":
        # Convert to markdown blockquote
        lines = disclaimer.split("\n")
        md_lines = []
        for line in lines:
            # Remove box characters
            clean = line.replace("╔", "").replace("╗", "").replace("╚", "")
            clean = clean.replace("╝", "").replace("║", "").replace("═", "")
            clean = clean.replace("╠", "---")
            if clean.strip():
                md_lines.append(f"> {clean.strip()}")
        return "\n".join(md_lines)

    return disclaimer


def combine_disclaimers(*types: DisclaimerType) -> str:
    """
    Combine multiple disclaimers into one notice.

    Args:
        *types: Disclaimer types to combine

    Returns:
        Combined disclaimer text

    Example:
        >>> combined = combine_disclaimers(
        ...     DisclaimerType.AI,
        ...     DisclaimerType.MEDICAL
        ... )
    """
    disclaimers = [get_disclaimer(t) for t in types]
    return "\n\n".join(disclaimers)


# ══════════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLE
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 80)
    print("AGENTIC BRAIN - LEGAL DISCLAIMERS MODULE")
    print("=" * 80)

    print("\n1. Medical Disclaimer:")
    print(get_disclaimer(DisclaimerType.MEDICAL))

    print("\n2. Compact Financial Disclaimer:")
    print(get_disclaimer(DisclaimerType.FINANCIAL, compact=True))

    print("\n3. Australian Consumer Law Notice:")
    print(get_acl_notice())

    print("\n4. Available Disclaimer Types:")
    for dtype in DisclaimerType:
        print(f"   - {dtype.value}")
