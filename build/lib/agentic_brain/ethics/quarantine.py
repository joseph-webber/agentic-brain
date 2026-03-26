"""
Content Quarantine System

When AI is uncertain about content safety, it goes to quarantine for human review.
"""

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List


@dataclass
class QuarantinedContent:
    """Content held in quarantine for review."""
    id: str
    content: str
    channel: str
    reason: str
    context: str
    created_at: str
    status: str  # pending, approved, rejected
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None


class Quarantine:
    """
    Quarantine system for uncertain content.
    
    Locations:
        - Local: ~/.agentic-brain/quarantine/
        - Custom: User-specified path
    
    Usage:
        quarantine = Quarantine()
        quarantine.add("suspicious content", channel="email", reason="Contains PII")
        
        # Review pending items
        for item in quarantine.get_pending():
            if is_safe(item):
                quarantine.approve(item.id)
            else:
                quarantine.reject(item.id)
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize quarantine.
        
        Args:
            base_path: Custom quarantine path. Defaults to ~/.agentic-brain/quarantine/
        """
        if base_path:
            self.base_path = Path(base_path)
        else:
            self.base_path = Path.home() / ".agentic-brain" / "quarantine"
        
        # Create directory structure
        self.pending_path = self.base_path / "pending"
        self.approved_path = self.base_path / "approved"
        self.rejected_path = self.base_path / "rejected"
        
        for path in [self.pending_path, self.approved_path, self.rejected_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    def add(
        self,
        content: str,
        channel: str,
        reason: str,
        context: str = "",
    ) -> QuarantinedContent:
        """
        Add content to quarantine.
        
        Args:
            content: The content to quarantine
            channel: Target channel (teams, email, etc.)
            reason: Why it's being quarantined
            context: Additional context
            
        Returns:
            QuarantinedContent record
        """
        item = QuarantinedContent(
            id=str(uuid.uuid4())[:8],
            content=content,
            channel=channel,
            reason=reason,
            context=context,
            created_at=datetime.utcnow().isoformat(),
            status="pending",
        )
        
        # Save to pending
        file_path = self.pending_path / f"{item.id}.json"
        with open(file_path, "w") as f:
            json.dump(asdict(item), f, indent=2)
        
        return item
    
    def get_pending(self) -> List[QuarantinedContent]:
        """Get all pending items."""
        items = []
        for file_path in self.pending_path.glob("*.json"):
            with open(file_path) as f:
                data = json.load(f)
                items.append(QuarantinedContent(**data))
        return sorted(items, key=lambda x: x.created_at, reverse=True)
    
    def approve(self, item_id: str, reviewer: str = "human") -> bool:
        """
        Approve quarantined content.
        
        Args:
            item_id: ID of the item to approve
            reviewer: Who approved it
            
        Returns:
            True if approved successfully
        """
        return self._move_item(item_id, "approved", reviewer)
    
    def reject(self, item_id: str, reviewer: str = "human") -> bool:
        """
        Reject quarantined content.
        
        Args:
            item_id: ID of the item to reject
            reviewer: Who rejected it
            
        Returns:
            True if rejected successfully
        """
        return self._move_item(item_id, "rejected", reviewer)
    
    def _move_item(self, item_id: str, status: str, reviewer: str) -> bool:
        """Move item from pending to approved/rejected."""
        source = self.pending_path / f"{item_id}.json"
        if not source.exists():
            return False
        
        with open(source) as f:
            data = json.load(f)
        
        data["status"] = status
        data["reviewed_at"] = datetime.utcnow().isoformat()
        data["reviewed_by"] = reviewer
        
        dest_path = self.approved_path if status == "approved" else self.rejected_path
        dest = dest_path / f"{item_id}.json"
        
        with open(dest, "w") as f:
            json.dump(data, f, indent=2)
        
        source.unlink()
        return True


def quarantine_content(
    content: str,
    channel: str,
    reason: str,
    context: str = "",
    base_path: Optional[Path] = None,
) -> QuarantinedContent:
    """
    Convenience function to quarantine content.
    
    Args:
        content: Content to quarantine
        channel: Target channel
        reason: Why quarantining
        context: Additional context
        base_path: Optional custom path
        
    Returns:
        QuarantinedContent record
    """
    q = Quarantine(base_path)
    return q.add(content, channel, reason, context)
