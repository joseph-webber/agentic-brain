# SPDX-License-Identifier: Apache-2.0
"""
User Profile Management

Allows users to personalize agentic-brain with their details:
- Name, DOB, email, phone
- Location and timezone (MINIMUM: timezone required)
- Accessibility preferences
- Voice preferences

All data is stored locally and NEVER pushed to git.
Privacy-first: Users choose what to share.
"""

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from .location_service import (
    LocationInfo,
    detect_location,
    get_system_timezone,
    request_location_permission,
)


@dataclass
class UserProfile:
    """User's personal profile - stored locally, never shared."""

    # Identity
    name: str = ""
    date_of_birth: Optional[str] = None  # YYYY-MM-DD format
    emails: list[str] = field(default_factory=list)
    phone: str = ""

    # Location (user chooses what to share)
    address: str = ""
    city: str = ""
    state: str = ""
    postcode: str = ""
    country: str = ""

    # TIMEZONE IS REQUIRED - minimum we need to know
    timezone: str = ""

    # Accessibility
    blind: bool = False
    uses_voiceover: bool = False
    prefers_audio: bool = False

    # Voice preferences
    favorite_voice: str = "Samantha"
    speech_rate: int = 155
    regional_expressions: bool = True
    region: str = ""

    # Privacy settings - user controls what's shared
    share_name: bool = True
    share_location: bool = False  # Default to private
    share_age: bool = False
    share_timezone: bool = True  # Timezone usually OK to share

    @property
    def age(self) -> Optional[int]:
        """Calculate age from DOB."""
        if not self.date_of_birth:
            return None
        try:
            dob = datetime.strptime(self.date_of_birth, "%Y-%m-%d").date()
            today = date.today()
            return (
                today.year
                - dob.year
                - ((today.month, today.day) < (dob.month, dob.day))
            )
        except ValueError:
            return None

    @property
    def primary_email(self) -> str:
        """Get primary email."""
        return self.emails[0] if self.emails else ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        d = asdict(self)
        d["age"] = self.age
        return d

    def to_env(self) -> str:
        """Convert to .env format."""
        lines = [
            "# User Configuration - NEVER COMMIT THIS FILE",
            "# This file is git-ignored and stores user-specific settings",
            "",
            "# User Identity",
            f"USER_NAME={self.name}",
        ]

        for i, email in enumerate(self.emails):
            suffix = "" if i == 0 else f"_{i+1}"
            lines.append(f"USER_EMAIL{suffix}={email}")

        if self.phone:
            lines.append(f"USER_PHONE={self.phone.replace(' ', '')}")

        if self.date_of_birth:
            lines.append(f"USER_DOB={self.date_of_birth}")

        lines.extend(
            [
                "",
                "# Timezone (REQUIRED)",
                f"USER_TIMEZONE={self.timezone}",
                "",
                "# Location (optional - only if user shares)",
            ]
        )

        if self.share_location:
            lines.extend(
                [
                    f"USER_CITY={self.city}",
                    f"USER_STATE={self.state}",
                    f"USER_COUNTRY={self.country}",
                    f"USER_POSTCODE={self.postcode}",
                ]
            )

        lines.extend(
            [
                "",
                "# Accessibility",
                f"USER_BLIND={str(self.blind).lower()}",
                f"USER_USES_VOICEOVER={str(self.uses_voiceover).lower()}",
                f"USER_PREFERS_AUDIO={str(self.prefers_audio).lower()}",
                "",
                "# Voice Preferences",
                f"USER_FAVORITE_VOICE={self.favorite_voice}",
                f"USER_SPEECH_RATE={self.speech_rate}",
                f"USER_REGION={self.region}",
                "",
                "# Privacy Settings",
                f"USER_SHARE_NAME={str(self.share_name).lower()}",
                f"USER_SHARE_LOCATION={str(self.share_location).lower()}",
                f"USER_SHARE_AGE={str(self.share_age).lower()}",
                f"USER_SHARE_TIMEZONE={str(self.share_timezone).lower()}",
            ]
        )

        return "\n".join(lines)


def _get_profile_path() -> Path:
    """Get path to user profile JSON."""
    return Path.home() / ".agentic-brain" / "private" / "user_profile.json"


def _get_env_path() -> Path:
    """Get path to .env.user file."""
    current = Path.cwd()
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current / ".env.user"
        current = current.parent
    return Path.cwd() / ".env.user"


def get_user_profile() -> UserProfile:
    """Load user profile from disk."""
    profile_path = _get_profile_path()

    if profile_path.exists():
        try:
            with open(profile_path) as f:
                data = json.load(f)

            # Handle old format with nested location/emails
            if "location" in data and isinstance(data["location"], dict):
                loc = data.pop("location")
                data.update(
                    {
                        "address": loc.get("address", ""),
                        "city": loc.get("city", ""),
                        "state": loc.get("state", ""),
                        "postcode": loc.get("postcode", ""),
                        "country": loc.get("country", ""),
                        "timezone": loc.get("timezone", ""),
                    }
                )

            if "emails" in data and isinstance(data["emails"], dict):
                emails = data.pop("emails")
                data["emails"] = list(emails.values())

            # Filter to only valid fields
            valid_fields = {f.name for f in UserProfile.__dataclass_fields__.values()}
            filtered = {k: v for k, v in data.items() if k in valid_fields}

            return UserProfile(**filtered)
        except (json.JSONDecodeError, TypeError):
            pass

    return UserProfile()


def save_user_profile(profile: UserProfile) -> None:
    """Save user profile to disk (JSON and .env)."""
    profile_path = _get_profile_path()
    profile_path.parent.mkdir(parents=True, exist_ok=True)

    with open(profile_path, "w") as f:
        json.dump(profile.to_dict(), f, indent=2)

    env_path = _get_env_path()
    with open(env_path, "w") as f:
        f.write(profile.to_env())


def setup_user_profile(interactive: bool = True) -> UserProfile:
    """
    Interactive setup for user profile.

    Privacy-first approach:
    1. Try to detect timezone from system
    2. Ask permission for location services
    3. Let user choose what to share
    4. MINIMUM: Get timezone (required for greetings)
    """
    if not interactive:
        return UserProfile()

    print("\n🧠 Agentic Brain - User Setup")
    print("=" * 50)
    print("This information stays on YOUR computer.")
    print("Nothing is shared unless you choose to.")
    print("=" * 50)

    profile = get_user_profile()

    # 1. TIMEZONE DETECTION (try automatic first)
    print("\n🕐 Detecting timezone...")
    detected = detect_location(try_location_services=False, ask_user=False)

    if detected.timezone:
        print(f"   Detected: {detected.timezone}")
        use_detected = input("Use this timezone? (y/n) [y]: ").strip().lower()
        if use_detected != "n":
            profile.timezone = detected.timezone
            if detected.city:
                profile.city = detected.city
            if detected.state:
                profile.state = detected.state
            if detected.country:
                profile.country = detected.country

    if not profile.timezone:
        # Must get timezone manually
        print("\n⚠️  Timezone is REQUIRED for proper greetings and scheduling.")
        print("   Examples: Australia/Adelaide, America/New_York, Europe/London")
        while not profile.timezone:
            tz = input("Your timezone: ").strip()
            if tz:
                profile.timezone = tz
            else:
                print("   Please enter a timezone (e.g., Australia/Adelaide)")

    # 2. LOCATION SERVICES (optional)
    print("\n📍 Location Services (optional)")
    print("   This helps us use regional expressions and local knowledge.")
    want_location = input("Allow location detection? (y/n) [n]: ").strip().lower()

    if want_location == "y":
        print("   Requesting location access...")
        if request_location_permission():
            location = detect_location(try_location_services=True, ask_user=True)
            if location.city:
                print(f"   Detected: {location.city}, {location.country}")
                profile.city = location.city
                profile.state = location.state
                profile.country = location.country
                profile.share_location = True
        else:
            print("   Location access not granted - that's OK!")

    # 3. NAME (optional)
    name = input(f"\nYour name [{profile.name or 'skip'}]: ").strip()
    if name:
        profile.name = name

    # 4. EMAIL(S) (optional)
    email = input(f"Primary email [{profile.primary_email or 'skip'}]: ").strip()
    if email:
        if profile.emails:
            profile.emails[0] = email
        else:
            profile.emails = [email]

    more = input("Additional emails (comma-separated) [skip]: ").strip()
    if more:
        for e in more.split(","):
            e = e.strip()
            if e and e not in profile.emails:
                profile.emails.append(e)

    # 5. PHONE (optional)
    phone = input(f"Phone [{profile.phone or 'skip'}]: ").strip()
    if phone:
        profile.phone = phone

    # 6. DOB (optional)
    dob = input(
        f"Date of birth YYYY-MM-DD [{profile.date_of_birth or 'skip'}]: "
    ).strip()
    if dob:
        profile.date_of_birth = dob

    # 7. ACCESSIBILITY
    print("\n♿ Accessibility")
    if input("Enable accessibility features? (y/n) [n]: ").strip().lower() == "y":
        profile.blind = True
        profile.uses_voiceover = True
        profile.prefers_audio = True

    # 8. VOICE PREFERENCES
    print("\n🎙️ Voice Preferences")
    voice = input(f"Favorite voice [{profile.favorite_voice}]: ").strip()
    if voice:
        profile.favorite_voice = voice

    # 9. REGIONAL EXPRESSIONS
    if profile.city:
        region = profile.city.lower().replace(" ", "_")
        print(f"   Using regional expressions for: {profile.city}")
        profile.region = region
    else:
        region = (
            input(f"Regional expressions [{profile.region or 'skip'}]: ")
            .strip()
            .lower()
        )
        if region:
            profile.region = region

    # 10. PRIVACY SETTINGS
    print("\n🔒 Privacy Settings")
    profile.share_name = (
        input("OK to use your name? (y/n) [y]: ").strip().lower() != "n"
    )
    profile.share_age = (
        input("OK to mention your age? (y/n) [n]: ").strip().lower() == "y"
    )

    if profile.city and not profile.share_location:
        profile.share_location = (
            input("OK to use your location? (y/n) [n]: ").strip().lower() == "y"
        )

    # SAVE
    save_user_profile(profile)

    print("\n✅ Profile saved!")
    print(f"   JSON: {_get_profile_path()}")
    print(f"   ENV:  {_get_env_path()}")
    print(f"\n🕐 Timezone: {profile.timezone}")
    if profile.city and profile.share_location:
        print(f"📍 Location: {profile.city}, {profile.country}")
    print("\n🔒 This data is git-ignored and stays on your computer.")

    return profile


def get_user_name() -> str:
    """Get user's name if they allow sharing."""
    profile = get_user_profile()
    if profile.share_name and profile.name:
        return profile.name
    return ""


def get_user_email() -> str:
    """Get user's primary email."""
    profile = get_user_profile()
    return profile.primary_email


def get_user_timezone() -> str:
    """Get user's timezone (always available)."""
    profile = get_user_profile()
    if profile.timezone:
        return profile.timezone
    # Fallback to system timezone
    return get_system_timezone()


def get_user_location() -> dict:
    """Get user's location if they allow sharing."""
    profile = get_user_profile()
    if profile.share_location:
        return {
            "city": profile.city,
            "state": profile.state,
            "country": profile.country,
            "timezone": profile.timezone,
            "region": profile.region,
        }
    # Always return timezone even if location not shared
    return {"timezone": profile.timezone}
