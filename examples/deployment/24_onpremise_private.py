#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 24: On-Premise Private Deployment
==========================================

Fully air-gapped deployment for maximum security.
Uses ONLY local resources - no cloud APIs, no internet required.

This deployment pattern is essential for:
- Government agencies with classified data
- Defense contractors (ITAR/EAR compliance)
- Healthcare (HIPAA without BAA complexity)
- Financial institutions (data sovereignty)
- Research facilities (IP protection)

Architecture:
    ┌──────────────────────────────────────────────────┐
    │                 AIR-GAPPED NETWORK               │
    │  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
    │  │  Ollama  │  │  Neo4j   │  │  This Agent  │   │
    │  │ (Local)  │◄─┤ (Local)  │◄─┤   (Local)    │   │
    │  └──────────┘  └──────────┘  └──────────────┘   │
    │       │              │              │           │
    │       └──────────────┴──────────────┘           │
    │              All Local Network                   │
    └──────────────────────────────────────────────────┘
                        │
                        ╳  No Internet Connection
                        │

Hardware Requirements:
    - Minimum: 16GB RAM, 4 CPU cores
    - Recommended: 32GB RAM, 8 cores, GPU (M1-M4/CUDA/ROCm)
    - Storage: 20GB for models, varies for data

Supported Hardware Acceleration:
    - Apple Silicon: M1, M2, M3, M4 (Metal Performance Shaders)
    - NVIDIA: CUDA (RTX 20/30/40 series, datacenter GPUs)
    - AMD: ROCm (RX 6000/7000 series)
    - CPU: AVX2/AVX-512 acceleration

Models (pre-downloaded for air-gap):
    - llama3.1:8b (default, good balance)
    - llama3.2:3b (faster, less capable)
    - codellama:13b (code tasks)
    - mistral:7b (alternative)

Demo Scenario:
    IT Policy Assistant for secure government facility.
    Helps staff understand security policies, procedures,
    and compliance requirements - all without internet.

Usage:
    python examples/24_onpremise_private.py
    python examples/24_onpremise_private.py --demo
    python examples/24_onpremise_private.py --interactive
    python examples/24_onpremise_private.py --hardware-check

Requirements:
    pip install agentic-brain
    ollama pull llama3.1:8b  # Pre-download before air-gap
"""

import argparse
import asyncio
import json
import os
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# HARDWARE DETECTION
# ══════════════════════════════════════════════════════════════════════════════


class AcceleratorType(Enum):
    """Hardware acceleration types."""

    APPLE_SILICON = "apple_silicon"  # M1, M2, M3, M4
    NVIDIA_CUDA = "nvidia_cuda"  # NVIDIA GPUs
    AMD_ROCM = "amd_rocm"  # AMD GPUs
    CPU_ONLY = "cpu_only"  # No GPU acceleration


@dataclass
class HardwareProfile:
    """Detected hardware capabilities."""

    accelerator: AcceleratorType
    accelerator_name: str
    cpu_cores: int
    total_ram_gb: float
    gpu_memory_gb: Optional[float] = None
    recommended_model: str = "llama3.1:8b"
    max_context: int = 4096

    def to_dict(self) -> dict:
        return {
            "accelerator": self.accelerator.value,
            "accelerator_name": self.accelerator_name,
            "cpu_cores": self.cpu_cores,
            "total_ram_gb": self.total_ram_gb,
            "gpu_memory_gb": self.gpu_memory_gb,
            "recommended_model": self.recommended_model,
            "max_context": self.max_context,
        }


def detect_hardware() -> HardwareProfile:
    """
    Detect available hardware acceleration.

    Checks for Apple Silicon, NVIDIA CUDA, AMD ROCm in order.
    Falls back to CPU if no acceleration found.
    """
    cpu_cores = os.cpu_count() or 4

    # Get total RAM
    try:
        if platform.system() == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True
            )
            total_ram_gb = int(result.stdout.strip()) / (1024**3)
        elif platform.system() == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        total_ram_gb = int(line.split()[1]) / (1024**2)
                        break
        else:
            total_ram_gb = 16.0  # Default assumption
    except Exception:
        total_ram_gb = 16.0

    # Check Apple Silicon (M1/M2/M3/M4)
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
            )
            cpu_brand = result.stdout.strip()

            # Detect specific chip
            chip_name = "Apple Silicon"
            gpu_memory = None
            recommended = "llama3.1:8b"
            max_ctx = 4096

            if "M4" in cpu_brand:
                chip_name = "Apple M4"
                gpu_memory = total_ram_gb * 0.75  # Unified memory
                recommended = "llama3.1:8b"
                max_ctx = 8192
            elif "M3" in cpu_brand:
                chip_name = "Apple M3"
                gpu_memory = total_ram_gb * 0.75
                recommended = "llama3.1:8b"
                max_ctx = 8192
            elif "M2" in cpu_brand:
                chip_name = "Apple M2"
                gpu_memory = total_ram_gb * 0.7
                recommended = "llama3.1:8b"
                max_ctx = 4096
            elif "M1" in cpu_brand:
                chip_name = "Apple M1"
                gpu_memory = total_ram_gb * 0.6
                recommended = "llama3.2:3b" if total_ram_gb < 16 else "llama3.1:8b"
                max_ctx = 4096

            return HardwareProfile(
                accelerator=AcceleratorType.APPLE_SILICON,
                accelerator_name=chip_name,
                cpu_cores=cpu_cores,
                total_ram_gb=total_ram_gb,
                gpu_memory_gb=gpu_memory,
                recommended_model=recommended,
                max_context=max_ctx,
            )
        except Exception:
            pass

    # Check NVIDIA CUDA
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            gpu_name = lines[0].split(",")[0].strip()
            gpu_mem = lines[0].split(",")[1].strip()
            gpu_memory_gb = float(gpu_mem.replace(" MiB", "")) / 1024

            # Recommend model based on VRAM
            if gpu_memory_gb >= 24:
                recommended = "codellama:34b"
                max_ctx = 8192
            elif gpu_memory_gb >= 12:
                recommended = "llama3.1:8b"
                max_ctx = 4096
            else:
                recommended = "llama3.2:3b"
                max_ctx = 2048

            return HardwareProfile(
                accelerator=AcceleratorType.NVIDIA_CUDA,
                accelerator_name=f"NVIDIA {gpu_name}",
                cpu_cores=cpu_cores,
                total_ram_gb=total_ram_gb,
                gpu_memory_gb=gpu_memory_gb,
                recommended_model=recommended,
                max_context=max_ctx,
            )
    except FileNotFoundError:
        pass

    # Check AMD ROCm
    try:
        result = subprocess.run(
            ["rocm-smi", "--showproductname"], capture_output=True, text=True
        )
        if result.returncode == 0:
            gpu_name = "AMD GPU"
            for line in result.stdout.split("\n"):
                if "Card series" in line:
                    gpu_name = line.split(":")[-1].strip()
                    break

            return HardwareProfile(
                accelerator=AcceleratorType.AMD_ROCM,
                accelerator_name=gpu_name,
                cpu_cores=cpu_cores,
                total_ram_gb=total_ram_gb,
                gpu_memory_gb=None,  # ROCm memory detection is complex
                recommended_model="llama3.1:8b",
                max_context=4096,
            )
    except FileNotFoundError:
        pass

    # CPU only fallback
    recommended = "llama3.2:3b" if total_ram_gb < 16 else "llama3.1:8b"
    return HardwareProfile(
        accelerator=AcceleratorType.CPU_ONLY,
        accelerator_name=f"{cpu_cores}-core CPU",
        cpu_cores=cpu_cores,
        total_ram_gb=total_ram_gb,
        recommended_model=recommended,
        max_context=2048,
    )


# ══════════════════════════════════════════════════════════════════════════════
# LOCAL-ONLY CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class OnPremiseConfig:
    """
    Configuration for air-gapped deployment.

    All settings point to local resources only.
    No cloud endpoints, no API keys needed.
    """

    # LLM Configuration (Ollama)
    ollama_host: str = "http://localhost:11434"
    model_name: str = "llama3.1:8b"
    model_fallback: str = "llama3.2:3b"

    # Memory Configuration
    memory_type: str = "neo4j"  # "neo4j" or "inmemory"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "Brain2026"

    # Security Settings
    audit_logging: bool = True
    log_path: str = "/var/log/ai-assistant"
    data_retention_days: int = 90

    # Performance
    max_concurrent_users: int = 10
    request_timeout_seconds: int = 120

    # Hardware (auto-detected)
    hardware: Optional[HardwareProfile] = None

    def validate(self) -> list[str]:
        """Validate configuration for air-gap deployment."""
        issues = []

        # Check for any cloud references
        cloud_indicators = [
            "openai.com",
            "anthropic.com",
            "api.openai",
            "googleapis.com",
            "azure.com",
            "amazonaws.com",
        ]

        config_str = f"{self.ollama_host} {self.neo4j_uri}"
        for indicator in cloud_indicators:
            if indicator in config_str.lower():
                issues.append(f"Cloud reference detected: {indicator}")

        # Validate Ollama is local
        if not ("localhost" in self.ollama_host or "127.0.0.1" in self.ollama_host):
            issues.append(f"Ollama host must be local: {self.ollama_host}")

        return issues


# ══════════════════════════════════════════════════════════════════════════════
# IN-MEMORY STORAGE (No Database Required)
# ══════════════════════════════════════════════════════════════════════════════


class InMemoryStore:
    """
    Simple in-memory storage for smallest footprint deployments.

    Use when Neo4j is not available or for testing.
    Data is lost on restart unless explicitly exported.
    """

    def __init__(self):
        self.conversations: list[dict] = []
        self.policies: dict[str, dict] = {}
        self.audit_log: list[dict] = []

    def add_message(self, user_id: str, role: str, content: str):
        """Store a conversation message."""
        self.conversations.append(
            {
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "role": role,
                "content": content,
            }
        )

    def get_recent_context(self, user_id: str, limit: int = 10) -> list[dict]:
        """Get recent conversation for a user."""
        user_msgs = [m for m in self.conversations if m["user_id"] == user_id]
        return user_msgs[-limit:]

    def log_audit(self, action: str, user_id: str, details: str):
        """Log an audit event."""
        self.audit_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "user_id": user_id,
                "details": details,
            }
        )

    def export_json(self) -> str:
        """Export all data as JSON for backup."""
        return json.dumps(
            {
                "conversations": self.conversations,
                "policies": self.policies,
                "audit_log": self.audit_log,
            },
            indent=2,
        )


# ══════════════════════════════════════════════════════════════════════════════
# IT POLICY KNOWLEDGE BASE
# ══════════════════════════════════════════════════════════════════════════════


class SecurityClassification(Enum):
    """Document security classifications."""

    UNCLASSIFIED = "unclassified"
    CONTROLLED = "controlled"
    CONFIDENTIAL = "confidential"
    SECRET = "secret"


@dataclass
class PolicyDocument:
    """An IT security policy document."""

    policy_id: str
    title: str
    classification: SecurityClassification
    content: str
    effective_date: str
    review_date: str
    owner: str
    keywords: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Return brief summary for search results."""
        return f"[{self.policy_id}] {self.title} ({self.classification.value})"


class PolicyKnowledgeBase:
    """
    Local-only IT policy knowledge base.

    All policies stored locally, no cloud sync.
    Designed for secure/classified environments.
    """

    def __init__(self):
        # Sample IT policies for secure environment
        self.policies: dict[str, PolicyDocument] = {
            "SEC-001": PolicyDocument(
                policy_id="SEC-001",
                title="Password and Authentication Policy",
                classification=SecurityClassification.CONTROLLED,
                content="""
                PASSWORD REQUIREMENTS:
                - Minimum 14 characters
                - Must include: uppercase, lowercase, numbers, special characters
                - Cannot reuse last 24 passwords
                - Maximum age: 90 days
                - Account lockout after 5 failed attempts

                MULTI-FACTOR AUTHENTICATION:
                - Required for all systems
                - Hardware tokens preferred (YubiKey, PIV card)
                - No SMS-based MFA (security risk)
                - Biometrics allowed as second factor

                SERVICE ACCOUNTS:
                - 32+ character passwords
                - Rotate quarterly
                - No interactive login allowed
                """,
                effective_date="2024-01-01",
                review_date="2025-01-01",
                owner="CISO",
                keywords=["password", "mfa", "authentication", "login", "security"],
            ),
            "SEC-002": PolicyDocument(
                policy_id="SEC-002",
                title="USB and Removable Media Policy",
                classification=SecurityClassification.CONFIDENTIAL,
                content="""
                AUTHORIZED DEVICES:
                - Only organization-issued encrypted USB drives
                - Encrypted external hard drives (FIPS 140-2)
                - Smart cards for authentication

                PROHIBITED:
                - Personal USB drives
                - Unencrypted storage devices
                - USB devices from unknown sources
                - Charging personal devices via USB

                PROCEDURES:
                1. All USB devices must be registered with IT Security
                2. Scan all incoming media with approved antivirus
                3. Report any lost/stolen devices within 1 hour
                4. Wipe devices before disposal (DoD 5220.22-M)

                EXCEPTIONS:
                - Require CISO approval in writing
                - Valid for maximum 30 days
                - Must be logged in exception register
                """,
                effective_date="2024-01-01",
                review_date="2025-01-01",
                owner="IT Security",
                keywords=["usb", "removable", "media", "storage", "drive"],
            ),
            "SEC-003": PolicyDocument(
                policy_id="SEC-003",
                title="Network Security Policy",
                classification=SecurityClassification.CONTROLLED,
                content="""
                NETWORK SEGMENTATION:
                - Classified network: Air-gapped, no internet
                - Corporate network: Filtered internet
                - Guest network: Isolated, internet only

                WIRELESS:
                - WPA3-Enterprise required
                - No WPA2-Personal
                - Hidden SSIDs for sensitive networks
                - Regular rogue AP scanning

                FIREWALLS:
                - Default deny all
                - Whitelist approach only
                - Log all blocked traffic
                - Review logs weekly

                VPN:
                - Required for all remote access
                - Always-on VPN for laptops
                - Split tunneling prohibited
                """,
                effective_date="2024-01-01",
                review_date="2025-01-01",
                owner="Network Security",
                keywords=["network", "firewall", "vpn", "wireless", "wifi"],
            ),
            "SEC-004": PolicyDocument(
                policy_id="SEC-004",
                title="Workstation Security Standards",
                classification=SecurityClassification.CONTROLLED,
                content="""
                HARDWARE STANDARDS:
                - Only approved monitor models (no built-in cameras on classified)
                - Approved keyboards and mice only
                - Cable locks required for laptops
                - USB port control enabled

                SOFTWARE REQUIREMENTS:
                - Endpoint Detection & Response (EDR) agent
                - Full disk encryption (BitLocker/FileVault)
                - Automatic updates enabled
                - Application allowlisting

                PERIPHERALS:
                - USB hubs must be approved models
                - External monitors require IT approval
                - Webcam covers when not in use
                - No personal Bluetooth devices

                PHYSICAL SECURITY:
                - Lock screen after 5 minutes
                - Clean desk policy
                - Secure storage for documents
                - Privacy screens in public areas
                """,
                effective_date="2024-01-01",
                review_date="2025-01-01",
                owner="IT Operations",
                keywords=["workstation", "laptop", "computer", "desktop", "hardware"],
            ),
            "SEC-005": PolicyDocument(
                policy_id="SEC-005",
                title="Data Classification and Handling",
                classification=SecurityClassification.CONTROLLED,
                content="""
                CLASSIFICATION LEVELS:
                - UNCLASSIFIED: Public information
                - CONTROLLED: Internal use only
                - CONFIDENTIAL: Limited distribution
                - SECRET: Need-to-know basis

                HANDLING REQUIREMENTS:

                UNCLASSIFIED:
                - Standard workstations
                - Email allowed
                - Cloud storage permitted

                CONTROLLED:
                - Encrypted storage
                - No personal email
                - Approved cloud only

                CONFIDENTIAL:
                - Dedicated secure systems
                - No external transmission
                - Logged access only

                SECRET:
                - Air-gapped systems only
                - Two-person integrity
                - Physical security required
                """,
                effective_date="2024-01-01",
                review_date="2025-01-01",
                owner="Security Classification Officer",
                keywords=[
                    "classification",
                    "handling",
                    "data",
                    "secret",
                    "confidential",
                ],
            ),
        }

    def search(self, query: str) -> list[PolicyDocument]:
        """Search policies by keyword."""
        query_lower = query.lower()
        results = []

        for policy in self.policies.values():
            # Check keywords
            if any(kw in query_lower for kw in policy.keywords):
                results.append(policy)
                continue

            # Check title and content
            if (
                query_lower in policy.title.lower()
                or query_lower in policy.content.lower()
            ):
                results.append(policy)

        return results

    def get_policy(self, policy_id: str) -> Optional[PolicyDocument]:
        """Get specific policy by ID."""
        return self.policies.get(policy_id)

    def list_all(self) -> list[str]:
        """List all policy IDs and titles."""
        return [f"{p.policy_id}: {p.title}" for p in self.policies.values()]


# ══════════════════════════════════════════════════════════════════════════════
# ON-PREMISE POLICY ASSISTANT
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a secure IT Policy Assistant for a classified government facility.

CRITICAL RULES:
- Never reference external websites or cloud services
- All information comes from local policy documents only
- Log all queries for audit compliance
- If unsure, recommend consulting the Security Officer

You can help with:
1. Policy lookups - "What's our password policy?"
2. Compliance questions - "Can I use a personal USB drive?"
3. Procedure guidance - "How do I report a lost device?"
4. Security clarification - "What classification is this?"

Current user clearance: {clearance}
Session ID: {session_id}

Available policies: {policy_list}

Always cite policy IDs when answering (e.g., "Per SEC-001, passwords must be...").

Respond with JSON:
{
    "answer": "Your response citing relevant policies",
    "policies_cited": ["SEC-001", "SEC-002"],
    "requires_followup": false,
    "security_note": "Any security concerns"
}
"""


class OnPremisePolicyAssistant:
    """
    Air-gapped IT policy assistant.

    Runs entirely on local resources:
    - Ollama for LLM
    - Local Neo4j or in-memory storage
    - No network calls to external services
    """

    def __init__(self, config: OnPremiseConfig):
        self.config = config
        self.kb = PolicyKnowledgeBase()
        self.store = InMemoryStore()
        self.hardware = config.hardware or detect_hardware()

        # Pre-load policies into store
        for pid, policy in self.kb.policies.items():
            self.store.policies[pid] = {
                "id": policy.policy_id,
                "title": policy.title,
                "classification": policy.classification.value,
            }

    async def query_local_llm(self, prompt: str) -> str:
        """
        Query the local Ollama instance.

        In production, use agentic-brain's Ollama integration.
        This is a simplified demonstration.
        """
        # Simulated response for demo
        # In production: use agentic_brain.LLMRouter with ollama backend
        return f"[Local LLM Response - {self.config.model_name}]"

    async def process_query(
        self, query: str, user_id: str = "anonymous", clearance: str = "CONTROLLED"
    ) -> dict:
        """
        Process a policy query securely.

        1. Log the query for audit
        2. Search local knowledge base
        3. Generate response via local LLM
        4. Return with policy citations
        """
        # Audit log
        self.store.log_audit("QUERY", user_id, query[:100])
        self.store.add_message(user_id, "user", query)

        # Search knowledge base
        relevant_policies = self.kb.search(query)

        # Build response based on found policies
        if not relevant_policies:
            response = {
                "answer": "I couldn't find specific policies matching your query. "
                "Please consult the Security Officer for guidance.",
                "policies_cited": [],
                "requires_followup": True,
                "security_note": "Query logged for review",
            }
        else:
            # Format policy information
            policy_info = []
            for p in relevant_policies[:3]:  # Top 3 relevant
                policy_info.append(
                    f"\n[{p.policy_id}] {p.title}:\n{p.content[:500]}..."
                )

            response = {
                "answer": self._generate_answer(query, relevant_policies),
                "policies_cited": [p.policy_id for p in relevant_policies[:3]],
                "requires_followup": False,
                "security_note": None,
            }

        # Store response
        self.store.add_message(user_id, "assistant", json.dumps(response))

        return response

    def _generate_answer(self, query: str, policies: list[PolicyDocument]) -> str:
        """Generate human-readable answer from policies."""
        query_lower = query.lower()

        # Password questions
        if any(kw in query_lower for kw in ["password", "login", "mfa"]):
            sec001 = self.kb.get_policy("SEC-001")
            if sec001:
                return f"Per {sec001.policy_id} ({sec001.title}):\n{sec001.content}"

        # USB questions
        if any(kw in query_lower for kw in ["usb", "drive", "removable"]):
            sec002 = self.kb.get_policy("SEC-002")
            if sec002:
                return f"Per {sec002.policy_id} ({sec002.title}):\n{sec002.content}"

        # Network questions
        if any(kw in query_lower for kw in ["network", "wifi", "vpn"]):
            sec003 = self.kb.get_policy("SEC-003")
            if sec003:
                return f"Per {sec003.policy_id} ({sec003.title}):\n{sec003.content}"

        # Workstation questions
        if any(
            kw in query_lower
            for kw in ["workstation", "laptop", "computer", "monitor", "keyboard"]
        ):
            sec004 = self.kb.get_policy("SEC-004")
            if sec004:
                return f"Per {sec004.policy_id} ({sec004.title}):\n{sec004.content}"

        # Default: show all relevant
        answers = []
        for p in policies[:2]:
            answers.append(f"**{p.policy_id}: {p.title}**\n{p.content[:300]}...")
        return "\n\n".join(answers)

    def get_audit_log(self) -> list[dict]:
        """Get audit log for compliance review."""
        return self.store.audit_log

    def export_state(self) -> str:
        """Export state for backup (to encrypted local storage)."""
        return self.store.export_json()


# ══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT VALIDATOR
# ══════════════════════════════════════════════════════════════════════════════


def validate_air_gap() -> dict:
    """
    Validate that deployment is truly air-gapped.

    Checks:
    - No cloud API keys configured
    - Ollama is local
    - No internet DNS resolution
    - All services are local
    """
    issues = []
    warnings = []

    # Check for cloud API keys in environment
    cloud_keys = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "AZURE_OPENAI_KEY",
        "HUGGINGFACE_TOKEN",
    ]
    for key in cloud_keys:
        if os.environ.get(key):
            issues.append(f"Cloud API key found: {key} (remove for air-gap)")

    # Check Ollama is running locally
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            warnings.append("Ollama not responding on localhost:11434")
    except Exception as e:
        warnings.append(f"Could not check Ollama: {e}")

    # Check for internet connectivity (should fail in air-gap)
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "1", "8.8.8.8"], capture_output=True, timeout=3
        )
        if result.returncode == 0:
            warnings.append("Internet connectivity detected (not air-gapped)")
    except subprocess.TimeoutExpired:
        pass  # Good - no internet
    except FileNotFoundError:
        pass  # Windows or no ping

    return {
        "is_valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def run_demo():
    """Run demonstration of on-premise policy assistant."""
    print("=" * 70)
    print("🔒 ON-PREMISE PRIVATE DEPLOYMENT")
    print("   IT Security Policy Assistant (Air-Gapped)")
    print("=" * 70)
    print()

    # Hardware detection
    print("📍 HARDWARE DETECTION")
    print("-" * 40)
    hardware = detect_hardware()
    print(f"  Accelerator: {hardware.accelerator_name}")
    print(f"  Type: {hardware.accelerator.value}")
    print(f"  CPU Cores: {hardware.cpu_cores}")
    print(f"  RAM: {hardware.total_ram_gb:.1f} GB")
    if hardware.gpu_memory_gb:
        print(f"  GPU Memory: {hardware.gpu_memory_gb:.1f} GB")
    print(f"  Recommended Model: {hardware.recommended_model}")
    print(f"  Max Context: {hardware.max_context}")
    print()

    # Configuration
    config = OnPremiseConfig(
        model_name=hardware.recommended_model,
        hardware=hardware,
    )

    # Validate configuration
    print("🔍 CONFIGURATION VALIDATION")
    print("-" * 40)
    issues = config.validate()
    if issues:
        for issue in issues:
            print(f"  ❌ {issue}")
    else:
        print("  ✅ Configuration valid for air-gap deployment")
    print()

    # Air-gap validation
    print("🛡️ AIR-GAP VALIDATION")
    print("-" * 40)
    validation = validate_air_gap()
    if validation["is_valid"]:
        print("  ✅ Deployment appears air-gapped")
    for issue in validation["issues"]:
        print(f"  ❌ {issue}")
    for warning in validation["warnings"]:
        print(f"  ⚠️  {warning}")
    print()

    # Initialize assistant
    assistant = OnPremisePolicyAssistant(config)

    # Demo queries
    print("💬 DEMO QUERIES")
    print("-" * 40)

    demo_queries = [
        "What's our password policy?",
        "Can I use my personal USB drive?",
        "What are the approved monitors and keyboards?",
        "How do I connect to the VPN?",
        "What's the classification for this document?",
    ]

    for query in demo_queries:
        print(f"\n👤 User: {query}")
        response = await assistant.process_query(query, user_id="demo_user")
        print(f"🤖 Assistant: {response['answer'][:300]}...")
        if response["policies_cited"]:
            print(f"   📋 Cited: {', '.join(response['policies_cited'])}")
        print()

    # Show audit log
    print("\n📊 AUDIT LOG")
    print("-" * 40)
    for entry in assistant.get_audit_log():
        print(f"  [{entry['timestamp']}] {entry['action']}: {entry['details']}")


async def run_interactive():
    """Run interactive policy assistant."""
    print("=" * 70)
    print("🔒 ON-PREMISE POLICY ASSISTANT - INTERACTIVE MODE")
    print("=" * 70)
    print()

    hardware = detect_hardware()
    config = OnPremiseConfig(
        model_name=hardware.recommended_model,
        hardware=hardware,
    )
    assistant = OnPremisePolicyAssistant(config)

    print(f"Using: {hardware.accelerator_name} with {config.model_name}")
    print("Commands: 'quit', 'policies', 'audit', 'export'")
    print()

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() == "quit":
                print("Session ended. All queries logged for audit.")
                break

            if user_input.lower() == "policies":
                print("\nAvailable Policies:")
                for p in assistant.kb.list_all():
                    print(f"  • {p}")
                continue

            if user_input.lower() == "audit":
                print("\nAudit Log:")
                for entry in assistant.get_audit_log():
                    print(f"  {entry}")
                continue

            if user_input.lower() == "export":
                export = assistant.export_state()
                print(f"\nState exported ({len(export)} bytes)")
                continue

            response = await assistant.process_query(user_input)
            print(f"\n🔒 {response['answer'][:500]}")
            if response["policies_cited"]:
                print(f"\n📋 Policies: {', '.join(response['policies_cited'])}")
            print()

        except KeyboardInterrupt:
            print("\nSession terminated.")
            break


def show_hardware_check():
    """Display detailed hardware information."""
    print("=" * 70)
    print("🖥️ HARDWARE CAPABILITY CHECK")
    print("=" * 70)
    print()

    hardware = detect_hardware()

    print("DETECTED HARDWARE:")
    print(json.dumps(hardware.to_dict(), indent=2))
    print()

    print("RECOMMENDATIONS:")
    print(f"  • Model: {hardware.recommended_model}")
    print(f"  • Context Window: {hardware.max_context} tokens")

    if hardware.accelerator == AcceleratorType.APPLE_SILICON:
        print("  • Ollama will use Metal Performance Shaders")
        print("  • Expected throughput: 20-40 tokens/sec")
    elif hardware.accelerator == AcceleratorType.NVIDIA_CUDA:
        print("  • Ollama will use CUDA acceleration")
        print(f"  • VRAM: {hardware.gpu_memory_gb:.1f} GB")
    elif hardware.accelerator == AcceleratorType.AMD_ROCM:
        print("  • Ollama will use ROCm acceleration")
    else:
        print("  • CPU-only mode (slower)")
        print("  • Consider adding GPU for better performance")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="On-Premise Private Deployment Example"
    )
    parser.add_argument("--demo", action="store_true", help="Run demonstration mode")
    parser.add_argument(
        "--interactive", action="store_true", help="Run interactive mode"
    )
    parser.add_argument(
        "--hardware-check", action="store_true", help="Show hardware capabilities"
    )

    args = parser.parse_args()

    if args.hardware_check:
        show_hardware_check()
    elif args.interactive:
        asyncio.run(run_interactive())
    else:
        # Default to demo mode
        asyncio.run(run_demo())
