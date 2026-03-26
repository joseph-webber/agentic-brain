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
Agentic Brain Mode System

42 operational modes for different use cases, industries, and architectures.
GraphRAG at the core, with hot-swap switching under 100ms.

Categories:
- USER (8): Free, Home, Developer, Business, Enterprise, Startup, Research, Creator
- INDUSTRY (20): Medical, Legal, Banking, Military, Education, Retail, etc.
- ARCHITECTURE (8): Monolith, Microservices, Cluster, Swarm, Airlock, etc.
- COMPLIANCE (4): HIPAA, GDPR, SOX, APRA
- POWER (2): Turbo, Maximum

Quick Usage:
    from agentic_brain.modes import ModeManager, set_mode, get_mode, list_modes

    # Switch modes
    set_mode("D")  # Developer mode
    set_mode("turbo")  # Maximum power

    # Get current mode
    mode = get_mode()
    print(f"Current: {mode.name}")

    # List all modes
    for mode in list_modes():
        print(f"{mode.code}: {mode.name}")

Short Codes Reference:
    USER: F=Free, H=Home, D=Developer, B=Business, E=Enterprise,
          ST=Startup, R=Research, CR=Creator
    INDUSTRY: MED=Medical, LAW=Legal, BANK=Banking, MIL=Military,
              EDU=Education, RET=Retail, MFG=Manufacturing, INS=Insurance,
              RE=RealEstate, HOSP=Hospitality, LOG=Logistics, TEL=Telecom,
              NRG=Energy, MEDIA=Media, GOV=Government, PHARMA=Pharmaceutical,
              AGRI=Agriculture, CON=Construction, AUTO=Automotive, NPO=NonProfit
    ARCHITECTURE: MONO=Monolith, MICRO=Microservices, CLU=Cluster, SWM=Swarm,
                  AIR=Airlock, EDGE=Edge, HYB=Hybrid, SRVL=Serverless
    COMPLIANCE: HIPAA, GDPR, SOX, APRA
    POWER: L=Turbo, P=Maximum
"""

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
)
from .manager import (
    ModeManager,
    ModeTransition,
    current_mode,
    get_manager,
    set_mode,
    status,
    switch,
)
from .registry import (
    CODE_TO_NAME,
    MODE_REGISTRY,
    MODES_BY_CATEGORY,
    get_mode_count,
    list_modes,
)
from .registry import (
    get_mode as registry_get_mode,
)
from .wizard import (
    ModeRecommendation,
    ModeWizard,
    WizardAnswer,
    WizardQuestion,
    WizardStep,
    interactive_wizard,
    quick_recommend,
)


# Convenience function that checks current mode first
def get_mode(name_or_code: str = None) -> Mode:
    """
    Get a mode by name/code, or get current mode if no argument.

    Args:
        name_or_code: Mode name or short code. If None, returns current mode.

    Returns:
        Mode object
    """
    if name_or_code is None:
        mode = current_mode()
        if mode is None:
            return registry_get_mode("developer")
        return mode
    return registry_get_mode(name_or_code)


# Module metadata
__version__ = "1.0.0"
__author__ = "Joseph Webber"
__license__ = "Apache-2.0"

__all__ = [
    # Core classes
    "Mode",
    "ModeConfig",
    "ModeCategory",
    "ModeManager",
    "ModeTransition",
    # Enums
    "RagType",
    "SecurityLevel",
    "VoicePersonality",
    # Config classes
    "LLMConfig",
    "RAGConfig",
    "SecurityConfig",
    "VoiceConfig",
    "ComplianceConfig",
    "ResourceConfig",
    # Registry
    "MODE_REGISTRY",
    "CODE_TO_NAME",
    "MODES_BY_CATEGORY",
    "get_mode_count",
    # Manager functions
    "get_manager",
    "get_mode",
    "set_mode",
    "list_modes",
    "current_mode",
    "switch",
    "status",
    # Wizard
    "ModeWizard",
    "WizardQuestion",
    "WizardAnswer",
    "WizardStep",
    "ModeRecommendation",
    "quick_recommend",
    "interactive_wizard",
]


# Quick verification on import
def _verify_modes():
    """Verify all 42 modes are registered."""
    counts = get_mode_count()
    total = sum(counts.values())

    expected = {
        "user": 8,
        "industry": 20,
        "architecture": 8,
        "compliance": 4,
        "power": 2,
    }

    for category, expected_count in expected.items():
        actual = counts.get(category, 0)
        if actual != expected_count:
            import warnings

            warnings.warn(
                f"Mode count mismatch for {category}: "
                f"expected {expected_count}, got {actual}"
            )

    if total != 42:
        import warnings

        warnings.warn(f"Expected 42 modes, got {total}")


# Run verification
_verify_modes()
