# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

# Copyright 2026 Joseph Webber
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
Mode Registry - All 42 operational modes defined.

Categories:
- USER: 8 modes (Free, Home, Developer, Business, Enterprise, Startup, Research, Creator)
- INDUSTRY: 20 modes (Medical, Legal, Banking, Military, Education, Retail, etc.)
- ARCHITECTURE: 8 modes (Monolith, Microservices, Cluster, Swarm, Airlock, etc.)
- COMPLIANCE: 4 modes (HIPAA, GDPR, SOX, APRA)
- POWER: 2 modes (Turbo, Maximum)

Total: 42 modes
"""

from typing import Dict, List, Optional

from .base import (
    ComplianceConfig,
    LLMConfig,
    Mode,
    ModeCategory,
    ModeConfig,
    RAGConfig,
    RagType,
    ResourceConfig,
    SecurityConfig,
    SecurityLevel,
    VoiceConfig,
    VoicePersonality,
    create_developer_llm,
    create_enterprise_security,
    create_gdpr_compliance,
    create_hipaa_compliance,
    create_turbo_resources,
)


def _build_mode_registry() -> Dict[str, Mode]:
    """Build the complete registry of 42 modes."""
    modes: Dict[str, Mode] = {}

    # =========================================================================
    # USER MODES (8)
    # =========================================================================

    # FREE - Basic free tier
    modes["free"] = Mode(
        name="Free",
        code="F",
        category=ModeCategory.USER,
        description="Free tier with basic capabilities. GraphRAG enabled, limited resources.",
        icon="🆓",
        color="#10B981",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="gpt-4o-mini",
                fallback_model="llama3.1:8b",
                max_tokens=2048,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG, top_k=5),
            resources=ResourceConfig(
                max_agents=3,
                max_memory_mb=1024,
                max_concurrent_requests=10,
                priority=1,
            ),
            features={
                "multi_agent": False,
                "code_execution": True,
                "web_browsing": True,
                "file_access": True,
                "external_apis": False,
                "learning": True,
                "memory": True,
                "plugins": False,
            },
        ),
    )

    # HOME - Personal/home use
    modes["home"] = Mode(
        name="Home",
        code="H",
        category=ModeCategory.USER,
        description="Personal home assistant mode. Family-friendly, privacy-focused.",
        icon="🏠",
        color="#F59E0B",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.7,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            voice=VoiceConfig(
                personality=VoicePersonality.FRIENDLY,
                primary_voice="Samantha",
                persona_mode=True,
                ambient_music=True,
            ),
            security=SecurityConfig(
                level=SecurityLevel.INTERNAL,
                pii_detection=True,
            ),
            resources=ResourceConfig(max_agents=5, priority=3),
        ),
    )

    # DEVELOPER - Software development
    modes["developer"] = Mode(
        name="Developer",
        code="D",
        category=ModeCategory.USER,
        description="Optimized for software development. Full code execution, debugging, and technical analysis.",
        icon="👨‍💻",
        color="#6366F1",
        config=ModeConfig(
            llm=create_developer_llm(),
            rag=RAGConfig(
                rag_type=RagType.GRAPHRAG,
                chunk_size=1024,
                top_k=15,
                graph_depth=4,
            ),
            voice=VoiceConfig(
                personality=VoicePersonality.TECHNICAL,
                primary_voice="Daniel",
            ),
            resources=ResourceConfig(
                max_agents=20,
                max_memory_mb=8192,
                max_concurrent_requests=50,
                priority=7,
            ),
            features={
                "multi_agent": True,
                "code_execution": True,
                "web_browsing": True,
                "file_access": True,
                "external_apis": True,
                "learning": True,
                "memory": True,
                "plugins": True,
            },
        ),
    )

    # BUSINESS - General business use
    modes["business"] = Mode(
        name="Business",
        code="B",
        category=ModeCategory.USER,
        description="Professional business mode. Document processing, analytics, reporting.",
        icon="💼",
        color="#3B82F6",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.5,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            voice=VoiceConfig(
                personality=VoicePersonality.PROFESSIONAL,
                primary_voice="Karen (Premium)",
            ),
            security=SecurityConfig(
                level=SecurityLevel.CONFIDENTIAL,
                encryption_required=True,
                audit_logging=True,
            ),
            resources=ResourceConfig(max_agents=15, priority=6),
        ),
    )

    # ENTERPRISE - Large organization
    modes["enterprise"] = Mode(
        name="Enterprise",
        code="E",
        category=ModeCategory.USER,
        description="Enterprise-grade deployment. Full compliance, SSO, advanced security.",
        icon="🏢",
        color="#7C3AED",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.3,
                reasoning_enabled=True,
            ),
            rag=RAGConfig(
                rag_type=RagType.HYBRID,
                graph_depth=5,
                top_k=20,
            ),
            security=create_enterprise_security(),
            voice=VoiceConfig(
                personality=VoicePersonality.PROFESSIONAL,
                primary_voice="Karen (Premium)",
            ),
            compliance=ComplianceConfig(
                audit_trail=True,
                data_residency="AU",
            ),
            resources=ResourceConfig(
                max_agents=50,
                max_memory_mb=16384,
                max_concurrent_requests=200,
                priority=8,
            ),
        ),
    )

    # STARTUP - Fast-moving startup
    modes["startup"] = Mode(
        name="Startup",
        code="ST",
        category=ModeCategory.USER,
        description="Agile startup mode. Fast iteration, experimentation, growth focus.",
        icon="🚀",
        color="#EC4899",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.8,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            voice=VoiceConfig(
                personality=VoicePersonality.ENERGETIC,
                primary_voice="Alex",
            ),
            resources=ResourceConfig(
                max_agents=25,
                max_memory_mb=8192,
                priority=7,
            ),
            features={
                "multi_agent": True,
                "code_execution": True,
                "web_browsing": True,
                "file_access": True,
                "external_apis": True,
                "learning": True,
                "memory": True,
                "plugins": True,
            },
        ),
    )

    # RESEARCH - Academic/research
    modes["research"] = Mode(
        name="Research",
        code="R",
        category=ModeCategory.USER,
        description="Academic research mode. Deep analysis, citations, reproducibility.",
        icon="🔬",
        color="#14B8A6",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.2,
                max_tokens=16384,
                reasoning_enabled=True,
            ),
            rag=RAGConfig(
                rag_type=RagType.HYBRID,
                chunk_size=2048,
                top_k=25,
                graph_depth=5,
            ),
            voice=VoiceConfig(
                personality=VoicePersonality.TECHNICAL,
                primary_voice="Daniel",
            ),
            resources=ResourceConfig(
                max_agents=30,
                max_memory_mb=16384,
                request_timeout_seconds=600,
                priority=6,
            ),
        ),
    )

    # CREATOR - Content creation
    modes["creator"] = Mode(
        name="Creator",
        code="CR",
        category=ModeCategory.USER,
        description="Content creator mode. Writing, art, music, video assistance.",
        icon="🎨",
        color="#F472B6",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.9,
                max_tokens=8192,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            voice=VoiceConfig(
                personality=VoicePersonality.FRIENDLY,
                primary_voice="Samantha",
                persona_mode=True,
            ),
            resources=ResourceConfig(
                max_agents=15,
                max_memory_mb=8192,
                priority=5,
            ),
        ),
    )

    # =========================================================================
    # INDUSTRY MODES (20)
    # =========================================================================

    # MEDICAL - Healthcare
    modes["medical"] = Mode(
        name="Medical",
        code="MED",
        category=ModeCategory.INDUSTRY,
        description="Healthcare industry mode. HIPAA compliant, clinical terminology, patient safety.",
        icon="🏥",
        color="#DC2626",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.1,
                reasoning_enabled=True,
            ),
            rag=RAGConfig(
                rag_type=RagType.GRAPHRAG,
                top_k=20,
                graph_depth=4,
            ),
            security=SecurityConfig(
                level=SecurityLevel.SECRET,
                encryption_required=True,
                pii_detection=True,
                pii_redaction=True,
                audit_logging=True,
            ),
            compliance=create_hipaa_compliance(),
            voice=VoiceConfig(
                personality=VoicePersonality.CALM,
                primary_voice="Moira",
            ),
        ),
    )

    # LEGAL - Law firms
    modes["legal"] = Mode(
        name="Legal",
        code="LAW",
        category=ModeCategory.INDUSTRY,
        description="Legal industry mode. Contract analysis, case research, compliance.",
        icon="⚖️",
        color="#1F2937",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.1,
                max_tokens=16384,
                reasoning_enabled=True,
            ),
            rag=RAGConfig(
                rag_type=RagType.HYBRID,
                chunk_size=2048,
                top_k=30,
                graph_depth=5,
            ),
            security=SecurityConfig(
                level=SecurityLevel.CONFIDENTIAL,
                encryption_required=True,
                audit_logging=True,
            ),
            voice=VoiceConfig(
                personality=VoicePersonality.PROFESSIONAL,
                primary_voice="Daniel",
            ),
        ),
    )

    # BANKING - Financial services
    modes["banking"] = Mode(
        name="Banking",
        code="BANK",
        category=ModeCategory.INDUSTRY,
        description="Banking and financial services. SOX/PCI compliant, fraud detection.",
        icon="🏦",
        color="#0369A1",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.1,
                reasoning_enabled=True,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            security=SecurityConfig(
                level=SecurityLevel.SECRET,
                encryption_required=True,
                pii_detection=True,
                pii_redaction=True,
                mfa_required=True,
            ),
            compliance=ComplianceConfig(
                frameworks=["SOX", "PCI-DSS", "GLBA"],
                audit_trail=True,
                retention_policy="7_years",
            ),
        ),
    )

    # MILITARY - Defense
    modes["military"] = Mode(
        name="Military",
        code="MIL",
        category=ModeCategory.INDUSTRY,
        description="Military/defense mode. Maximum security, air-gapped capable.",
        icon="🎖️",
        color="#065F46",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="llama3.1:70b",  # Local only
                fallback_model="llama3.1:8b",
                use_local_fallback=True,
                temperature=0.1,
            ),
            rag=RAGConfig(
                rag_type=RagType.GRAPHRAG,
                neo4j_enabled=True,
            ),
            security=SecurityConfig(
                level=SecurityLevel.TOP_SECRET,
                encryption_required=True,
                air_gapped=True,
                mfa_required=True,
                audit_logging=True,
            ),
            voice=VoiceConfig(
                personality=VoicePersonality.TECHNICAL,
                primary_voice="Daniel",
            ),
            features={
                "multi_agent": True,
                "code_execution": True,
                "web_browsing": False,  # Air-gapped
                "file_access": True,
                "external_apis": False,  # Air-gapped
                "learning": True,
                "memory": True,
                "plugins": False,
            },
        ),
    )

    # EDUCATION - Schools/Universities
    modes["education"] = Mode(
        name="Education",
        code="EDU",
        category=ModeCategory.INDUSTRY,
        description="Education sector. Learning assistance, plagiarism awareness, age-appropriate.",
        icon="🎓",
        color="#7C3AED",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.6,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            voice=VoiceConfig(
                personality=VoicePersonality.FRIENDLY,
                primary_voice="Samantha",
            ),
            security=SecurityConfig(
                level=SecurityLevel.INTERNAL,
                pii_detection=True,
            ),
            compliance=ComplianceConfig(
                frameworks=["FERPA", "COPPA"],
            ),
        ),
    )

    # RETAIL - E-commerce/Retail
    modes["retail"] = Mode(
        name="Retail",
        code="RET",
        category=ModeCategory.INDUSTRY,
        description="Retail and e-commerce. Customer service, inventory, sales analytics.",
        icon="🛍️",
        color="#EA580C",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.7,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            voice=VoiceConfig(
                personality=VoicePersonality.FRIENDLY,
                primary_voice="Samantha",
            ),
        ),
    )

    # MANUFACTURING - Industrial
    modes["manufacturing"] = Mode(
        name="Manufacturing",
        code="MFG",
        category=ModeCategory.INDUSTRY,
        description="Manufacturing and industrial. Quality control, supply chain, safety.",
        icon="🏭",
        color="#78716C",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.3,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            security=SecurityConfig(
                level=SecurityLevel.CONFIDENTIAL,
            ),
        ),
    )

    # INSURANCE - Insurance companies
    modes["insurance"] = Mode(
        name="Insurance",
        code="INS",
        category=ModeCategory.INDUSTRY,
        description="Insurance industry. Claims processing, risk assessment, underwriting.",
        icon="🛡️",
        color="#4F46E5",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.2,
                reasoning_enabled=True,
            ),
            rag=RAGConfig(rag_type=RagType.HYBRID),
            security=SecurityConfig(
                level=SecurityLevel.CONFIDENTIAL,
                pii_detection=True,
                pii_redaction=True,
            ),
        ),
    )

    # REALESTATE - Real estate
    modes["realestate"] = Mode(
        name="Real Estate",
        code="RE",
        category=ModeCategory.INDUSTRY,
        description="Real estate industry. Property analysis, market trends, documentation.",
        icon="🏘️",
        color="#059669",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.5,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
        ),
    )

    # HOSPITALITY - Hotels/Travel
    modes["hospitality"] = Mode(
        name="Hospitality",
        code="HOSP",
        category=ModeCategory.INDUSTRY,
        description="Hospitality and travel. Booking assistance, guest services, multilingual.",
        icon="🏨",
        color="#0891B2",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.7,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            voice=VoiceConfig(
                personality=VoicePersonality.FRIENDLY,
                primary_voice="Samantha",
                persona_mode=True,
            ),
        ),
    )

    # LOGISTICS - Supply chain/Logistics
    modes["logistics"] = Mode(
        name="Logistics",
        code="LOG",
        category=ModeCategory.INDUSTRY,
        description="Logistics and supply chain. Tracking, optimization, routing.",
        icon="🚚",
        color="#CA8A04",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.3,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
        ),
    )

    # TELECOM - Telecommunications
    modes["telecom"] = Mode(
        name="Telecom",
        code="TEL",
        category=ModeCategory.INDUSTRY,
        description="Telecommunications. Network analysis, customer support, billing.",
        icon="📡",
        color="#0D9488",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.4,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
        ),
    )

    # ENERGY - Energy/Utilities
    modes["energy"] = Mode(
        name="Energy",
        code="NRG",
        category=ModeCategory.INDUSTRY,
        description="Energy and utilities. Grid management, sustainability, compliance.",
        icon="⚡",
        color="#FBBF24",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.3,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            security=SecurityConfig(
                level=SecurityLevel.CONFIDENTIAL,
            ),
        ),
    )

    # MEDIA - Media/Entertainment
    modes["media"] = Mode(
        name="Media",
        code="MEDIA",
        category=ModeCategory.INDUSTRY,
        description="Media and entertainment. Content creation, rights management, distribution.",
        icon="🎬",
        color="#E11D48",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.8,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            voice=VoiceConfig(
                personality=VoicePersonality.ENERGETIC,
            ),
        ),
    )

    # GOVERNMENT - Public sector
    modes["government"] = Mode(
        name="Government",
        code="GOV",
        category=ModeCategory.INDUSTRY,
        description="Government and public sector. Citizen services, compliance, transparency.",
        icon="🏛️",
        color="#4B5563",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.2,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            security=SecurityConfig(
                level=SecurityLevel.SECRET,
                encryption_required=True,
                audit_logging=True,
            ),
            compliance=ComplianceConfig(
                frameworks=["FedRAMP", "FISMA"],
                audit_trail=True,
            ),
        ),
    )

    # PHARMA - Pharmaceutical
    modes["pharma"] = Mode(
        name="Pharmaceutical",
        code="PHARMA",
        category=ModeCategory.INDUSTRY,
        description="Pharmaceutical industry. Drug research, clinical trials, FDA compliance.",
        icon="💊",
        color="#7C3AED",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.1,
                reasoning_enabled=True,
            ),
            rag=RAGConfig(
                rag_type=RagType.HYBRID,
                graph_depth=5,
            ),
            security=SecurityConfig(
                level=SecurityLevel.SECRET,
                encryption_required=True,
            ),
            compliance=ComplianceConfig(
                frameworks=["FDA", "GxP", "21CFR11"],
            ),
        ),
    )

    # AGRICULTURE - Farming/Agriculture
    modes["agriculture"] = Mode(
        name="Agriculture",
        code="AGRI",
        category=ModeCategory.INDUSTRY,
        description="Agriculture and farming. Crop management, weather, sustainability.",
        icon="🌾",
        color="#65A30D",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.5,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
        ),
    )

    # CONSTRUCTION - Building/Construction
    modes["construction"] = Mode(
        name="Construction",
        code="CON",
        category=ModeCategory.INDUSTRY,
        description="Construction industry. Project management, safety, compliance.",
        icon="🏗️",
        color="#F97316",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.4,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            security=SecurityConfig(
                level=SecurityLevel.CONFIDENTIAL,
            ),
        ),
    )

    # AUTOMOTIVE - Automotive industry
    modes["automotive"] = Mode(
        name="Automotive",
        code="AUTO",
        category=ModeCategory.INDUSTRY,
        description="Automotive industry. Design, manufacturing, dealer support.",
        icon="🚗",
        color="#1E40AF",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.4,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
        ),
    )

    # NONPROFIT - Non-profit organizations
    modes["nonprofit"] = Mode(
        name="Non-Profit",
        code="NPO",
        category=ModeCategory.INDUSTRY,
        description="Non-profit organizations. Donor management, grant writing, impact reporting.",
        icon="💚",
        color="#16A34A",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.6,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            voice=VoiceConfig(
                personality=VoicePersonality.FRIENDLY,
            ),
            resources=ResourceConfig(
                priority=4,  # Budget-conscious
            ),
        ),
    )

    # =========================================================================
    # ARCHITECTURE MODES (8)
    # =========================================================================

    # MONOLITH - Single deployment
    modes["monolith"] = Mode(
        name="Monolith",
        code="MONO",
        category=ModeCategory.ARCHITECTURE,
        description="Single monolithic deployment. Simple, self-contained, easy to manage.",
        icon="🧱",
        color="#6B7280",
        config=ModeConfig(
            llm=LLMConfig(primary_model="claude-sonnet-4-20250514"),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            resources=ResourceConfig(
                max_agents=5,
                max_memory_mb=4096,
            ),
        ),
    )

    # MICROSERVICES - Distributed services
    modes["microservices"] = Mode(
        name="Microservices",
        code="MICRO",
        category=ModeCategory.ARCHITECTURE,
        description="Distributed microservices architecture. Scalable, resilient, modular.",
        icon="🔗",
        color="#3B82F6",
        config=ModeConfig(
            llm=LLMConfig(primary_model="claude-sonnet-4-20250514"),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            resources=ResourceConfig(
                max_agents=50,
                max_memory_mb=16384,
                max_concurrent_requests=500,
            ),
        ),
    )

    # CLUSTER - Clustered deployment
    modes["cluster"] = Mode(
        name="Cluster",
        code="CLU",
        category=ModeCategory.ARCHITECTURE,
        description="Clustered deployment. High availability, load balanced, fault tolerant.",
        icon="🎯",
        color="#8B5CF6",
        config=ModeConfig(
            llm=LLMConfig(primary_model="claude-sonnet-4-20250514"),
            rag=RAGConfig(
                rag_type=RagType.GRAPHRAG,
                semantic_cache=True,
            ),
            resources=ResourceConfig(
                max_agents=100,
                max_memory_mb=32768,
                max_concurrent_requests=1000,
            ),
        ),
    )

    # SWARM - Agent swarm
    modes["swarm"] = Mode(
        name="Swarm",
        code="SWM",
        category=ModeCategory.ARCHITECTURE,
        description="Agent swarm architecture. Self-organizing, adaptive, emergent behavior.",
        icon="🐝",
        color="#F59E0B",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.7,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            resources=ResourceConfig(
                max_agents=200,
                max_memory_mb=65536,
                max_concurrent_requests=2000,
                priority=9,
            ),
            features={
                "multi_agent": True,
                "code_execution": True,
                "web_browsing": True,
                "file_access": True,
                "external_apis": True,
                "learning": True,
                "memory": True,
                "plugins": True,
            },
        ),
    )

    # AIRLOCK - Air-gapped security
    modes["airlock"] = Mode(
        name="Airlock",
        code="AIR",
        category=ModeCategory.ARCHITECTURE,
        description="Air-gapped secure environment. No external network, maximum isolation.",
        icon="🔒",
        color="#DC2626",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="llama3.1:70b",
                fallback_model="llama3.1:8b",
                use_local_fallback=True,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            security=SecurityConfig(
                level=SecurityLevel.TOP_SECRET,
                encryption_required=True,
                air_gapped=True,
                mfa_required=True,
            ),
            features={
                "multi_agent": True,
                "code_execution": True,
                "web_browsing": False,
                "file_access": True,
                "external_apis": False,
                "learning": True,
                "memory": True,
                "plugins": False,
            },
        ),
    )

    # EDGE - Edge computing
    modes["edge"] = Mode(
        name="Edge",
        code="EDGE",
        category=ModeCategory.ARCHITECTURE,
        description="Edge computing deployment. Low latency, local processing, IoT integration.",
        icon="📍",
        color="#06B6D4",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="llama3.1:8b",  # Smaller for edge
                max_tokens=2048,
            ),
            rag=RAGConfig(
                rag_type=RagType.VECTOR,  # Lighter than GraphRAG
                top_k=5,
            ),
            resources=ResourceConfig(
                max_agents=3,
                max_memory_mb=2048,
            ),
        ),
    )

    # HYBRID - Hybrid cloud
    modes["hybrid"] = Mode(
        name="Hybrid",
        code="HYB",
        category=ModeCategory.ARCHITECTURE,
        description="Hybrid cloud architecture. On-premise + cloud, flexible deployment.",
        icon="☁️",
        color="#0EA5E9",
        config=ModeConfig(
            llm=LLMConfig(primary_model="claude-sonnet-4-20250514"),
            rag=RAGConfig(rag_type=RagType.HYBRID),
            resources=ResourceConfig(
                max_agents=75,
                max_memory_mb=24576,
            ),
        ),
    )

    # SERVERLESS - Serverless functions
    modes["serverless"] = Mode(
        name="Serverless",
        code="SRVL",
        category=ModeCategory.ARCHITECTURE,
        description="Serverless architecture. Auto-scaling, pay-per-use, event-driven.",
        icon="⚡",
        color="#A855F7",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                streaming=False,  # Serverless often doesn't support streaming
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            resources=ResourceConfig(
                max_agents=1000,  # Can scale massively
                request_timeout_seconds=60,  # Shorter for serverless
            ),
        ),
    )

    # =========================================================================
    # COMPLIANCE MODES (4)
    # =========================================================================

    # HIPAA - Healthcare compliance
    modes["hipaa"] = Mode(
        name="HIPAA",
        code="HIPAA",
        category=ModeCategory.COMPLIANCE,
        description="HIPAA compliant mode. Protected health information, full audit trail.",
        icon="🏥",
        color="#DC2626",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.1,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            security=SecurityConfig(
                level=SecurityLevel.SECRET,
                encryption_required=True,
                pii_detection=True,
                pii_redaction=True,
                audit_logging=True,
            ),
            compliance=create_hipaa_compliance(),
        ),
    )

    # GDPR - EU data protection
    modes["gdpr"] = Mode(
        name="GDPR",
        code="GDPR",
        category=ModeCategory.COMPLIANCE,
        description="GDPR compliant mode. EU data protection, consent management, data portability.",
        icon="🇪🇺",
        color="#003399",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.2,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            security=SecurityConfig(
                level=SecurityLevel.CONFIDENTIAL,
                encryption_required=True,
                pii_detection=True,
                pii_redaction=True,
            ),
            compliance=create_gdpr_compliance(),
        ),
    )

    # SOX - Financial compliance
    modes["sox"] = Mode(
        name="SOX",
        code="SOX",
        category=ModeCategory.COMPLIANCE,
        description="SOX compliant mode. Financial controls, audit trail, segregation of duties.",
        icon="📊",
        color="#1E40AF",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.1,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            security=SecurityConfig(
                level=SecurityLevel.CONFIDENTIAL,
                encryption_required=True,
                audit_logging=True,
            ),
            compliance=ComplianceConfig(
                frameworks=["SOX", "COSO"],
                audit_trail=True,
                retention_policy="7_years",
            ),
        ),
    )

    # APRA - Australian prudential regulation
    modes["apra"] = Mode(
        name="APRA",
        code="APRA",
        category=ModeCategory.COMPLIANCE,
        description="APRA compliant mode. Australian prudential standards, CPS 234 security.",
        icon="🦘",
        color="#00843D",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                temperature=0.1,
            ),
            rag=RAGConfig(rag_type=RagType.GRAPHRAG),
            security=SecurityConfig(
                level=SecurityLevel.CONFIDENTIAL,
                encryption_required=True,
                audit_logging=True,
            ),
            compliance=ComplianceConfig(
                frameworks=["APRA", "CPS234", "CPS220"],
                data_residency="AU",
                audit_trail=True,
            ),
        ),
    )

    # =========================================================================
    # POWER MODES (2)
    # =========================================================================

    # TURBO - Maximum performance
    modes["turbo"] = Mode(
        name="Turbo",
        code="L",
        category=ModeCategory.POWER,
        description="Maximum performance mode. All limits removed, full power, no restrictions.",
        icon="🚀",
        color="#EF4444",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                fallback_model="gpt-4o",
                temperature=0.7,
                max_tokens=32768,
                context_window=200000,
                reasoning_enabled=True,
            ),
            rag=RAGConfig(
                rag_type=RagType.HYBRID,
                top_k=50,
                graph_depth=7,
                semantic_cache=True,
            ),
            resources=create_turbo_resources(),
            voice=VoiceConfig(
                personality=VoicePersonality.ENERGETIC,
                primary_voice="Alex",
            ),
            features={
                "multi_agent": True,
                "code_execution": True,
                "web_browsing": True,
                "file_access": True,
                "external_apis": True,
                "learning": True,
                "memory": True,
                "plugins": True,
            },
        ),
    )

    # PLAID - Beyond Turbo
    modes["plaid"] = Mode(
        name="Maximum",
        code="P",
        category=ModeCategory.POWER,
        description="Beyond Turbo. Experimental features, bleeding edge, no safety limits.",
        icon="🌈",
        color="#8B5CF6",
        config=ModeConfig(
            llm=LLMConfig(
                primary_model="claude-sonnet-4-20250514",
                fallback_model="gpt-4o",
                local_model="llama3.1:70b",
                temperature=0.9,
                max_tokens=65536,
                context_window=200000,
                reasoning_enabled=True,
            ),
            rag=RAGConfig(
                rag_type=RagType.HYBRID,
                top_k=100,
                graph_depth=10,
                semantic_cache=True,
            ),
            resources=ResourceConfig(
                max_agents=500,
                max_memory_mb=131072,
                max_cpu_percent=100.0,
                max_concurrent_requests=5000,
                request_timeout_seconds=7200,
                priority=10,
            ),
            voice=VoiceConfig(
                personality=VoicePersonality.ENERGETIC,
                primary_voice="Alex",
                persona_mode=True,
            ),
            features={
                "multi_agent": True,
                "code_execution": True,
                "web_browsing": True,
                "file_access": True,
                "external_apis": True,
                "learning": True,
                "memory": True,
                "plugins": True,
            },
            custom={
                "experimental": True,
                "bleeding_edge": True,
                "safety_limits": False,
            },
        ),
    )

    return modes


# Build the registry on module load
MODE_REGISTRY: Dict[str, Mode] = _build_mode_registry()

# Build code lookup table
CODE_TO_NAME: Dict[str, str] = {
    mode.code.upper(): name for name, mode in MODE_REGISTRY.items()
}

# Category groupings
MODES_BY_CATEGORY: Dict[ModeCategory, List[str]] = {
    ModeCategory.USER: [],
    ModeCategory.INDUSTRY: [],
    ModeCategory.ARCHITECTURE: [],
    ModeCategory.COMPLIANCE: [],
    ModeCategory.POWER: [],
}

for name, mode in MODE_REGISTRY.items():
    MODES_BY_CATEGORY[mode.category].append(name)


def get_mode(name_or_code: str) -> Mode:
    """
    Get a mode by name or short code.

    Args:
        name_or_code: Mode name (e.g., "developer") or code (e.g., "D")

    Returns:
        The Mode object

    Raises:
        KeyError: If mode not found
    """
    # Try direct name lookup
    name_lower = name_or_code.lower()
    if name_lower in MODE_REGISTRY:
        return MODE_REGISTRY[name_lower]

    # Try code lookup
    code_upper = name_or_code.upper()
    if code_upper in CODE_TO_NAME:
        return MODE_REGISTRY[CODE_TO_NAME[code_upper]]

    raise KeyError(f"Mode not found: {name_or_code}")


def list_modes(category: Optional[ModeCategory] = None) -> List[Mode]:
    """
    List all modes, optionally filtered by category.

    Args:
        category: Optional category filter

    Returns:
        List of Mode objects
    """
    if category:
        return [MODE_REGISTRY[name] for name in MODES_BY_CATEGORY[category]]
    return list(MODE_REGISTRY.values())


def get_mode_count() -> Dict[str, int]:
    """Get count of modes per category."""
    return {cat.value: len(modes) for cat, modes in MODES_BY_CATEGORY.items()}
