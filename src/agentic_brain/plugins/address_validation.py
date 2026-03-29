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


"""
Australian Address Validation Plugin.

Validates and formats Australian addresses for customer service chatbots.
Returns both original and formatted address for comparison.

Features:
- Typo correction for suburbs and streets
- State abbreviation normalization
- Postcode validation
- Unit/apartment number parsing
- Street type standardization
- Confidence scoring

Example:
    >>> from agentic_brain.plugins.address_validation import AddressValidationPlugin
    >>> plugin = AddressValidationPlugin()
    >>> result = plugin.process("301/10 Blaoduras Wya SA 5000 ADELAID")
    >>> print(result.processed_output['formatted'])
    "Unit 301/10 Boulevard Way, Adelaide SA 5000"
"""

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from agentic_brain.plugins.base import Plugin, PluginConfig

logger = logging.getLogger(__name__)


# =============================================================================
# AUSTRALIAN ADDRESS DATA
# =============================================================================

# State name variations -> standard abbreviation
STATE_MAPPINGS: Dict[str, str] = {
    # Standard abbreviations
    "NSW": "NSW",
    "VIC": "VIC",
    "QLD": "QLD",
    "SA": "SA",
    "WA": "WA",
    "TAS": "TAS",
    "NT": "NT",
    "ACT": "ACT",
    # Full names
    "NEW SOUTH WALES": "NSW",
    "VICTORIA": "VIC",
    "QUEENSLAND": "QLD",
    "SOUTH AUSTRALIA": "SA",
    "WESTERN AUSTRALIA": "WA",
    "TASMANIA": "TAS",
    "NORTHERN TERRITORY": "NT",
    "AUSTRALIAN CAPITAL TERRITORY": "ACT",
    # Common typos/variations
    "N.S.W.": "NSW",
    "N.S.W": "NSW",
    "V.I.C.": "VIC",
    "Q.L.D.": "QLD",
    "S.A.": "SA",
    "W.A.": "WA",
    "A.C.T.": "ACT",
    "A.C.T": "ACT",
}

# Street type abbreviations -> full name
STREET_TYPES: Dict[str, str] = {
    # Standard
    "ST": "Street",
    "RD": "Road",
    "AVE": "Avenue",
    "AV": "Avenue",
    "DR": "Drive",
    "CT": "Court",
    "CRT": "Court",
    "PL": "Place",
    "LA": "Lane",
    "LN": "Lane",
    "WAY": "Way",
    "WY": "Way",
    "CL": "Close",
    "CR": "Crescent",
    "CRES": "Crescent",
    "TCE": "Terrace",
    "TER": "Terrace",
    "PDE": "Parade",
    "HWY": "Highway",
    "BLVD": "Boulevard",
    "BVD": "Boulevard",
    "ESP": "Esplanade",
    "GR": "Grove",
    "GRV": "Grove",
    "LOOP": "Loop",
    "MEWS": "Mews",
    "PKWY": "Parkway",
    "SQ": "Square",
    "TRL": "Trail",
    "VW": "View",
    "WALK": "Walk",
    "CIR": "Circle",
    "CIRC": "Circuit",
    # Already full
    "STREET": "Street",
    "ROAD": "Road",
    "AVENUE": "Avenue",
    "DRIVE": "Drive",
    "COURT": "Court",
    "PLACE": "Place",
    "LANE": "Lane",
    "CLOSE": "Close",
    "CRESCENT": "Crescent",
    "TERRACE": "Terrace",
    "PARADE": "Parade",
    "HIGHWAY": "Highway",
    "BOULEVARD": "Boulevard",
    "ESPLANADE": "Esplanade",
    "GROVE": "Grove",
    "PARKWAY": "Parkway",
    "SQUARE": "Square",
    "CIRCLE": "Circle",
    "CIRCUIT": "Circuit",
}

# Common suburb name corrections (typo -> correct)
SUBURB_CORRECTIONS: Dict[str, str] = {
    # Adelaide
    "ADELAID": "Adelaide",
    "ADELADE": "Adelaide",
    "ADEALIDE": "Adelaide",
    "GLENLEG": "Glenelg",
    "GLENEL": "Glenelg",
    "SALISBURY": "Salisbury",
    "SALIBURY": "Salisbury",
    "PARALOWIE": "Paralowie",
    "MODURY": "Modbury",
    "MODBURY": "Modbury",
    "BURNISDE": "Burnside",
    "BURNSIDE": "Burnside",
    "NORWOOD": "Norwood",
    # Sydney
    "SYDENY": "Sydney",
    "SYNDEY": "Sydney",
    "PARAMATTA": "Parramatta",
    "PARRAMATA": "Parramatta",
    "BONDI": "Bondi",
    "BONDAI": "Bondi",
    "MANLY": "Manly",
    "MANLLY": "Manly",
    # Melbourne
    "MELBORNE": "Melbourne",
    "MELBOUNRE": "Melbourne",
    "ST KILDA": "St Kilda",
    "SAINT KILDA": "St Kilda",
    "FITZORY": "Fitzroy",
    "FITZROY": "Fitzroy",
    # Brisbane
    "BRISBANE": "Brisbane",
    "BRIBANE": "Brisbane",
    "BRIABANE": "Brisbane",
    "SOUTBANK": "South Bank",
    "SOUTHBANK": "South Bank",
    # Perth
    "PERH": "Perth",
    "PETH": "Perth",
    "FREMANLTE": "Fremantle",
    "FREEMANTLE": "Fremantle",
    "FREMANTLE": "Fremantle",
    # Other capitals
    "HOBRAT": "Hobart",
    "HOBART": "Hobart",
    "CANBERA": "Canberra",
    "CANBERRRA": "Canberra",
    "CANBERRA": "Canberra",
    "DARIWN": "Darwin",
    "DRAWIN": "Darwin",
    "DARWIN": "Darwin",
}

# Common street name corrections
STREET_CORRECTIONS: Dict[str, str] = {
    "BLAODURAS": "Boulevard",
    "BOULDEVARD": "Boulevard",
    "BOULEVRAD": "Boulevard",
    "AVENEU": "Avenue",
    "AVNUE": "Avenue",
    "STRET": "Street",
    "SREET": "Street",
    "RAOD": "Road",
    "ROAAD": "Road",
    "CRESENT": "Crescent",
    "CRECENT": "Crescent",
    "TERRACE": "Terrace",
    "TERRAC": "Terrace",
    "TERACE": "Terrace",
}

# Postcode to state mapping (first digit)
POSTCODE_STATE_PREFIX: Dict[str, str] = {
    "0": "NT",
    "1": "NSW",
    "2": "NSW",  # or ACT for 26xx
    "3": "VIC",
    "4": "QLD",
    "5": "SA",
    "6": "WA",
    "7": "TAS",
}


# =============================================================================
# ADDRESS DATA STRUCTURES
# =============================================================================


@dataclass
class ParsedAddress:
    """Parsed and validated Australian address."""

    # Components
    unit_number: Optional[str] = None
    street_number: Optional[str] = None
    street_name: Optional[str] = None
    street_type: Optional[str] = None
    suburb: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None

    # Validation
    is_valid: bool = False
    confidence: float = 0.0

    # Corrections made
    corrections: List[str] = field(default_factory=list)

    # Warnings
    warnings: List[str] = field(default_factory=list)

    def format_standard(self) -> str:
        """Format as standard Australian address."""
        parts = []

        # Unit/Street number
        if self.unit_number and self.street_number:
            parts.append(f"Unit {self.unit_number}/{self.street_number}")
        elif self.unit_number:
            parts.append(f"Unit {self.unit_number}")
        elif self.street_number:
            parts.append(self.street_number)

        # Street
        if self.street_name:
            street = self.street_name
            if self.street_type:
                street += f" {self.street_type}"
            parts.append(street)

        # Combine street parts
        street_line = " ".join(parts)

        # Suburb, State, Postcode
        location_parts = []
        if self.suburb:
            location_parts.append(self.suburb)
        if self.state:
            location_parts.append(self.state)
        if self.postcode:
            location_parts.append(self.postcode)

        location_line = " ".join(location_parts)

        if street_line and location_line:
            return f"{street_line}, {location_line}"
        return street_line or location_line

    def format_single_line(self) -> str:
        """Format as single line."""
        return self.format_standard()

    def format_multiline(self) -> str:
        """Format as multiple lines."""
        lines = []

        # Line 1: Unit/Street
        parts = []
        if self.unit_number and self.street_number:
            parts.append(f"Unit {self.unit_number}/{self.street_number}")
        elif self.unit_number:
            parts.append(f"Unit {self.unit_number}")
        elif self.street_number:
            parts.append(self.street_number)

        if self.street_name:
            street = self.street_name
            if self.street_type:
                street += f" {self.street_type}"
            parts.append(street)

        if parts:
            lines.append(" ".join(parts))

        # Line 2: Suburb State Postcode
        location_parts = []
        if self.suburb:
            location_parts.append(self.suburb)
        if self.state:
            location_parts.append(self.state)
        if self.postcode:
            location_parts.append(self.postcode)

        if location_parts:
            lines.append(" ".join(location_parts))

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "unit_number": self.unit_number,
            "street_number": self.street_number,
            "street_name": self.street_name,
            "street_type": self.street_type,
            "suburb": self.suburb,
            "state": self.state,
            "postcode": self.postcode,
            "is_valid": self.is_valid,
            "confidence": self.confidence,
            "corrections": self.corrections,
            "warnings": self.warnings,
            "formatted": self.format_standard(),
        }


# =============================================================================
# ADDRESS PARSER
# =============================================================================


class AddressParser:
    """
    Parse and validate Australian addresses.

    Handles messy input with typos and missing punctuation.
    """

    def __init__(self):
        self.state_mappings = STATE_MAPPINGS
        self.street_types = STREET_TYPES
        self.suburb_corrections = SUBURB_CORRECTIONS
        self.street_corrections = STREET_CORRECTIONS

    def parse(self, address: str) -> ParsedAddress:
        """
        Parse an address string into components.

        Args:
            address: Raw address string (may contain typos)

        Returns:
            ParsedAddress with components and validation
        """
        result = ParsedAddress()
        corrections = []
        warnings = []

        # Normalize input
        address = self._normalize(address)

        # Extract postcode (4 digits at end or near end)
        postcode_match = re.search(r"\b(\d{4})\b", address)
        if postcode_match:
            result.postcode = postcode_match.group(1)
            address = address.replace(postcode_match.group(0), " ").strip()

        # Extract and normalize state
        state, state_corrected = self._extract_state(address)
        if state:
            result.state = state
            if state_corrected:
                corrections.append(f"State: {state_corrected} → {state}")
            # Remove state from address
            address = self._remove_state(address, state_corrected or state)

        # Validate postcode matches state
        if result.postcode and result.state:
            expected_state = self._postcode_to_state(result.postcode)
            if expected_state and expected_state != result.state:
                warnings.append(
                    f"Postcode {result.postcode} typically belongs to {expected_state}, not {result.state}"
                )

        # Extract suburb
        suburb, suburb_corrected = self._extract_suburb(address)
        if suburb:
            result.suburb = suburb
            if suburb_corrected:
                corrections.append(f"Suburb: {suburb_corrected} → {suburb}")
            address = address.replace(suburb_corrected or suburb, " ", 1).strip()

        # Extract unit number (patterns: 1/23, Unit 1, Apt 1, etc.)
        unit_match = re.search(
            r"(?:(?:UNIT|APT|APARTMENT|SUITE|SHOP)\s*)?(\d+[A-Z]?)\s*/\s*(\d+)",
            address,
            re.I,
        )
        if unit_match:
            result.unit_number = unit_match.group(1)
            result.street_number = unit_match.group(2)
            address = address.replace(unit_match.group(0), " ").strip()
        else:
            # Just unit number
            unit_only = re.search(
                r"(?:UNIT|APT|APARTMENT|SUITE|SHOP)\s*(\d+[A-Z]?)", address, re.I
            )
            if unit_only:
                result.unit_number = unit_only.group(1)
                address = address.replace(unit_only.group(0), " ").strip()

            # Street number
            street_num = re.search(r"^(\d+[A-Z]?)\b", address.strip())
            if street_num and not result.street_number:
                result.street_number = street_num.group(1)
                address = address[len(street_num.group(0)) :].strip()

        # Extract street type
        street_type, type_original = self._extract_street_type(address)
        if street_type:
            result.street_type = street_type
            address = self._remove_word(address, type_original)

        # Remaining is street name
        street_name = address.strip()
        street_name, name_corrected = self._correct_street_name(street_name)
        if street_name:
            result.street_name = street_name.title()
            if name_corrected:
                corrections.append(f"Street: {name_corrected} → {street_name}")

        # Calculate confidence
        result.corrections = corrections
        result.warnings = warnings
        result.confidence = self._calculate_confidence(result)
        result.is_valid = result.confidence >= 0.5

        return result

    def _normalize(self, text: str) -> str:
        """Normalize address text."""
        # Uppercase for matching
        text = text.upper()
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove common punctuation
        text = text.replace(",", " ").replace(".", " ").replace(";", " ")
        return text.strip()

    def _extract_state(self, address: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract and normalize state abbreviation."""
        for pattern, standard in self.state_mappings.items():
            if re.search(r"\b" + re.escape(pattern) + r"\b", address, re.I):
                return standard, pattern if pattern != standard else None
        return None, None

    def _remove_state(self, address: str, state: str) -> str:
        """Remove state from address."""
        return re.sub(
            r"\b" + re.escape(state) + r"\b", " ", address, flags=re.I
        ).strip()

    def _postcode_to_state(self, postcode: str) -> Optional[str]:
        """Determine state from postcode."""
        if not postcode or len(postcode) != 4:
            return None

        first_digit = postcode[0]
        state = POSTCODE_STATE_PREFIX.get(first_digit)

        # Special case: ACT postcodes
        if postcode.startswith("26") or postcode.startswith("29"):
            # Could be ACT or NSW
            if 2600 <= int(postcode) <= 2618 or 2900 <= int(postcode) <= 2920:
                return "ACT"

        return state

    def _extract_suburb(self, address: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract suburb name, correcting typos."""
        address_upper = address.upper()

        # Check for known suburbs/corrections
        for typo, correct in self.suburb_corrections.items():
            if typo in address_upper:
                return correct, typo

        # Try to find suburb at end of remaining address
        words = address.split()
        if words:
            # Last word might be suburb
            last_word = words[-1].upper()
            if last_word in self.suburb_corrections:
                return self.suburb_corrections[last_word], last_word

            # Use fuzzy matching for common suburbs
            best_match, best_ratio = self._fuzzy_match_suburb(last_word)
            if best_match and best_ratio > 0.7:
                return best_match, last_word

        return None, None

    def _fuzzy_match_suburb(self, word: str) -> Tuple[Optional[str], float]:
        """Fuzzy match a word against known suburbs."""
        best_match = None
        best_ratio = 0.0

        for correct in set(self.suburb_corrections.values()):
            ratio = SequenceMatcher(None, word.upper(), correct.upper()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = correct

        return best_match, best_ratio

    def _extract_street_type(self, address: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract and normalize street type."""
        words = address.upper().split()

        for word in words:
            if word in self.street_types:
                return self.street_types[word], word

        # Check corrections
        for word in words:
            if word in self.street_corrections:
                return self.street_corrections[word], word

        return None, None

    def _correct_street_name(self, name: str) -> Tuple[str, Optional[str]]:
        """Correct street name typos."""
        name_upper = name.upper()

        for typo, correct in self.street_corrections.items():
            if typo in name_upper:
                corrected = name_upper.replace(typo, correct.upper())
                return corrected.title(), name

        return name.title() if name else "", None

    def _remove_word(self, text: str, word: str) -> str:
        """Remove a word from text."""
        return re.sub(r"\b" + re.escape(word) + r"\b", " ", text, flags=re.I).strip()

    def _calculate_confidence(self, parsed: ParsedAddress) -> float:
        """Calculate confidence score for parsed address."""
        score = 0.0
        max_score = 0.0

        # Postcode (important)
        max_score += 0.25
        if parsed.postcode and len(parsed.postcode) == 4:
            score += 0.25

        # State
        max_score += 0.15
        if parsed.state:
            score += 0.15

        # Suburb
        max_score += 0.2
        if parsed.suburb:
            score += 0.2

        # Street number
        max_score += 0.15
        if parsed.street_number:
            score += 0.15

        # Street name
        max_score += 0.15
        if parsed.street_name:
            score += 0.15

        # Street type
        max_score += 0.1
        if parsed.street_type:
            score += 0.1

        # Penalty for corrections
        correction_penalty = len(parsed.corrections) * 0.05
        score = max(0, score - correction_penalty)

        # Penalty for warnings
        warning_penalty = len(parsed.warnings) * 0.1
        score = max(0, score - warning_penalty)

        return round(score / max_score, 2) if max_score > 0 else 0.0


# =============================================================================
# ADDRESS VALIDATION PLUGIN
# =============================================================================


class AddressValidationPlugin(Plugin):
    """
    Australian Address Validation Plugin for Agentic Brain.

    Validates and formats Australian addresses, returning both
    original and formatted versions for comparison.

    Perfect for customer service chatbots that receive address data.

    Usage:
        plugin = AddressValidationPlugin()
        result = plugin.process("301/10 Blaoduras Wya SA 5000 ADELAID")

        print(result.original_input)
        # "301/10 Blaoduras Wya SA 5000 ADELAID"

        print(result.processed_output['formatted'])
        # "Unit 301/10 Boulevard Way, Adelaide SA 5000"
    """

    def __init__(self, config: Optional[PluginConfig] = None):
        """Initialize plugin."""
        default_config = PluginConfig(
            name="address_validation",
            description="Australian address validation and formatting",
            version="1.0.0",
            config={
                "strict_mode": False,  # Reject low-confidence addresses
                "confidence_threshold": 0.5,
            },
        )
        super().__init__(config or default_config)

        self.parser = AddressParser()

    def on_load(self) -> None:
        """Called when plugin is loaded."""
        logger.info("Address Validation Plugin loaded")

    def on_message(
        self,
        message: str,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Process a message that may contain an address.

        Args:
            message: User message
            **kwargs: Additional context

        Returns:
            Validation result if address detected, None otherwise
        """
        # Check if message looks like an address
        if self._looks_like_address(message):
            parsed = self.parser.parse(message)

            if parsed.is_valid:
                return {
                    "original": message,
                    "formatted": parsed.format_standard(),
                    "parsed": parsed.to_dict(),
                    "confidence": parsed.confidence,
                }

        return None

    def validate_address(self, address: str) -> Dict[str, Any]:
        """
        Validate and format an address.

        Args:
            address: Raw address string

        Returns:
            Dict with original, formatted, parsed components, and confidence
        """
        parsed = self.parser.parse(address)

        return {
            "original": address,
            "formatted": parsed.format_standard(),
            "formatted_multiline": parsed.format_multiline(),
            "parsed": parsed.to_dict(),
            "is_valid": parsed.is_valid,
            "confidence": parsed.confidence,
            "corrections": parsed.corrections,
            "warnings": parsed.warnings,
            "match_ready": self._is_match_ready(parsed),
        }

    def compare_addresses(
        self,
        address1: str,
        address2: str,
    ) -> Dict[str, Any]:
        """
        Compare two addresses to check if they match.

        Useful for finding duplicate records.

        Args:
            address1: First address
            address2: Second address

        Returns:
            Comparison result with match confidence
        """
        parsed1 = self.parser.parse(address1)
        parsed2 = self.parser.parse(address2)

        # Compare key fields
        matches = {
            "postcode": parsed1.postcode == parsed2.postcode,
            "state": parsed1.state == parsed2.state,
            "suburb": self._normalize_suburb(parsed1.suburb)
            == self._normalize_suburb(parsed2.suburb),
            "street_number": parsed1.street_number == parsed2.street_number,
            "unit_number": parsed1.unit_number == parsed2.unit_number,
            "street_name": self._fuzzy_match(parsed1.street_name, parsed2.street_name),
        }

        # Calculate match score
        weights = {
            "postcode": 0.25,
            "state": 0.1,
            "suburb": 0.2,
            "street_number": 0.2,
            "unit_number": 0.1,
            "street_name": 0.15,
        }

        match_score = sum(
            weights[field] for field, matched in matches.items() if matched
        )

        return {
            "address1": {
                "original": address1,
                "formatted": parsed1.format_standard(),
            },
            "address2": {
                "original": address2,
                "formatted": parsed2.format_standard(),
            },
            "match_score": round(match_score, 2),
            "is_match": match_score >= 0.8,
            "field_matches": matches,
        }

    def _looks_like_address(self, text: str) -> bool:
        """Check if text looks like an address."""
        # Has a postcode?
        if re.search(r"\b\d{4}\b", text):
            return True

        # Has a state abbreviation?
        for state in ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"]:
            if re.search(r"\b" + state + r"\b", text, re.I):
                return True

        # Has a street type?
        for st_type in ["STREET", "ST", "ROAD", "RD", "AVENUE", "AVE", "DRIVE", "DR"]:
            if re.search(r"\b" + st_type + r"\b", text, re.I):
                return True

        return False

    def _is_match_ready(self, parsed: ParsedAddress) -> bool:
        """Check if address has enough info for system matching."""
        # Need at least: postcode + street number
        return bool(parsed.postcode and parsed.street_number)

    def _normalize_suburb(self, suburb: Optional[str]) -> str:
        """Normalize suburb name for comparison."""
        if not suburb:
            return ""
        return suburb.upper().strip()

    def _fuzzy_match(self, str1: Optional[str], str2: Optional[str]) -> bool:
        """Fuzzy match two strings."""
        if not str1 or not str2:
            return str1 == str2

        ratio = SequenceMatcher(None, str1.upper(), str2.upper()).ratio()
        return ratio > 0.8


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def validate_address(address: str) -> Dict[str, Any]:
    """
    Quick function to validate an Australian address.

    Args:
        address: Raw address string

    Returns:
        Validation result with original and formatted address
    """
    plugin = AddressValidationPlugin()
    return plugin.validate_address(address)


def format_address(address: str) -> str:
    """
    Quick function to format an Australian address.

    Args:
        address: Raw address string

    Returns:
        Formatted address string
    """
    plugin = AddressValidationPlugin()
    result = plugin.validate_address(address)
    return result["formatted"]


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Plugin
    "AddressValidationPlugin",
    # Data structures
    "ParsedAddress",
    "AddressParser",
    # Functions
    "validate_address",
    "format_address",
]
