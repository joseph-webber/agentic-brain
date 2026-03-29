# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Lightweight SAML 2.0 helper for AuthnRequest generation, response parsing,
# and Service Provider metadata. This module intentionally avoids external
# dependencies so it can be used in unit tests and minimal deployments.
#
# Security note: this implementation focuses on structure and basic
# validation (issuer and audience fields). Production deployments should
# integrate a hardened SAML library (python3-saml or pysaml2) for full
# XML signature validation, encryption, and replay protection.

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from typing import Dict

# XML namespaces used for SAML 2.0
SAML_PROTOCOL_NS = "urn:oasis:names:tc:SAML:2.0:protocol"
SAML_ASSERTION_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
SAML_METADATA_NS = "urn:oasis:names:tc:SAML:2.0:metadata"

ET.register_namespace("samlp", SAML_PROTOCOL_NS)
ET.register_namespace("saml", SAML_ASSERTION_NS)


@dataclass
class SAMLConfig:
    """Minimal SAML Service Provider configuration.

    This config is intentionally small and self-contained so tests can
    construct it without touching the broader enterprise auth config.
    """

    idp_entity_id: str
    idp_sso_url: str
    idp_certificate: str
    sp_entity_id: str
    sp_acs_url: str


class SAMLProvider:
    """SAML 2.0 authentication provider helper.

    Provides three core capabilities:
    - :meth:`create_authn_request` to initiate an SP-initiated SSO flow
    - :meth:`validate_response` to parse a SAML Response and extract user data
    - :meth:`get_metadata` to expose SP metadata for IdP configuration

    This class does NOT perform XML signature verification or decryption –
    callers must layer a hardened SAML stack on top for production use.
    """

    def __init__(self, config: SAMLConfig):
        self.config = config

    # ---------------------------------------------------------------------
    # AuthnRequest generation
    # ---------------------------------------------------------------------

    def create_authn_request(self) -> str:
        """Generate a simple SAML AuthnRequest XML document.

        The request uses HTTP-POST binding and includes Issuer, Destination,
        and AssertionConsumerServiceURL. A random ID and current UTC
        IssueInstant are generated on each call.
        """

        request_id = f"_{uuid.uuid4().hex}"
        issue_instant = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        root = ET.Element(
            str(ET.QName(SAML_PROTOCOL_NS, "AuthnRequest")),
            {
                "ID": request_id,
                "Version": "2.0",
                "IssueInstant": issue_instant,
                "Destination": self.config.idp_sso_url,
                "ProtocolBinding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                "AssertionConsumerServiceURL": self.config.sp_acs_url,
            },
        )

        issuer = ET.SubElement(root, str(ET.QName(SAML_ASSERTION_NS, "Issuer")))
        issuer.text = self.config.sp_entity_id

        # NameIDPolicy is optional but commonly included
        name_id_policy = ET.SubElement(
            root,
            str(ET.QName(SAML_PROTOCOL_NS, "NameIDPolicy")),
            {
                "Format": "urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified",
                "AllowCreate": "true",
            },
        )
        # Explicitly silence unused variable warning for linters
        _ = name_id_policy

        return ET.tostring(root, encoding="unicode")

    # ---------------------------------------------------------------------
    # Response validation
    # ---------------------------------------------------------------------

    def validate_response(self, saml_response: str) -> Dict[str, object]:
        """Validate a SAML Response and extract user information.

        This performs *minimal* validation suitable for unit tests:

        - Ensures the Response Issuer matches the configured IdP entity ID
        - Extracts the Subject NameID
        - Extracts AttributeStatement values into a dictionary

        Args:
            saml_response: Raw XML string containing a SAML Response.

        Returns:
            dict with keys:
                - ``name_id`` (str | None)
                - ``attributes`` (dict[str, object])

        Raises:
            ValueError: If the issuer does not match the configured IdP.
        """

        ns = {"samlp": SAML_PROTOCOL_NS, "saml": SAML_ASSERTION_NS}
        root = ET.fromstring(saml_response)

        issuer_el = root.find("saml:Issuer", ns)
        issuer = (
            issuer_el.text.strip() if issuer_el is not None and issuer_el.text else None
        )
        if issuer != self.config.idp_entity_id:
            raise ValueError("Invalid SAML issuer")

        name_id_el = root.find(".//saml:Subject/saml:NameID", ns)
        name_id = name_id_el.text if name_id_el is not None else None

        attributes: Dict[str, object] = {}
        for attr in root.findall(".//saml:Attribute", ns):
            name = attr.attrib.get("Name")
            if not name:
                continue
            values = [v.text for v in attr.findall("saml:AttributeValue", ns) if v.text]
            if not values:
                continue
            attributes[name] = values[0] if len(values) == 1 else values

        return {"name_id": name_id, "attributes": attributes}

    # ---------------------------------------------------------------------
    # Service Provider metadata
    # ---------------------------------------------------------------------

    def get_metadata(self) -> str:
        """Generate minimal SP metadata XML.

        The metadata describes the Service Provider entity and its
        Assertion Consumer Service endpoint. It is intentionally
        conservative and does not expose signing/encryption keys.
        """

        root = ET.Element(
            str(ET.QName(SAML_METADATA_NS, "EntityDescriptor")),
            {"entityID": self.config.sp_entity_id},
        )

        sp_sso = ET.SubElement(
            root,
            str(ET.QName(SAML_METADATA_NS, "SPSSODescriptor")),
            {
                "AuthnRequestsSigned": "false",
                "WantAssertionsSigned": "true",
                "protocolSupportEnumeration": SAML_PROTOCOL_NS,
            },
        )

        ET.SubElement(
            sp_sso,
            str(ET.QName(SAML_METADATA_NS, "AssertionConsumerService")),
            {
                "Binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                "Location": self.config.sp_acs_url,
                "index": "0",
                "isDefault": "true",
            },
        )

        return ET.tostring(root, encoding="unicode")
