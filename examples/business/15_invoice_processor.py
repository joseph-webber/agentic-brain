#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 15: Invoice Processor with AI Extraction

Demonstrates:
- PDF text extraction
- AI-powered data extraction
- Structured output parsing
- Google Sheets integration pattern
- Multi-vendor format handling

This shows a real-world invoice processing pipeline that:
1. Extracts text from PDF invoices
2. Uses AI to parse invoice details
3. Validates extracted data
4. Logs to a spreadsheet

Requirements:
- Ollama running with llama3.1:8b
- pypdf2 for PDF extraction (optional)

Author: agentic-brain
License: MIT
"""

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

# Agentic Brain imports
from agentic_brain.router import LLMRouter

# ─────────────────────────────────────────────────────────────────────────────
# INVOICE MODELS
# ─────────────────────────────────────────────────────────────────────────────


class InvoiceStatus(Enum):
    """Invoice processing status."""

    PENDING = "pending"
    EXTRACTED = "extracted"
    VALIDATED = "validated"
    LOGGED = "logged"
    FAILED = "failed"


@dataclass
class InvoiceData:
    """Extracted invoice data."""

    vendor_name: str
    invoice_number: str
    invoice_date: str
    due_date: Optional[str]
    subtotal: float
    tax: float
    total: float
    currency: str = "AUD"
    line_items: list[dict] = None

    def __post_init__(self):
        if self.line_items is None:
            self.line_items = []


@dataclass
class ProcessingResult:
    """Result of invoice processing."""

    status: InvoiceStatus
    data: Optional[InvoiceData]
    confidence: float
    errors: list[str]
    raw_text: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# VENDOR PROFILES (configure per vendor)
# ─────────────────────────────────────────────────────────────────────────────


VENDOR_PROFILES = {
    "innovative": {
        "name": "Innovative Music",
        "sender_domain": "halleonard.com.au",
        "subject_pattern": r"Innovative Music Invoice",
        "date_format": "%d/%m/%Y",
        "total_pattern": r"Total\s*[:\$]\s*([\d,]+\.?\d*)",
    },
    "ambertech": {
        "name": "Ambertech",
        "sender_domain": "ambertech.com.au",
        "subject_pattern": r"TAX INVOICE",
        "date_format": "%d-%m-%Y",
        "total_pattern": r"Total.*?([\d,]+\.\d{2})",
    },
    "generic": {
        "name": "Unknown Vendor",
        "sender_domain": "*",
        "subject_pattern": r"invoice|bill|statement",
        "date_format": "%Y-%m-%d",
        "total_pattern": r"(?:Total|Amount Due)[:\s]*\$?([\d,]+\.?\d*)",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# PDF TEXT EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF file.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Extracted text content
    """
    try:
        # Try pypdf2 if available
        from pypdf2 import PdfReader

        reader = PdfReader(pdf_path)
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)
    except ImportError:
        # Fallback: return sample text for demo
        return """
        TAX INVOICE
        Innovative Music Distribution
        ABN: 12 345 678 901
        
        Invoice Number: INV-2026-0123
        Invoice Date: 20/03/2026
        Due Date: 19/04/2026
        
        Bill To:
        HappySkies Store
        123 Business Street
        Adelaide SA 5000
        
        Items:
        1x Sheet Music - Bach Collection     $45.00
        2x Guitar Strings Set                $32.00
        1x Music Stand                       $89.00
        
        Subtotal:                           $166.00
        GST (10%):                           $16.60
        
        TOTAL:                             $182.60
        
        Payment Terms: Net 30
        """


# ─────────────────────────────────────────────────────────────────────────────
# AI INVOICE EXTRACTOR
# ─────────────────────────────────────────────────────────────────────────────


class InvoiceExtractor:
    """AI-powered invoice data extractor.

    Uses an LLM to intelligently extract structured data
    from invoice text, handling multiple vendor formats.
    """

    EXTRACTION_PROMPT = """You are an expert invoice parser. Extract data from this invoice text.

Return ONLY valid JSON in this exact format (no other text):
{{
    "vendor_name": "Company Name",
    "invoice_number": "INV-123",
    "invoice_date": "YYYY-MM-DD",
    "due_date": "YYYY-MM-DD or null",
    "subtotal": 100.00,
    "tax": 10.00,
    "total": 110.00,
    "currency": "AUD",
    "line_items": [
        {{"description": "Item 1", "quantity": 1, "unit_price": 50.00, "total": 50.00}},
        {{"description": "Item 2", "quantity": 2, "unit_price": 25.00, "total": 50.00}}
    ],
    "confidence": 0.95
}}

Invoice text:
{invoice_text}

IMPORTANT:
- Convert all dates to YYYY-MM-DD format
- Use null for missing optional fields
- Extract ALL line items if visible
- Set confidence 0.0-1.0 based on clarity
"""

    def __init__(self, model: str = "llama3.1:8b"):
        """Initialize the extractor."""
        self.model = model
        self.router: Optional[LLMRouter] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.router = LLMRouter(
            providers=["ollama"],
            default_model=self.model,
        )
        await self.router.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.router:
            await self.router.__aexit__(exc_type, exc_val, exc_tb)

    async def extract(
        self, text: str, vendor_hint: Optional[str] = None
    ) -> ProcessingResult:
        """Extract invoice data from text.

        Args:
            text: Invoice text content
            vendor_hint: Optional vendor name for format hints

        Returns:
            ProcessingResult with extracted data
        """
        errors = []

        # Step 1: Try rule-based extraction first
        rule_based = self._extract_with_rules(text, vendor_hint)
        if rule_based and rule_based.total > 0:
            return ProcessingResult(
                status=InvoiceStatus.EXTRACTED,
                data=rule_based,
                confidence=0.9,
                errors=[],
                raw_text=text,
            )

        # Step 2: Fall back to AI extraction
        prompt = self.EXTRACTION_PROMPT.format(invoice_text=text[:3000])

        try:
            response = await self.router.complete(prompt)
            data, confidence = self._parse_ai_response(response)

            if data:
                return ProcessingResult(
                    status=InvoiceStatus.EXTRACTED,
                    data=data,
                    confidence=confidence,
                    errors=[],
                    raw_text=text,
                )
            else:
                errors.append("Failed to parse AI response")
        except Exception as e:
            errors.append(f"AI extraction error: {e}")

        return ProcessingResult(
            status=InvoiceStatus.FAILED,
            data=None,
            confidence=0.0,
            errors=errors,
            raw_text=text,
        )

    def _extract_with_rules(
        self, text: str, vendor_hint: Optional[str] = None
    ) -> Optional[InvoiceData]:
        """Try rule-based extraction for known vendors."""
        profile = VENDOR_PROFILES.get(vendor_hint, VENDOR_PROFILES["generic"])

        # Extract invoice number
        inv_match = re.search(
            r"(?:Invoice|Inv)[\s#:]*([A-Z0-9\-]+)",
            text,
            re.IGNORECASE,
        )
        invoice_number = inv_match.group(1) if inv_match else "UNKNOWN"

        # Extract total
        total_match = re.search(profile["total_pattern"], text)
        if not total_match:
            return None

        total_str = total_match.group(1).replace(",", "")
        try:
            total = float(total_str)
        except ValueError:
            return None

        # Extract dates
        date_match = re.search(
            r"(?:Invoice Date|Date)[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
            text,
            re.IGNORECASE,
        )
        invoice_date = (
            date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d")
        )

        # Extract vendor name
        vendor_name = profile["name"]
        if vendor_name == "Unknown Vendor":
            # Try to extract from text
            vendor_match = re.search(
                r"^(.+?)\n(?:ABN|ACN|Invoice)",
                text.strip(),
                re.MULTILINE,
            )
            if vendor_match:
                vendor_name = vendor_match.group(1).strip()

        # Estimate tax (assume 10% GST)
        tax = round(total / 11, 2)
        subtotal = round(total - tax, 2)

        return InvoiceData(
            vendor_name=vendor_name,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            due_date=None,
            subtotal=subtotal,
            tax=tax,
            total=total,
        )

    def _parse_ai_response(self, response: str) -> tuple[Optional[InvoiceData], float]:
        """Parse AI JSON response into InvoiceData."""
        # Find JSON in response
        json_match = re.search(r"\{[\s\S]*\}", response)
        if not json_match:
            return None, 0.0

        try:
            data = json.loads(json_match.group())

            invoice = InvoiceData(
                vendor_name=data.get("vendor_name", "Unknown"),
                invoice_number=data.get("invoice_number", "UNKNOWN"),
                invoice_date=data.get("invoice_date", ""),
                due_date=data.get("due_date"),
                subtotal=float(data.get("subtotal", 0)),
                tax=float(data.get("tax", 0)),
                total=float(data.get("total", 0)),
                currency=data.get("currency", "AUD"),
                line_items=data.get("line_items", []),
            )

            confidence = float(data.get("confidence", 0.7))
            return invoice, confidence

        except (json.JSONDecodeError, KeyError, ValueError):
            return None, 0.0


# ─────────────────────────────────────────────────────────────────────────────
# INVOICE VALIDATOR
# ─────────────────────────────────────────────────────────────────────────────


def validate_invoice(data: InvoiceData) -> tuple[bool, list[str]]:
    """Validate extracted invoice data.

    Args:
        data: Extracted invoice data

    Returns:
        Tuple of (is_valid, list of errors)
    """
    errors = []

    # Required fields
    if not data.invoice_number or data.invoice_number == "UNKNOWN":
        errors.append("Missing invoice number")

    if not data.invoice_date:
        errors.append("Missing invoice date")

    if data.total <= 0:
        errors.append("Invalid total amount")

    # Math validation
    expected_total = data.subtotal + data.tax
    if abs(expected_total - data.total) > 0.02:  # Allow 2 cent rounding
        errors.append(f"Total mismatch: {data.subtotal} + {data.tax} != {data.total}")

    # Date validation
    if data.invoice_date:
        try:
            # Try common date formats
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
                try:
                    datetime.strptime(data.invoice_date, fmt)
                    break
                except ValueError:
                    continue
            else:
                errors.append(f"Invalid date format: {data.invoice_date}")
        except Exception:
            errors.append(f"Cannot parse date: {data.invoice_date}")

    return len(errors) == 0, errors


# ─────────────────────────────────────────────────────────────────────────────
# SPREADSHEET LOGGER (stub - implement with gspread in production)
# ─────────────────────────────────────────────────────────────────────────────


class SpreadsheetLogger:
    """Logs invoice data to Google Sheets (stub implementation)."""

    def __init__(self, spreadsheet_id: str = "demo"):
        self.spreadsheet_id = spreadsheet_id
        self.logged_invoices: list[InvoiceData] = []

    def log_invoice(self, data: InvoiceData) -> bool:
        """Log invoice to spreadsheet.

        In production, this would use gspread:
        ```
        import gspread
        gc = gspread.service_account()
        sheet = gc.open_by_key(self.spreadsheet_id).sheet1
        sheet.append_row([
            data.invoice_date,
            data.vendor_name,
            data.invoice_number,
            data.total,
        ])
        ```
        """
        self.logged_invoices.append(data)
        print(f"📊 Logged to sheet: {data.vendor_name} - ${data.total:.2f}")
        return True


# ─────────────────────────────────────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────────────────────────────────────


async def demo():
    """Demonstrate invoice processing."""

    print("=" * 60)
    print("Invoice Processor Example")
    print("=" * 60)

    # Sample invoice texts (in production, extract from PDF)
    sample_invoices = [
        """
        TAX INVOICE
        Innovative Music Distribution
        ABN: 12 345 678 901
        
        Invoice Number: INV-2026-0123
        Invoice Date: 20/03/2026
        Due Date: 19/04/2026
        
        Subtotal: $166.00
        GST (10%): $16.60
        TOTAL: $182.60
        """,
        """
        AMBERTECH PTY LTD
        TAX INVOICE #AMB-44521
        
        Date: 18-03-2026
        
        Audio Cable 3m x5    $125.00
        XLR Adapter x10      $89.50
        
        Subtotal: $214.50
        GST: $21.45
        Total: $235.95
        """,
        """
        Invoice from Unknown Supplier
        Inv: 99887
        Date: 2026-03-15
        
        Services rendered
        Amount Due: $500.00
        """,
    ]

    logger = SpreadsheetLogger()

    async with InvoiceExtractor() as extractor:
        for i, invoice_text in enumerate(sample_invoices, 1):
            print(f"\n📄 Processing Invoice {i}...")
            print("-" * 40)

            # Extract
            result = await extractor.extract(invoice_text)

            if result.status == InvoiceStatus.FAILED:
                print(f"❌ Extraction failed: {result.errors}")
                continue

            print(f"✅ Extracted: {result.data.vendor_name}")
            print(f"   Invoice #: {result.data.invoice_number}")
            print(f"   Date: {result.data.invoice_date}")
            print(f"   Total: ${result.data.total:.2f}")
            print(f"   Confidence: {result.confidence:.0%}")

            # Validate
            is_valid, errors = validate_invoice(result.data)
            if not is_valid:
                print(f"⚠️  Validation warnings: {errors}")

            # Log to spreadsheet
            logger.log_invoice(result.data)

    # Summary
    print("\n" + "=" * 60)
    print(f"✅ Processed {len(logger.logged_invoices)} invoices")
    total = sum(inv.total for inv in logger.logged_invoices)
    print(f"💰 Total value: ${total:.2f}")

    print("\nThis pattern can be extended for:")
    print("  • Email attachment extraction")
    print("  • Multiple vendor formats")
    print("  • Automatic payment scheduling")
    print("  • Expense categorization")
    print("  • Duplicate detection")


if __name__ == "__main__":
    asyncio.run(demo())
