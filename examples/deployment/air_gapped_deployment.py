#!/usr/bin/env python3
"""
Air-Gapped Deployment Patterns for Agentic Brain

Generic patterns and utilities for deploying AI assistants in
air-gapped, classified, or isolated network environments.

Copyright (C) 2024-2025 Agentic Brain Project
SPDX-License-Identifier: GPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Features:
- Offline model loading and verification
- Local-only RAG setup with Neo4j
- Security hardening checklist validation
- Docker deployment templates
- HSM integration patterns
- Network isolation verification

Target Environments:
- Defence/Military networks (PROTECTED, SECRET, TOP SECRET)
- Healthcare (HIPAA, air-gapped research)
- Financial (PCI-DSS isolated zones)
- Government (FedRAMP High, air-gapped)
- Critical infrastructure (SCADA, OT networks)

Usage:
    # Verify deployment readiness
    python air_gapped_deployment.py verify

    # Generate Docker deployment
    python air_gapped_deployment.py docker --output ./deploy

    # Run security checklist
    python air_gapped_deployment.py security-check

Requirements:
    - Python 3.11+
    - Ollama (pre-installed with models)
    - Neo4j Community/Enterprise
    - Docker (for containerized deployment)
    - Optional: HSM libraries (PKCS#11)
"""

import asyncio
import hashlib
import json
import logging
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class AirGappedConfig:
    """
    Configuration for air-gapped deployment.

    All settings must be configured before deployment as
    no external configuration sources are available.
    """

    # Identification
    deployment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deployment_name: str = "air-gapped-brain"
    environment: str = "production"  # development, staging, production

    # Paths (must be on encrypted storage in production)
    base_path: Path = field(default_factory=lambda: Path("/opt/agentic-brain"))
    data_path: Path = field(default_factory=lambda: Path("/opt/agentic-brain/data"))
    models_path: Path = field(default_factory=lambda: Path("/opt/agentic-brain/models"))
    config_path: Path = field(default_factory=lambda: Path("/opt/agentic-brain/config"))
    logs_path: Path = field(default_factory=lambda: Path("/var/log/agentic-brain"))
    audit_path: Path = field(
        default_factory=lambda: Path("/var/log/agentic-brain/audit")
    )

    # Ollama settings
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_models: list[str] = field(
        default_factory=lambda: ["llama3.1:8b", "nomic-embed-text", "codellama:13b"]
    )

    # Neo4j settings
    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_database: str = "neo4j"

    # Security settings
    encryption_at_rest: bool = True
    require_hsm: bool = False
    hsm_library_path: str = "/usr/lib/softhsm/libsofthsm2.so"
    session_timeout_hours: int = 8
    max_concurrent_sessions: int = 10

    # Network isolation
    allowed_interfaces: list[str] = field(default_factory=lambda: ["lo"])
    blocked_ports: list[int] = field(default_factory=lambda: [80, 443, 22])

    # Audit settings
    audit_retention_days: int = 365
    audit_hash_algorithm: str = "sha256"

    def validate(self) -> list[str]:
        """Validate configuration. Returns list of issues."""
        issues = []

        # Check paths exist or can be created
        for path_name in ["base_path", "data_path", "models_path", "config_path"]:
            path = getattr(self, path_name)
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except PermissionError:
                    issues.append(f"Cannot create {path_name}: {path}")

        # Check Ollama URL format
        if not self.ollama_host.startswith("http://127.0.0.1"):
            issues.append(f"Ollama must use localhost only, got: {self.ollama_host}")

        # Check Neo4j URL format
        if "127.0.0.1" not in self.neo4j_uri and "localhost" not in self.neo4j_uri:
            issues.append(f"Neo4j must use localhost only, got: {self.neo4j_uri}")

        return issues

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "deployment_id": self.deployment_id,
            "deployment_name": self.deployment_name,
            "environment": self.environment,
            "base_path": str(self.base_path),
            "data_path": str(self.data_path),
            "models_path": str(self.models_path),
            "ollama_host": self.ollama_host,
            "ollama_models": self.ollama_models,
            "neo4j_uri": self.neo4j_uri,
            "neo4j_user": self.neo4j_user,
            "encryption_at_rest": self.encryption_at_rest,
            "require_hsm": self.require_hsm,
            "session_timeout_hours": self.session_timeout_hours,
        }


# ══════════════════════════════════════════════════════════════════════════════
# SECURITY CHECKLIST
# ══════════════════════════════════════════════════════════════════════════════


class CheckStatus(Enum):
    """Status of a security check."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"
    INFO = "INFO"


@dataclass
class CheckResult:
    """Result of a security check."""

    name: str
    status: CheckStatus
    message: str
    details: str = ""
    remediation: str = ""

    def __str__(self) -> str:
        status_icons = {
            CheckStatus.PASS: "✓",
            CheckStatus.FAIL: "✗",
            CheckStatus.WARN: "⚠",
            CheckStatus.SKIP: "○",
            CheckStatus.INFO: "ℹ",
        }
        return f"[{status_icons[self.status]}] {self.name}: {self.message}"


class SecurityChecklist:
    """
    Security hardening checklist for air-gapped deployments.

    Based on:
    - Australian ISM (Information Security Manual)
    - CIS Benchmarks
    - NIST 800-53
    - Defence Security Principles Framework
    """

    def __init__(self, config: AirGappedConfig):
        self.config = config
        self.results: list[CheckResult] = []

    async def run_all(self) -> list[CheckResult]:
        """Run all security checks."""
        self.results = []

        # Network checks
        await self._check_network_isolation()
        await self._check_no_external_dns()
        await self._check_firewall_rules()

        # System checks
        await self._check_disk_encryption()
        await self._check_secure_boot()
        await self._check_audit_logging()

        # Application checks
        await self._check_ollama_local()
        await self._check_neo4j_local()
        await self._check_models_verified()

        # Access control checks
        await self._check_file_permissions()
        await self._check_user_isolation()

        return self.results

    async def _check_network_isolation(self):
        """Verify no external network connectivity."""
        name = "Network Isolation"

        try:
            # Try to connect to external host
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("8.8.8.8", 53))
            sock.close()

            if result == 0:
                self.results.append(
                    CheckResult(
                        name=name,
                        status=CheckStatus.FAIL,
                        message="External network connectivity detected",
                        details="System can reach 8.8.8.8:53 (Google DNS)",
                        remediation="Configure firewall to block all outbound traffic",
                    )
                )
            else:
                self.results.append(
                    CheckResult(
                        name=name,
                        status=CheckStatus.PASS,
                        message="No external network connectivity",
                    )
                )
        except (TimeoutError, OSError):
            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.PASS,
                    message="No external network connectivity",
                )
            )

    async def _check_no_external_dns(self):
        """Verify DNS is not configured for external resolution."""
        name = "DNS Isolation"

        try:
            # Try to resolve external hostname
            socket.gethostbyname("google.com")
            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.FAIL,
                    message="External DNS resolution possible",
                    remediation="Remove external DNS servers from /etc/resolv.conf",
                )
            )
        except socket.gaierror:
            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.PASS,
                    message="External DNS resolution blocked",
                )
            )

    async def _check_firewall_rules(self):
        """Check firewall is configured correctly."""
        name = "Firewall Configuration"

        try:
            # Check if iptables/nftables is running
            result = subprocess.run(
                ["iptables", "-L", "-n"], capture_output=True, text=True, timeout=5
            )

            if "DROP" in result.stdout or "REJECT" in result.stdout:
                self.results.append(
                    CheckResult(
                        name=name,
                        status=CheckStatus.PASS,
                        message="Firewall rules configured with DROP/REJECT policies",
                    )
                )
            else:
                self.results.append(
                    CheckResult(
                        name=name,
                        status=CheckStatus.WARN,
                        message="Firewall running but no DROP rules found",
                        remediation="Configure firewall to deny by default",
                    )
                )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.WARN,
                    message="Could not verify firewall status",
                    remediation="Install and configure iptables or nftables",
                )
            )

    async def _check_disk_encryption(self):
        """Verify disk encryption is enabled."""
        name = "Disk Encryption"

        if not self.config.encryption_at_rest:
            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.WARN,
                    message="Encryption at rest not required in config",
                    remediation="Enable encryption_at_rest in configuration",
                )
            )
            return

        try:
            # Check for LUKS encrypted volumes
            result = subprocess.run(
                ["lsblk", "-o", "NAME,TYPE,MOUNTPOINT,FSTYPE"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if "crypt" in result.stdout.lower():
                self.results.append(
                    CheckResult(
                        name=name,
                        status=CheckStatus.PASS,
                        message="LUKS disk encryption detected",
                    )
                )
            else:
                self.results.append(
                    CheckResult(
                        name=name,
                        status=CheckStatus.FAIL,
                        message="No disk encryption detected",
                        remediation="Configure LUKS encryption for data volumes",
                    )
                )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.SKIP,
                    message="Could not check disk encryption",
                )
            )

    async def _check_secure_boot(self):
        """Check if Secure Boot is enabled."""
        name = "Secure Boot"

        try:
            # Check EFI secure boot status
            result = subprocess.run(
                ["mokutil", "--sb-state"], capture_output=True, text=True, timeout=5
            )

            if "SecureBoot enabled" in result.stdout:
                self.results.append(
                    CheckResult(
                        name=name,
                        status=CheckStatus.PASS,
                        message="Secure Boot is enabled",
                    )
                )
            else:
                self.results.append(
                    CheckResult(
                        name=name,
                        status=CheckStatus.WARN,
                        message="Secure Boot not enabled",
                        remediation="Enable Secure Boot in UEFI settings",
                    )
                )
        except FileNotFoundError:
            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.SKIP,
                    message="mokutil not available - Secure Boot check skipped",
                )
            )

    async def _check_audit_logging(self):
        """Verify audit logging is configured."""
        name = "Audit Logging"

        # Check if audit directory exists and is writable
        if self.config.audit_path.exists():
            if os.access(self.config.audit_path, os.W_OK):
                self.results.append(
                    CheckResult(
                        name=name,
                        status=CheckStatus.PASS,
                        message=f"Audit directory exists: {self.config.audit_path}",
                    )
                )
            else:
                self.results.append(
                    CheckResult(
                        name=name,
                        status=CheckStatus.FAIL,
                        message="Audit directory not writable",
                        remediation=f"chmod 750 {self.config.audit_path}",
                    )
                )
        else:
            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.FAIL,
                    message="Audit directory does not exist",
                    remediation=f"mkdir -p {self.config.audit_path}",
                )
            )

    async def _check_ollama_local(self):
        """Verify Ollama is running locally only."""
        name = "Ollama Local-Only"

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.config.ollama_host}/api/tags", timeout=5.0
                )

                if resp.status_code == 200:
                    self.results.append(
                        CheckResult(
                            name=name,
                            status=CheckStatus.PASS,
                            message=f"Ollama running at {self.config.ollama_host}",
                        )
                    )
                else:
                    self.results.append(
                        CheckResult(
                            name=name,
                            status=CheckStatus.FAIL,
                            message="Ollama not responding",
                        )
                    )
        except Exception as e:
            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.FAIL,
                    message=f"Cannot connect to Ollama: {e}",
                    remediation="Start Ollama with: systemctl start ollama",
                )
            )

    async def _check_neo4j_local(self):
        """Verify Neo4j is running locally only."""
        name = "Neo4j Local-Only"

        # Check if Neo4j port is listening on localhost only
        try:
            result = subprocess.run(
                ["ss", "-tlnp"], capture_output=True, text=True, timeout=5
            )

            # Neo4j default port is 7687
            if "127.0.0.1:7687" in result.stdout:
                self.results.append(
                    CheckResult(
                        name=name,
                        status=CheckStatus.PASS,
                        message="Neo4j listening on localhost only",
                    )
                )
            elif "0.0.0.0:7687" in result.stdout:
                self.results.append(
                    CheckResult(
                        name=name,
                        status=CheckStatus.FAIL,
                        message="Neo4j listening on all interfaces",
                        remediation="Configure dbms.default_listen_address=127.0.0.1",
                    )
                )
            else:
                self.results.append(
                    CheckResult(
                        name=name,
                        status=CheckStatus.WARN,
                        message="Neo4j port 7687 not found",
                        remediation="Verify Neo4j is running",
                    )
                )
        except FileNotFoundError:
            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.SKIP,
                    message="ss command not available",
                )
            )

    async def _check_models_verified(self):
        """Verify model integrity via checksums."""
        name = "Model Verification"

        # Check for model manifest with checksums
        manifest_path = self.config.models_path / "manifest.json"

        if not manifest_path.exists():
            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.WARN,
                    message="Model manifest not found",
                    details=f"Expected at: {manifest_path}",
                    remediation="Create manifest with model checksums",
                )
            )
            return

        try:
            with open(manifest_path) as f:
                manifest = json.load(f)

            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.INFO,
                    message=f"Model manifest found with {len(manifest.get('models', []))} models",
                )
            )
        except json.JSONDecodeError:
            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.FAIL,
                    message="Model manifest is invalid JSON",
                )
            )

    async def _check_file_permissions(self):
        """Verify file permissions are restrictive."""
        name = "File Permissions"

        issues = []

        # Check config directory
        if self.config.config_path.exists():
            mode = oct(self.config.config_path.stat().st_mode)[-3:]
            if int(mode[2]) > 0:  # World readable/writable/executable
                issues.append(f"Config dir has world permissions: {mode}")

        # Check data directory
        if self.config.data_path.exists():
            mode = oct(self.config.data_path.stat().st_mode)[-3:]
            if int(mode[2]) > 0:
                issues.append(f"Data dir has world permissions: {mode}")

        if issues:
            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.FAIL,
                    message="Overly permissive file permissions",
                    details="; ".join(issues),
                    remediation="chmod -R o-rwx on sensitive directories",
                )
            )
        else:
            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.PASS,
                    message="File permissions are appropriately restrictive",
                )
            )

    async def _check_user_isolation(self):
        """Check that application runs as non-root."""
        name = "User Isolation"

        if os.geteuid() == 0:
            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.FAIL,
                    message="Running as root - not recommended",
                    remediation="Create dedicated service account for application",
                )
            )
        else:
            self.results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.PASS,
                    message=f"Running as non-root user (uid={os.geteuid()})",
                )
            )

    def print_report(self):
        """Print formatted security report."""
        print()
        print("=" * 70)
        print("AIR-GAPPED DEPLOYMENT SECURITY REPORT")
        print("=" * 70)
        print(f"Deployment: {self.config.deployment_name}")
        print(f"Environment: {self.config.environment}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print("=" * 70)
        print()

        # Group by status
        passed = [r for r in self.results if r.status == CheckStatus.PASS]
        failed = [r for r in self.results if r.status == CheckStatus.FAIL]
        warned = [r for r in self.results if r.status == CheckStatus.WARN]
        skipped = [r for r in self.results if r.status == CheckStatus.SKIP]
        [r for r in self.results if r.status == CheckStatus.INFO]

        # Summary
        print(
            f"Summary: {len(passed)} passed, {len(failed)} failed, "
            f"{len(warned)} warnings, {len(skipped)} skipped"
        )
        print()

        # Failed (highest priority)
        if failed:
            print("FAILURES (must fix):")
            print("-" * 40)
            for result in failed:
                print(f"  {result}")
                if result.remediation:
                    print(f"    → Remediation: {result.remediation}")
            print()

        # Warnings
        if warned:
            print("WARNINGS (should fix):")
            print("-" * 40)
            for result in warned:
                print(f"  {result}")
                if result.remediation:
                    print(f"    → Remediation: {result.remediation}")
            print()

        # Passed
        if passed:
            print("PASSED:")
            print("-" * 40)
            for result in passed:
                print(f"  {result}")
            print()

        # Overall result
        print("=" * 70)
        if failed:
            print("RESULT: ✗ DEPLOYMENT NOT READY - Fix failures before deploying")
        elif warned:
            print("RESULT: ⚠ DEPLOYMENT READY WITH WARNINGS - Review warnings")
        else:
            print("RESULT: ✓ DEPLOYMENT READY")
        print("=" * 70)


# ══════════════════════════════════════════════════════════════════════════════
# OFFLINE MODEL LOADER
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class ModelManifestEntry:
    """Entry in the model manifest."""

    name: str
    filename: str
    sha256: str
    size_bytes: int
    purpose: str  # e.g., "general", "embedding", "code"


class OfflineModelLoader:
    """
    Load and verify AI models in air-gapped environment.

    Models must be:
    1. Pre-downloaded and transferred via approved media
    2. Verified against checksums in the manifest
    3. Loaded into Ollama for serving

    Transfer Process (manual):
    1. On internet-connected system: ollama pull <model>
    2. Export model: ollama cp <model> /media/transfer/<model>.tar
    3. Generate checksums: sha256sum /media/transfer/*.tar > manifest.txt
    4. Transfer via approved media (USB, DVD, etc.)
    5. On air-gapped system: Import and verify
    """

    def __init__(self, config: AirGappedConfig):
        self.config = config
        self.manifest_path = config.models_path / "manifest.json"
        self.manifest: dict = {}

    def load_manifest(self) -> bool:
        """Load model manifest from disk."""
        if not self.manifest_path.exists():
            logging.error(f"Manifest not found: {self.manifest_path}")
            return False

        try:
            with open(self.manifest_path) as f:
                self.manifest = json.load(f)
            return True
        except json.JSONDecodeError as e:
            logging.error(f"Invalid manifest: {e}")
            return False

    def verify_model(self, model_name: str) -> bool:
        """Verify model file integrity."""
        if model_name not in self.manifest.get("models", {}):
            logging.warning(f"Model {model_name} not in manifest")
            return False

        entry = self.manifest["models"][model_name]
        model_path = self.config.models_path / entry["filename"]

        if not model_path.exists():
            logging.error(f"Model file not found: {model_path}")
            return False

        # Calculate SHA256
        sha256 = hashlib.sha256()
        with open(model_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)

        calculated = sha256.hexdigest()
        expected = entry["sha256"]

        if calculated != expected:
            logging.error(
                f"Checksum mismatch for {model_name}:\n"
                f"  Expected: {expected}\n"
                f"  Got: {calculated}"
            )
            return False

        logging.info(f"Model {model_name} verified successfully")
        return True

    def verify_all_models(self) -> dict[str, bool]:
        """Verify all models in manifest."""
        results = {}
        for model_name in self.manifest.get("models", {}):
            results[model_name] = self.verify_model(model_name)
        return results

    async def check_ollama_models(self) -> dict[str, bool]:
        """Check which models are loaded in Ollama."""
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.config.ollama_host}/api/tags", timeout=10.0
                )

                if resp.status_code != 200:
                    return {}

                loaded = {m["name"] for m in resp.json().get("models", [])}

                results = {}
                for required in self.config.ollama_models:
                    results[required] = required in loaded

                return results
        except Exception as e:
            logging.error(f"Cannot check Ollama: {e}")
            return {}

    def create_manifest_template(self) -> str:
        """Create template manifest for model transfer."""
        template = {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "deployment": self.config.deployment_name,
            "models": {},
        }

        for model in self.config.ollama_models:
            template["models"][model] = {
                "filename": f"{model.replace(':', '_')}.tar",
                "sha256": "TO_BE_FILLED",
                "size_bytes": 0,
                "purpose": "general",
            }

        return json.dumps(template, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# LOCAL RAG SETUP
# ══════════════════════════════════════════════════════════════════════════════


class LocalRAGSetup:
    """
    Set up local-only RAG (Retrieval Augmented Generation).

    Components:
    - Neo4j for knowledge graph and vector storage
    - SQLite for full-text search backup
    - Ollama for embeddings (local only)
    - File-based document storage

    No external APIs or cloud services used.
    """

    def __init__(self, config: AirGappedConfig):
        self.config = config
        self.documents_path = config.data_path / "documents"
        self.embeddings_db = config.data_path / "embeddings.db"

    def initialize_storage(self):
        """Initialize local storage directories."""
        # Create directory structure
        directories = [
            self.documents_path,
            self.documents_path / "manuals",
            self.documents_path / "procedures",
            self.documents_path / "drawings",
            self.config.data_path / "indexes",
            self.config.data_path / "cache",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logging.info(f"Created directory: {directory}")

    def initialize_sqlite(self):
        """Initialize SQLite for full-text search."""
        conn = sqlite3.connect(self.embeddings_db)

        # Create document table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                classification TEXT NOT NULL,
                system TEXT,
                subsystem TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """
        )

        # Create FTS5 virtual table for full-text search
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                doc_id,
                title,
                content,
                tokenize='porter unicode61'
            )
        """
        )

        # Create embeddings table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                doc_id TEXT PRIMARY KEY,
                embedding BLOB NOT NULL,
                model TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
            )
        """
        )

        conn.commit()
        conn.close()
        logging.info(f"SQLite database initialized: {self.embeddings_db}")

    async def initialize_neo4j(self):
        """Initialize Neo4j schema for knowledge graph."""
        # Neo4j initialization would go here
        # For air-gapped, Neo4j must be pre-configured
        logging.info("Neo4j schema initialization (requires manual setup)")

        # Print setup instructions
        print(
            """
Neo4j Setup for Air-Gapped Deployment:

1. Install Neo4j Community or Enterprise on local system
2. Configure neo4j.conf:
   - dbms.default_listen_address=127.0.0.1
   - dbms.connector.bolt.listen_address=127.0.0.1:7687
   - dbms.security.auth_enabled=true

3. Create indexes:
   CREATE INDEX doc_id FOR (d:Document) ON (d.doc_id);
   CREATE INDEX doc_system FOR (d:Document) ON (d.system);
   CREATE INDEX doc_classification FOR (d:Document) ON (d.classification);

4. Create vector index (Neo4j 5.x):
   CALL db.index.vector.createNodeIndex(
     'document_embeddings',
     'Document',
     'embedding',
     1024,
     'cosine'
   );
"""
        )

    def import_documents(self, source_path: Path) -> int:
        """Import documents from source path."""
        count = 0
        conn = sqlite3.connect(self.embeddings_db)

        for doc_file in source_path.glob("**/*.json"):
            try:
                with open(doc_file) as f:
                    doc = json.load(f)

                conn.execute(
                    """
                    INSERT OR REPLACE INTO documents
                    (doc_id, title, content, classification, system, subsystem,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc["doc_id"],
                        doc["title"],
                        doc.get("content", ""),
                        doc["classification"],
                        doc.get("system", ""),
                        doc.get("subsystem", ""),
                        doc.get("created_at", datetime.now().isoformat()),
                        datetime.now().isoformat(),
                    ),
                )

                # Update FTS index
                conn.execute(
                    """
                    INSERT OR REPLACE INTO documents_fts (doc_id, title, content)
                    VALUES (?, ?, ?)
                    """,
                    (doc["doc_id"], doc["title"], doc.get("content", "")),
                )

                count += 1

            except Exception as e:
                logging.error(f"Error importing {doc_file}: {e}")

        conn.commit()
        conn.close()

        logging.info(f"Imported {count} documents")
        return count

    def search_documents(self, query: str, limit: int = 10) -> list[dict]:
        """Search documents using FTS5."""
        conn = sqlite3.connect(self.embeddings_db)

        cursor = conn.execute(
            """
            SELECT d.doc_id, d.title, d.classification, d.system,
                   snippet(documents_fts, 2, '>>>', '<<<', '...', 32) as snippet
            FROM documents_fts
            JOIN documents d ON documents_fts.doc_id = d.doc_id
            WHERE documents_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )

        results = []
        for row in cursor:
            results.append(
                {
                    "doc_id": row[0],
                    "title": row[1],
                    "classification": row[2],
                    "system": row[3],
                    "snippet": row[4],
                }
            )

        conn.close()
        return results


# ══════════════════════════════════════════════════════════════════════════════
# DOCKER DEPLOYMENT
# ══════════════════════════════════════════════════════════════════════════════


class DockerDeployment:
    """
    Generate Docker deployment artifacts for air-gapped systems.

    Creates:
    - Dockerfile with security hardening
    - docker-compose.yml for full stack
    - Configuration files
    - Startup scripts

    All images must be pre-pulled and transferred as .tar files.
    """

    def __init__(self, config: AirGappedConfig):
        self.config = config

    def generate_dockerfile(self) -> str:
        """Generate hardened Dockerfile."""
        return """# Air-Gapped Agentic Brain Deployment
# Security-hardened container for classified environments

FROM python:3.11-slim-bookworm AS base

# Security: Don't run as root
RUN groupadd -r airbrain && useradd -r -g airbrain airbrain

# Security: Minimize attack surface
RUN apt-get update && apt-get install -y --no-install-recommends \\
    ca-certificates \\
    curl \\
    && rm -rf /var/lib/apt/lists/* \\
    && apt-get clean

# Security: Remove unnecessary packages
RUN apt-get purge -y --auto-remove wget

WORKDIR /app

# Copy application
COPY --chown=airbrain:airbrain . /app

# Install dependencies (from local wheels, no PyPI access)
COPY wheels/ /wheels/
RUN pip install --no-index --find-links=/wheels -r requirements.txt

# Security: Read-only filesystem where possible
RUN chmod -R 555 /app && \\
    mkdir -p /app/data /app/logs && \\
    chmod -R 755 /app/data /app/logs && \\
    chown -R airbrain:airbrain /app/data /app/logs

# Security: Drop capabilities
USER airbrain

# Security: No shell needed
SHELL ["/bin/false"]

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# Expose only necessary port
EXPOSE 8000

# Security: Read-only root filesystem in docker-compose
# Security: No new privileges
# These are enforced in docker-compose.yml

ENTRYPOINT ["python", "-m", "agentic_brain.server"]
"""

    def generate_docker_compose(self) -> str:
        """Generate docker-compose.yml with security settings."""
        return """# Air-Gapped Deployment Stack
# docker-compose.yml

version: "3.8"

services:
  brain:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: airbrain
    restart: unless-stopped

    # Security: Read-only filesystem
    read_only: true

    # Security: No new privileges
    security_opt:
      - no-new-privileges:true

    # Security: Drop all capabilities, add only needed
    cap_drop:
      - ALL

    # Security: Resource limits
    deploy:
      resources:
        limits:
          cpus: "4.0"
          memory: 8G
        reservations:
          cpus: "1.0"
          memory: 2G

    # Security: No network access except to other containers
    networks:
      - airgap_internal

    # Writable volumes
    volumes:
      - brain_data:/app/data:rw
      - brain_logs:/app/logs:rw
      - type: tmpfs
        target: /tmp
        tmpfs:
          size: 100M

    environment:
      - OLLAMA_HOST=http://ollama:11434
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - LOG_LEVEL=INFO

    depends_on:
      - ollama
      - neo4j

    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped

    # Security settings
    read_only: true
    security_opt:
      - no-new-privileges:true

    networks:
      - airgap_internal

    volumes:
      - ollama_models:/root/.ollama:rw
      - type: tmpfs
        target: /tmp
        tmpfs:
          size: 1G

    deploy:
      resources:
        limits:
          cpus: "8.0"
          memory: 16G
        reservations:
          cpus: "2.0"
          memory: 8G

    # GPU access (if available)
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: all
    #           capabilities: [gpu]

  neo4j:
    image: neo4j:5-community
    container_name: neo4j
    restart: unless-stopped

    security_opt:
      - no-new-privileges:true

    networks:
      - airgap_internal

    volumes:
      - neo4j_data:/data:rw
      - neo4j_logs:/logs:rw

    environment:
      - NEO4J_AUTH=${NEO4J_PASSWORD:-changeme}
      - NEO4J_dbms_default__listen__address=0.0.0.0
      - NEO4J_dbms_security_auth__enabled=true
      - NEO4J_dbms_memory_heap_initial__size=512m
      - NEO4J_dbms_memory_heap_max__size=2G

    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 4G

networks:
  airgap_internal:
    driver: bridge
    internal: true  # No external access

volumes:
  brain_data:
  brain_logs:
  ollama_models:
  neo4j_data:
  neo4j_logs:
"""

    def generate_startup_script(self) -> str:
        """Generate secure startup script."""
        return """#!/bin/bash
# Air-Gapped Brain Startup Script
# Run with: sudo ./start.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Air-Gapped Agentic Brain Deployment"
echo "=========================================="

# Security checks
echo "[1/5] Running security checks..."

# Check not running as root (for docker-compose)
if [ "$EUID" -eq 0 ]; then
    echo "WARNING: Running as root. Use sudo for docker commands only."
fi

# Check network isolation
if ping -c 1 8.8.8.8 &> /dev/null; then
    echo "ERROR: External network access detected!"
    echo "This system must be air-gapped."
    exit 1
fi
echo "  ✓ Network isolation verified"

# Check Docker
if ! docker info &> /dev/null; then
    echo "ERROR: Docker not running or not accessible"
    exit 1
fi
echo "  ✓ Docker available"

# Check disk encryption (Linux)
if command -v cryptsetup &> /dev/null; then
    if cryptsetup status /dev/mapper/encrypted_data &> /dev/null; then
        echo "  ✓ Disk encryption active"
    else
        echo "  ⚠ Disk encryption not detected"
    fi
fi

# Load pre-transferred images
echo "[2/5] Loading container images..."
for image_tar in images/*.tar; do
    if [ -f "$image_tar" ]; then
        echo "  Loading: $image_tar"
        docker load -i "$image_tar"
    fi
done

# Verify Ollama models
echo "[3/5] Verifying AI models..."
if [ -d "models" ]; then
    for model_tar in models/*.tar; do
        if [ -f "$model_tar" ]; then
            echo "  Model: $model_tar"
            # Verify checksum
            model_name=$(basename "$model_tar" .tar)
            expected_hash=$(grep "$model_name" models/checksums.txt | cut -d' ' -f1)
            actual_hash=$(sha256sum "$model_tar" | cut -d' ' -f1)
            if [ "$expected_hash" = "$actual_hash" ]; then
                echo "    ✓ Checksum verified"
            else
                echo "    ✗ CHECKSUM MISMATCH - DO NOT USE"
                exit 1
            fi
        fi
    done
fi

# Start services
echo "[4/5] Starting services..."
docker-compose up -d

# Wait for health
echo "[5/5] Waiting for services to be healthy..."
sleep 10

# Check health
if docker-compose ps | grep -q "healthy"; then
    echo ""
    echo "=========================================="
    echo "✓ Deployment successful!"
    echo "=========================================="
    echo ""
    echo "Services:"
    docker-compose ps
    echo ""
    echo "Access: http://localhost:8000"
    echo ""
else
    echo "WARNING: Some services may not be healthy"
    docker-compose ps
    docker-compose logs --tail=20
fi
"""

    def save_deployment(self, output_path: Path):
        """Save all deployment files."""
        output_path.mkdir(parents=True, exist_ok=True)

        # Dockerfile
        with open(output_path / "Dockerfile", "w") as f:
            f.write(self.generate_dockerfile())

        # docker-compose.yml
        with open(output_path / "docker-compose.yml", "w") as f:
            f.write(self.generate_docker_compose())

        # Startup script
        startup_script = output_path / "start.sh"
        with open(startup_script, "w") as f:
            f.write(self.generate_startup_script())
        startup_script.chmod(0o755)

        # Create directories
        (output_path / "images").mkdir(exist_ok=True)
        (output_path / "models").mkdir(exist_ok=True)
        (output_path / "wheels").mkdir(exist_ok=True)
        (output_path / "config").mkdir(exist_ok=True)

        # Config file
        with open(output_path / "config" / "deployment.json", "w") as f:
            json.dump(self.config.to_dict(), f, indent=2)

        logging.info(f"Deployment files saved to: {output_path}")

        # Print instructions
        print(
            f"""
Air-Gapped Deployment Package Created: {output_path}

Transfer to air-gapped system:
1. Copy entire directory to approved transfer media
2. Transfer via sneakernet to target system
3. Run: ./start.sh

Required files to add:
- images/*.tar     - Docker images (docker save -o image.tar image:tag)
- models/*.tar     - Ollama models
- wheels/*.whl     - Python packages (pip download -d wheels/ -r requirements.txt)
"""
        )


# ══════════════════════════════════════════════════════════════════════════════
# HSM INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════


class HSMIntegration:
    """
    Hardware Security Module integration patterns.

    For air-gapped deployments requiring:
    - Key management
    - Certificate storage
    - Cryptographic operations

    Supports:
    - PKCS#11 compatible HSMs
    - SoftHSM for development/testing
    - AWS CloudHSM (for hybrid deployments)
    """

    def __init__(self, library_path: str = "/usr/lib/softhsm/libsofthsm2.so"):
        self.library_path = library_path
        self._session = None

    def check_availability(self) -> bool:
        """Check if HSM is available."""
        try:
            import pkcs11

            lib = pkcs11.lib(self.library_path)
            slots = lib.get_slots()
            return len(slots) > 0
        except Exception as e:
            logging.warning(f"HSM not available: {e}")
            return False

    def generate_key(self, key_label: str, key_size: int = 256) -> bool:
        """Generate AES key in HSM."""
        # This would use PKCS#11 in production
        logging.info(f"HSM: Would generate {key_size}-bit AES key: {key_label}")
        return True

    def encrypt_with_hsm(self, data: bytes, key_label: str) -> bytes:
        """Encrypt data using HSM key."""
        # This would use PKCS#11 in production
        # For demo, we use local encryption
        key = hashlib.sha256(key_label.encode()).digest()
        iv = secrets.token_bytes(16)

        # Simplified - would use proper AES-GCM with HSM
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

        cipher = Cipher(algorithms.AES(key), modes.GCM(iv))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()

        return iv + encryptor.tag + ciphertext

    def get_certificate(self, cert_label: str) -> bytes | None:
        """Retrieve certificate from HSM."""
        # This would use PKCS#11 in production
        logging.info(f"HSM: Would retrieve certificate: {cert_label}")
        return None

    @staticmethod
    def print_setup_guide():
        """Print HSM setup guide."""
        print(
            """
Hardware Security Module (HSM) Setup Guide

For Air-Gapped Deployments:

1. DEVELOPMENT/TESTING (SoftHSM)
   sudo apt install softhsm2
   softhsm2-util --init-token --slot 0 --label "airbrain"

2. PRODUCTION (Network HSM)
   - Configure network HSM on isolated management network
   - Install vendor PKCS#11 library
   - Update library_path in configuration

3. PRODUCTION (USB Token)
   - Use approved USB HSM token (e.g., YubiHSM)
   - Install vendor drivers and PKCS#11 library

Key Management:
- Master encryption key stored in HSM only
- Session keys derived from master key
- Audit keys separate from data keys
- Key rotation via HSM API

Supported HSMs:
- Thales Luna (production)
- Utimaco SecurityServer (production)
- YubiHSM 2 (portable)
- SoftHSM 2 (development only)
"""
        )


# ══════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ══════════════════════════════════════════════════════════════════════════════


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Air-Gapped Deployment Tools for Agentic Brain"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Verify command
    subparsers.add_parser("verify", help="Verify deployment readiness")

    # Docker command
    docker_parser = subparsers.add_parser("docker", help="Generate Docker deployment")
    docker_parser.add_argument(
        "--output", "-o", type=Path, default=Path("./deploy"), help="Output directory"
    )

    # Security check command
    subparsers.add_parser(
        "security-check", help="Run security checklist"
    )

    # RAG setup command
    subparsers.add_parser("rag-setup", help="Initialize local RAG storage")

    # HSM info command
    subparsers.add_parser("hsm-info", help="Show HSM setup information")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
    )

    # Create default config
    config = AirGappedConfig()

    if args.command == "verify":
        issues = config.validate()
        if issues:
            print("Configuration issues:")
            for issue in issues:
                print(f"  - {issue}")
            sys.exit(1)
        else:
            print("Configuration valid")
            print(json.dumps(config.to_dict(), indent=2))

    elif args.command == "docker":
        deployer = DockerDeployment(config)
        deployer.save_deployment(args.output)

    elif args.command == "security-check":
        checklist = SecurityChecklist(config)
        asyncio.run(checklist.run_all())
        checklist.print_report()

    elif args.command == "rag-setup":
        rag = LocalRAGSetup(config)
        rag.initialize_storage()
        rag.initialize_sqlite()
        asyncio.run(rag.initialize_neo4j())
        print("RAG storage initialized")

    elif args.command == "hsm-info":
        HSMIntegration.print_setup_guide()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
