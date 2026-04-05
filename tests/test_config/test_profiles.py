# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import agentic_brain.config.profiles as config_profiles
from agentic_brain.config.profiles import (
    BUILTIN_PROFILES,
    CustomProfile,
    DevelopmentProfile,
    ProductionProfile,
    ProfileName,
    StagingProfile,
    available_profiles,
    get_profile,
)


def test_development_profile_defaults():
    profile = DevelopmentProfile()
    defaults = profile.build()

    assert profile.name == ProfileName.DEVELOPMENT.value
    assert defaults["debug"] is True
    assert defaults["server"]["reload"] is True
    assert defaults["cache"]["backend"] == "memory"


def test_production_profile_defaults():
    profile = ProductionProfile()
    defaults = profile.build()

    assert profile.name == ProfileName.PRODUCTION.value
    assert defaults["debug"] is False
    assert defaults["server"]["reload"] is False
    assert defaults["server"]["docs_enabled"] is False
    assert defaults["cache"]["backend"] == "redis"


def test_testing_profile_defaults():
    profile = config_profiles.TestingProfile()
    defaults = profile.build()

    assert profile.name == ProfileName.TESTING.value
    assert defaults["neo4j"]["database"] == "test"
    assert defaults["features"]["voice_enabled"] is False


def test_staging_profile_defaults():
    profile = StagingProfile()
    defaults = profile.build()

    assert profile.name == ProfileName.STAGING.value
    assert defaults["server"]["workers"] == 2
    assert defaults["cache"]["backend"] == "redis"


def test_custom_profile_deep_merge():
    profile = CustomProfile(
        name="eu-production",
        defaults={
            "server": {"port": 9000, "workers": 2},
            "features": {"voice_enabled": False},
        },
    )

    merged = profile.build({"server": {"workers": 6}, "app_name": "EU Brain"})

    assert merged["server"] == {"port": 9000, "workers": 6}
    assert merged["features"]["voice_enabled"] is False
    assert merged["app_name"] == "EU Brain"


def test_get_profile_aliases():
    assert isinstance(get_profile("dev"), DevelopmentProfile)
    assert isinstance(get_profile("production"), ProductionProfile)
    assert isinstance(get_profile("testing"), config_profiles.TestingProfile)
    assert isinstance(get_profile("staging"), StagingProfile)


def test_available_profiles_contains_builtins():
    names = {profile.name for profile in available_profiles()}

    assert names == {
        ProfileName.DEVELOPMENT.value,
        ProfileName.STAGING.value,
        ProfileName.PRODUCTION.value,
        ProfileName.TESTING.value,
    }
    assert len(BUILTIN_PROFILES) == 4
