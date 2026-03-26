"""
🔒 SECURITY POSTURE MODES 🔒

Control how the router behaves based on security requirements.
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class PostureMode(Enum):
    """Security posture levels"""
    OPEN = "open"              # All workers, no restrictions
    STANDARD = "standard"      # Default, balanced security
    RESTRICTED = "restricted"  # Only approved workers
    AIRGAPPED = "airgapped"    # Local only, no external APIs
    COMPLIANCE = "compliance"  # Audit logging, approved only


@dataclass
class SecurityPosture:
    """
    Security posture configuration for the router.
    
    Controls which workers can be used and how.
    """
    mode: PostureMode = PostureMode.STANDARD
    
    # Worker restrictions
    allowed_workers: Optional[List[str]] = None  # None = all allowed
    blocked_workers: List[str] = None
    
    # Data handling
    log_prompts: bool = False      # Log all prompts (compliance)
    log_responses: bool = False    # Log all responses (compliance)
    redact_pii: bool = True        # Redact PII before sending
    
    # Rate limiting
    max_requests_per_minute: int = 60
    max_tokens_per_request: int = 4000
    
    # Cost controls
    max_cost_per_hour: float = 10.0
    prefer_free_workers: bool = True
    
    def __post_init__(self):
        if self.blocked_workers is None:
            self.blocked_workers = []
        
        # Apply mode defaults
        if self.mode == PostureMode.AIRGAPPED:
            self.allowed_workers = ["local"]
            self.log_prompts = False
            self.log_responses = False
        elif self.mode == PostureMode.COMPLIANCE:
            self.log_prompts = True
            self.log_responses = True
            self.redact_pii = True
        elif self.mode == PostureMode.RESTRICTED:
            if self.allowed_workers is None:
                self.allowed_workers = ["openai", "local"]
    
    def is_worker_allowed(self, worker_name: str) -> bool:
        """Check if a worker is allowed under current posture"""
        if worker_name in self.blocked_workers:
            return False
        if self.allowed_workers is not None:
            return worker_name in self.allowed_workers
        return True
    
    def filter_workers(self, workers: List[str]) -> List[str]:
        """Filter list of workers to only allowed ones"""
        return [w for w in workers if self.is_worker_allowed(w)]


# Preset postures
POSTURES = {
    "open": SecurityPosture(mode=PostureMode.OPEN),
    "standard": SecurityPosture(mode=PostureMode.STANDARD),
    "restricted": SecurityPosture(
        mode=PostureMode.RESTRICTED,
        allowed_workers=["openai", "local"],
    ),
    "airgapped": SecurityPosture(
        mode=PostureMode.AIRGAPPED,
        allowed_workers=["local"],
    ),
    "compliance": SecurityPosture(
        mode=PostureMode.COMPLIANCE,
        log_prompts=True,
        log_responses=True,
    ),
    "cost_saver": SecurityPosture(
        mode=PostureMode.STANDARD,
        prefer_free_workers=True,
        allowed_workers=["groq", "gemini", "local", "together"],
        max_cost_per_hour=1.0,
    ),
}

def get_posture(name: str) -> SecurityPosture:
    """Get a preset posture by name"""
    return POSTURES.get(name, POSTURES["standard"])
