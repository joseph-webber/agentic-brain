#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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
Comprehensive tests for the legal disclaimers module.

Tests cover:
- DisclaimerType enum
- All disclaimer constants
- get_disclaimer() function
- format_disclaimer() function
- combine_disclaimers() function
- get_acl_notice() function
- get_privacy_notice() function
"""

from datetime import datetime

import pytest

from agentic_brain.legal import (
    ACL_CONSUMER_RIGHTS,
    AI_DISCLAIMER,
    DEFENCE_DISCLAIMER,
    FINANCIAL_DISCLAIMER,
    GENERAL_DISCLAIMER,
    LEGAL_DISCLAIMER,
    # Constants
    MEDICAL_DISCLAIMER,
    NDIS_DISCLAIMER,
    PRIVACY_COLLECTION_NOTICE,
    # Enums
    DisclaimerType,
    combine_disclaimers,
    format_disclaimer,
    get_acl_notice,
    # Functions
    get_disclaimer,
    get_privacy_notice,
)

# ══════════════════════════════════════════════════════════════════════════════
# DisclaimerType Enum Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestDisclaimerTypeEnum:
    """Tests for the DisclaimerType enum."""

    def test_medical_type_exists(self):
        """Medical disclaimer type should exist."""
        assert DisclaimerType.MEDICAL.value == "medical"

    def test_healthcare_alias(self):
        """Healthcare should be alias for medical."""
        assert DisclaimerType.HEALTHCARE.value == "medical"

    def test_financial_type_exists(self):
        """Financial disclaimer type should exist."""
        assert DisclaimerType.FINANCIAL.value == "financial"

    def test_investment_alias(self):
        """Investment should be alias for financial."""
        assert DisclaimerType.INVESTMENT.value == "financial"

    def test_legal_type_exists(self):
        """Legal disclaimer type should exist."""
        assert DisclaimerType.LEGAL.value == "legal"

    def test_ndis_type_exists(self):
        """NDIS disclaimer type should exist."""
        assert DisclaimerType.NDIS.value == "ndis"

    def test_disability_alias(self):
        """Disability should be alias for NDIS."""
        assert DisclaimerType.DISABILITY.value == "ndis"

    def test_defence_type_exists(self):
        """Defence disclaimer type should exist."""
        assert DisclaimerType.DEFENCE.value == "defence"

    def test_government_alias(self):
        """Government should be alias for defence."""
        assert DisclaimerType.GOVERNMENT.value == "defence"

    def test_ai_type_exists(self):
        """AI disclaimer type should exist."""
        assert DisclaimerType.AI.value == "ai"

    def test_ml_alias(self):
        """ML should be alias for AI."""
        assert DisclaimerType.ML.value == "ai"

    def test_general_type_exists(self):
        """General disclaimer type should exist."""
        assert DisclaimerType.GENERAL.value == "general"

    def test_all_types_iterable(self):
        """Should be able to iterate over all disclaimer types."""
        types = list(DisclaimerType)
        assert len(types) >= 7  # At least 7 types (including aliases)


# ══════════════════════════════════════════════════════════════════════════════
# Disclaimer Constants Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestDisclaimerConstants:
    """Tests for disclaimer constant strings."""

    def test_medical_disclaimer_not_empty(self):
        """Medical disclaimer should not be empty."""
        assert MEDICAL_DISCLAIMER
        assert len(MEDICAL_DISCLAIMER) > 100

    def test_medical_disclaimer_contains_key_terms(self):
        """Medical disclaimer should contain required terms."""
        assert "NOT" in MEDICAL_DISCLAIMER
        assert (
            "professional medical advice" in MEDICAL_DISCLAIMER.lower()
            or "medical" in MEDICAL_DISCLAIMER.lower()
        )
        assert "000" in MEDICAL_DISCLAIMER or "emergency" in MEDICAL_DISCLAIMER.lower()
        assert "TGA" in MEDICAL_DISCLAIMER or "Therapeutic" in MEDICAL_DISCLAIMER

    def test_financial_disclaimer_not_empty(self):
        """Financial disclaimer should not be empty."""
        assert FINANCIAL_DISCLAIMER
        assert len(FINANCIAL_DISCLAIMER) > 100

    def test_financial_disclaimer_contains_key_terms(self):
        """Financial disclaimer should contain required terms."""
        assert (
            "AFSL" in FINANCIAL_DISCLAIMER
            or "Financial Services" in FINANCIAL_DISCLAIMER
        )
        assert "advice" in FINANCIAL_DISCLAIMER.lower()
        assert "liability" in FINANCIAL_DISCLAIMER.lower()

    def test_legal_disclaimer_not_empty(self):
        """Legal disclaimer should not be empty."""
        assert LEGAL_DISCLAIMER
        assert len(LEGAL_DISCLAIMER) > 100

    def test_legal_disclaimer_contains_key_terms(self):
        """Legal disclaimer should contain required terms."""
        assert "NOT" in LEGAL_DISCLAIMER
        assert "legal advice" in LEGAL_DISCLAIMER.lower()
        assert (
            "lawyer" in LEGAL_DISCLAIMER.lower()
            or "legal practitioner" in LEGAL_DISCLAIMER.lower()
        )

    def test_ndis_disclaimer_not_empty(self):
        """NDIS disclaimer should not be empty."""
        assert NDIS_DISCLAIMER
        assert len(NDIS_DISCLAIMER) > 100

    def test_ndis_disclaimer_contains_key_terms(self):
        """NDIS disclaimer should contain required terms."""
        assert "NDIS" in NDIS_DISCLAIMER
        assert "Price Guide" in NDIS_DISCLAIMER or "pricing" in NDIS_DISCLAIMER.lower()
        assert "Quality" in NDIS_DISCLAIMER or "Safeguards" in NDIS_DISCLAIMER

    def test_defence_disclaimer_not_empty(self):
        """Defence disclaimer should not be empty."""
        assert DEFENCE_DISCLAIMER
        assert len(DEFENCE_DISCLAIMER) > 100

    def test_defence_disclaimer_contains_key_terms(self):
        """Defence disclaimer should contain required security terms."""
        assert "CLASSIFIED" in DEFENCE_DISCLAIMER or "classified" in DEFENCE_DISCLAIMER
        assert "security" in DEFENCE_DISCLAIMER.lower()
        assert "ISM" in DEFENCE_DISCLAIMER or "Essential Eight" in DEFENCE_DISCLAIMER

    def test_ai_disclaimer_not_empty(self):
        """AI disclaimer should not be empty."""
        assert AI_DISCLAIMER
        assert len(AI_DISCLAIMER) > 100

    def test_ai_disclaimer_contains_key_terms(self):
        """AI disclaimer should contain required AI terms."""
        assert (
            "AI" in AI_DISCLAIMER or "artificial intelligence" in AI_DISCLAIMER.lower()
        )
        assert (
            "hallucination" in AI_DISCLAIMER.lower() or "error" in AI_DISCLAIMER.lower()
        )
        assert "bias" in AI_DISCLAIMER.lower() or "limitation" in AI_DISCLAIMER.lower()

    def test_general_disclaimer_not_empty(self):
        """General disclaimer should not be empty."""
        assert GENERAL_DISCLAIMER
        assert len(GENERAL_DISCLAIMER) > 50

    def test_acl_consumer_rights_not_empty(self):
        """ACL consumer rights notice should not be empty."""
        assert ACL_CONSUMER_RIGHTS
        assert len(ACL_CONSUMER_RIGHTS) > 100

    def test_acl_contains_consumer_law_reference(self):
        """ACL notice should reference Australian Consumer Law."""
        assert "Consumer" in ACL_CONSUMER_RIGHTS
        assert (
            "guarantee" in ACL_CONSUMER_RIGHTS.lower()
            or "right" in ACL_CONSUMER_RIGHTS.lower()
        )

    def test_privacy_collection_notice_not_empty(self):
        """Privacy collection notice should not be empty."""
        assert PRIVACY_COLLECTION_NOTICE
        assert len(PRIVACY_COLLECTION_NOTICE) > 50


# ══════════════════════════════════════════════════════════════════════════════
# get_disclaimer() Function Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestGetDisclaimer:
    """Tests for the get_disclaimer() function."""

    def test_get_medical_disclaimer(self):
        """Should return medical disclaimer."""
        result = get_disclaimer(DisclaimerType.MEDICAL)
        assert result
        assert "medical" in result.lower() or "health" in result.lower()

    def test_get_medical_via_healthcare_alias(self):
        """Healthcare alias should return same as medical."""
        medical = get_disclaimer(DisclaimerType.MEDICAL)
        healthcare = get_disclaimer(DisclaimerType.HEALTHCARE)
        assert medical == healthcare

    def test_get_financial_disclaimer(self):
        """Should return financial disclaimer."""
        result = get_disclaimer(DisclaimerType.FINANCIAL)
        assert result
        assert "financial" in result.lower()

    def test_get_financial_via_investment_alias(self):
        """Investment alias should return same as financial."""
        financial = get_disclaimer(DisclaimerType.FINANCIAL)
        investment = get_disclaimer(DisclaimerType.INVESTMENT)
        assert financial == investment

    def test_get_legal_disclaimer(self):
        """Should return legal disclaimer."""
        result = get_disclaimer(DisclaimerType.LEGAL)
        assert result
        assert "legal" in result.lower()

    def test_get_ndis_disclaimer(self):
        """Should return NDIS disclaimer."""
        result = get_disclaimer(DisclaimerType.NDIS)
        assert result
        assert "NDIS" in result

    def test_get_ndis_via_disability_alias(self):
        """Disability alias should return same as NDIS."""
        ndis = get_disclaimer(DisclaimerType.NDIS)
        disability = get_disclaimer(DisclaimerType.DISABILITY)
        assert ndis == disability

    def test_get_defence_disclaimer(self):
        """Should return defence disclaimer."""
        result = get_disclaimer(DisclaimerType.DEFENCE)
        assert result
        assert "defence" in result.lower() or "security" in result.lower()

    def test_get_defence_via_government_alias(self):
        """Government alias should return same as defence."""
        defence = get_disclaimer(DisclaimerType.DEFENCE)
        government = get_disclaimer(DisclaimerType.GOVERNMENT)
        assert defence == government

    def test_get_ai_disclaimer(self):
        """Should return AI disclaimer."""
        result = get_disclaimer(DisclaimerType.AI)
        assert result
        assert "AI" in result or "artificial" in result.lower()

    def test_get_ai_via_ml_alias(self):
        """ML alias should return same as AI."""
        ai = get_disclaimer(DisclaimerType.AI)
        ml = get_disclaimer(DisclaimerType.ML)
        assert ai == ml

    def test_get_general_disclaimer(self):
        """Should return general disclaimer."""
        result = get_disclaimer(DisclaimerType.GENERAL)
        assert result

    def test_get_disclaimer_compact_mode(self):
        """Compact mode should return shorter version."""
        full = get_disclaimer(DisclaimerType.MEDICAL)
        compact = get_disclaimer(DisclaimerType.MEDICAL, compact=True)
        # Compact should be shorter or equal
        assert len(compact) <= len(full)

    def test_all_types_return_non_empty(self):
        """All disclaimer types should return non-empty strings."""
        unique_types = [
            DisclaimerType.MEDICAL,
            DisclaimerType.FINANCIAL,
            DisclaimerType.LEGAL,
            DisclaimerType.NDIS,
            DisclaimerType.DEFENCE,
            DisclaimerType.AI,
            DisclaimerType.GENERAL,
        ]
        for dtype in unique_types:
            result = get_disclaimer(dtype)
            assert result, f"{dtype} returned empty disclaimer"
            assert len(result) > 20, f"{dtype} disclaimer too short"


# ══════════════════════════════════════════════════════════════════════════════
# format_disclaimer() Function Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestFormatDisclaimer:
    """Tests for the format_disclaimer() function."""

    def test_format_text_default(self):
        """Default format should be text."""
        result = format_disclaimer(DisclaimerType.MEDICAL)
        assert result
        assert isinstance(result, str)

    def test_format_text_explicit(self):
        """Explicit text format should work."""
        result = format_disclaimer(DisclaimerType.MEDICAL, format="text")
        assert result
        # Text format should preserve box characters
        assert "╔" in result or "IMPORTANT" in result

    def test_format_html(self):
        """HTML format should produce HTML tags."""
        result = format_disclaimer(DisclaimerType.MEDICAL, format="html")
        assert result
        assert "<" in result and ">" in result
        assert "div" in result.lower() or "br" in result.lower()

    def test_format_markdown(self):
        """Markdown format should produce blockquotes."""
        result = format_disclaimer(DisclaimerType.MEDICAL, format="markdown")
        assert result
        assert ">" in result  # Markdown blockquote

    def test_format_with_timestamp(self):
        """Include timestamp option should add timestamp."""
        result = format_disclaimer(DisclaimerType.MEDICAL, include_timestamp=True)
        assert result
        assert "Disclaimer shown:" in result or datetime.now().strftime("%Y") in result

    def test_format_html_with_timestamp(self):
        """HTML format with timestamp should work."""
        result = format_disclaimer(
            DisclaimerType.FINANCIAL, format="html", include_timestamp=True
        )
        assert result
        assert "<" in result

    def test_format_markdown_with_timestamp(self):
        """Markdown format with timestamp should work."""
        result = format_disclaimer(
            DisclaimerType.LEGAL, format="markdown", include_timestamp=True
        )
        assert result
        assert ">" in result

    def test_format_all_types_as_html(self):
        """All types should format to HTML without error."""
        types = [
            DisclaimerType.MEDICAL,
            DisclaimerType.FINANCIAL,
            DisclaimerType.LEGAL,
            DisclaimerType.NDIS,
            DisclaimerType.AI,
        ]
        for dtype in types:
            result = format_disclaimer(dtype, format="html")
            assert result, f"{dtype} failed HTML format"

    def test_format_all_types_as_markdown(self):
        """All types should format to markdown without error."""
        types = [
            DisclaimerType.MEDICAL,
            DisclaimerType.FINANCIAL,
            DisclaimerType.LEGAL,
            DisclaimerType.NDIS,
            DisclaimerType.AI,
        ]
        for dtype in types:
            result = format_disclaimer(dtype, format="markdown")
            assert result, f"{dtype} failed markdown format"


# ══════════════════════════════════════════════════════════════════════════════
# combine_disclaimers() Function Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestCombineDisclaimers:
    """Tests for the combine_disclaimers() function."""

    def test_combine_two_disclaimers(self):
        """Should combine two disclaimers."""
        result = combine_disclaimers(DisclaimerType.AI, DisclaimerType.MEDICAL)
        assert result
        # Should contain content from both
        assert "AI" in result or "artificial" in result.lower()
        assert "medical" in result.lower() or "health" in result.lower()

    def test_combine_three_disclaimers(self):
        """Should combine three disclaimers."""
        result = combine_disclaimers(
            DisclaimerType.AI, DisclaimerType.MEDICAL, DisclaimerType.FINANCIAL
        )
        assert result
        assert "AI" in result or "artificial" in result.lower()
        assert "financial" in result.lower()

    def test_combined_longer_than_individual(self):
        """Combined disclaimers should be longer than individuals."""
        medical = get_disclaimer(DisclaimerType.MEDICAL)
        financial = get_disclaimer(DisclaimerType.FINANCIAL)
        combined = combine_disclaimers(DisclaimerType.MEDICAL, DisclaimerType.FINANCIAL)
        assert len(combined) > len(medical)
        assert len(combined) > len(financial)

    def test_combine_single_disclaimer(self):
        """Combining single disclaimer should work."""
        result = combine_disclaimers(DisclaimerType.AI)
        ai_only = get_disclaimer(DisclaimerType.AI)
        assert result == ai_only

    def test_combine_all_major_types(self):
        """Should be able to combine all major types."""
        result = combine_disclaimers(
            DisclaimerType.MEDICAL,
            DisclaimerType.FINANCIAL,
            DisclaimerType.LEGAL,
            DisclaimerType.AI,
        )
        assert result
        assert len(result) > 500  # Should be substantial


# ══════════════════════════════════════════════════════════════════════════════
# get_acl_notice() Function Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestGetAclNotice:
    """Tests for the get_acl_notice() function."""

    def test_returns_non_empty(self):
        """Should return non-empty string."""
        result = get_acl_notice()
        assert result
        assert len(result) > 50

    def test_contains_consumer_law_content(self):
        """Should contain Australian Consumer Law content."""
        result = get_acl_notice()
        assert "consumer" in result.lower() or "Consumer" in result

    def test_returns_same_as_constant(self):
        """Should return the ACL_CONSUMER_RIGHTS constant."""
        result = get_acl_notice()
        assert result == ACL_CONSUMER_RIGHTS


# ══════════════════════════════════════════════════════════════════════════════
# get_privacy_notice() Function Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestGetPrivacyNotice:
    """Tests for the get_privacy_notice() function."""

    def test_returns_non_empty(self):
        """Should return non-empty string."""
        result = get_privacy_notice()
        assert result
        assert len(result) > 20

    def test_default_notice(self):
        """Default notice without customisation."""
        result = get_privacy_notice()
        assert "personal information" in result.lower() or "privacy" in result.lower()

    def test_with_company_name(self):
        """Should include company name when provided."""
        result = get_privacy_notice(company_name="Test Corp")
        assert "Test Corp" in result

    def test_with_contact_email(self):
        """Should include contact email when provided."""
        result = get_privacy_notice(contact_email="privacy@test.com")
        assert "privacy@test.com" in result

    def test_with_both_customisations(self):
        """Should include both company and email."""
        result = get_privacy_notice(
            company_name="Acme Ltd", contact_email="data@acme.com"
        )
        assert "Acme Ltd" in result
        assert "data@acme.com" in result

    def test_none_values_handled(self):
        """None values should not break the function."""
        result = get_privacy_notice(company_name=None, contact_email=None)
        assert result
        assert len(result) > 20


# ══════════════════════════════════════════════════════════════════════════════
# Australian Compliance Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestAustralianCompliance:
    """Tests ensuring Australian regulatory compliance."""

    def test_medical_references_tga(self):
        """Medical disclaimer should reference TGA."""
        disclaimer = MEDICAL_DISCLAIMER
        assert "TGA" in disclaimer or "Therapeutic Goods" in disclaimer

    def test_medical_references_emergency_number(self):
        """Medical disclaimer should reference 000."""
        disclaimer = MEDICAL_DISCLAIMER
        assert "000" in disclaimer or "Triple Zero" in disclaimer

    def test_financial_references_afsl(self):
        """Financial disclaimer should reference AFSL."""
        disclaimer = FINANCIAL_DISCLAIMER
        assert "AFSL" in disclaimer or "Australian Financial Services" in disclaimer

    def test_ndis_references_price_guide(self):
        """NDIS disclaimer should reference Price Guide."""
        disclaimer = NDIS_DISCLAIMER
        assert "Price Guide" in disclaimer or "pricing" in disclaimer.lower()

    def test_ndis_references_quality_safeguards(self):
        """NDIS disclaimer should reference Quality and Safeguards Commission."""
        disclaimer = NDIS_DISCLAIMER
        assert "Quality" in disclaimer or "Safeguards" in disclaimer

    def test_defence_references_ism(self):
        """Defence disclaimer should reference ISM or security standards."""
        disclaimer = DEFENCE_DISCLAIMER
        # ISM = Information Security Manual
        assert (
            "ISM" in disclaimer
            or "Essential Eight" in disclaimer
            or "security" in disclaimer.lower()
        )

    def test_defence_references_classification(self):
        """Defence disclaimer should reference security classification."""
        disclaimer = DEFENCE_DISCLAIMER
        assert (
            "CLASSIFIED" in disclaimer
            or "PROTECTED" in disclaimer
            or "OFFICIAL" in disclaimer
        )

    def test_acl_is_mandatory_notice(self):
        """ACL notice should be present and substantial."""
        notice = ACL_CONSUMER_RIGHTS
        assert len(notice) > 100
        assert "consumer" in notice.lower() or "guarantee" in notice.lower()


# ══════════════════════════════════════════════════════════════════════════════
# Edge Cases and Error Handling
# ══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_invalid_format_fallback(self):
        """Invalid format should fallback gracefully."""
        # Should not raise, should return something
        result = format_disclaimer(DisclaimerType.MEDICAL, format="invalid")
        assert result

    def test_empty_company_name_string(self):
        """Empty string company name handled."""
        result = get_privacy_notice(company_name="")
        assert result

    def test_whitespace_company_name(self):
        """Whitespace-only company name handled."""
        result = get_privacy_notice(company_name="   ")
        assert result

    def test_special_characters_in_company_name(self):
        """Special characters in company name handled."""
        result = get_privacy_notice(company_name="Test & Co <Ltd>")
        assert result
        assert "Test & Co" in result

    def test_unicode_in_company_name(self):
        """Unicode characters in company name handled."""
        result = get_privacy_notice(company_name="Test™ Pty Ltd")
        assert result
        assert "Test™" in result

    def test_long_company_name(self):
        """Very long company name handled."""
        long_name = "A" * 500
        result = get_privacy_notice(company_name=long_name)
        assert result
        assert long_name in result


# ══════════════════════════════════════════════════════════════════════════════
# Module-level Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestModuleExports:
    """Tests for module exports and __all__."""

    def test_disclaimer_type_exported(self):
        """DisclaimerType should be exported."""
        from agentic_brain.legal import DisclaimerType

        assert DisclaimerType

    def test_all_constants_exported(self):
        """All disclaimer constants should be exported."""
        from agentic_brain.legal import (
            ACL_CONSUMER_RIGHTS,
            AI_DISCLAIMER,
            DEFENCE_DISCLAIMER,
            FINANCIAL_DISCLAIMER,
            GENERAL_DISCLAIMER,
            LEGAL_DISCLAIMER,
            MEDICAL_DISCLAIMER,
            NDIS_DISCLAIMER,
            PRIVACY_COLLECTION_NOTICE,
        )

        assert all(
            [
                MEDICAL_DISCLAIMER,
                FINANCIAL_DISCLAIMER,
                LEGAL_DISCLAIMER,
                NDIS_DISCLAIMER,
                DEFENCE_DISCLAIMER,
                AI_DISCLAIMER,
                GENERAL_DISCLAIMER,
                ACL_CONSUMER_RIGHTS,
                PRIVACY_COLLECTION_NOTICE,
            ]
        )

    def test_all_functions_exported(self):
        """All functions should be exported."""
        from agentic_brain.legal import (
            format_disclaimer,
            get_acl_notice,
            get_disclaimer,
            get_privacy_notice,
        )

        assert all(
            [
                get_disclaimer,
                get_acl_notice,
                format_disclaimer,
                get_privacy_notice,
            ]
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
