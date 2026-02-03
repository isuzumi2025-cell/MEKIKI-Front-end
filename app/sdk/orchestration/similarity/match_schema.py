"""
match_schema.py - MatchResult Schema Definition (Phase 1.2)

Purpose: Define fixed schema for paragraph matching to stabilize downstream processes

Schema Version: 1.0.0
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from datetime import datetime
import uuid


class MatchStatus(str, Enum):
    """Match status classification"""
    EXACT = "EXACT"  # High confidence, strong similarity
    PARTIAL = "PARTIAL"  # Moderate confidence, partial match
    LOW_CONF = "LOW_CONF"  # Low confidence, weak match
    NO_MATCH = "NO_MATCH"  # No match found (unmatched region)


@dataclass
class BBox:
    """Bounding box with validation"""
    x1: int
    y1: int
    x2: int
    y2: int

    def __post_init__(self):
        # Ensure x1 <= x2, y1 <= y2
        if self.x1 > self.x2:
            self.x1, self.x2 = self.x2, self.x1
        if self.y1 > self.y2:
            self.y1, self.y2 = self.y2, self.y1

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        return self.width * self.height

    def to_tuple(self) -> Tuple[int, int, int, int]:
        """Convert to tuple format (x1, y1, x2, y2)"""
        return (self.x1, self.y1, self.x2, self.y2)

    @classmethod
    def from_tuple(cls, bbox: Tuple[int, int, int, int]) -> 'BBox':
        """Create from tuple (x1, y1, x2, y2)"""
        return cls(bbox[0], bbox[1], bbox[2], bbox[3])


@dataclass
class MatchEntity:
    """
    Represents one side of a match (Web or PDF)

    Required fields:
    - source_id: ID from web_id or pdf_id (e.g., "W-001", "P-001")
    - page: Page index (0-based)
    - bbox: Bounding box
    - text: Extracted text

    Optional fields:
    - role: Semantic role (headline, body, caption, etc.)
    - features: Additional metadata
    """
    source_id: str
    page: int
    bbox: BBox
    text: str
    role: Optional[str] = None
    features: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        # Ensure bbox is BBox type
        if isinstance(self.bbox, tuple):
            self.bbox = BBox.from_tuple(self.bbox)


@dataclass
class MatchScore:
    """
    Multi-dimensional match score

    - overall: Combined score (0.0-1.0)
    - text: Text similarity score (0.0-1.0)
    - layout: Layout similarity score (0.0-1.0, optional)
    - style: Style similarity score (0.0-1.0, optional)
    - confidence: Confidence level (0.0-1.0)
    """
    overall: float
    text: float
    layout: Optional[float] = None
    style: Optional[float] = None
    confidence: float = 1.0

    def __post_init__(self):
        # Clamp scores to [0.0, 1.0]
        self.overall = max(0.0, min(1.0, self.overall))
        self.text = max(0.0, min(1.0, self.text))
        if self.layout is not None:
            self.layout = max(0.0, min(1.0, self.layout))
        if self.style is not None:
            self.style = max(0.0, min(1.0, self.style))
        self.confidence = max(0.0, min(1.0, self.confidence))


@dataclass
class MatchDebug:
    """
    Debug information for match

    - id_audit_refs: References to ID audit results
    - notes: Human-readable notes
    - warnings: List of warning messages
    """
    id_audit_refs: Optional[List[str]] = None
    notes: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class MatchResult:
    """
    Complete match result with schema validation

    Schema Version: 1.0.0

    Required fields:
    - match_id: Unique identifier for this match
    - web: Web entity (or None if unmatched PDF)
    - pdf: PDF entity (or None if unmatched Web)
    - score: Match score
    - status: Match status classification

    Optional fields:
    - debug: Debug information
    - created_at: Timestamp
    """
    match_id: str
    web: Optional[MatchEntity]
    pdf: Optional[MatchEntity]
    score: MatchScore
    status: MatchStatus
    debug: MatchDebug = field(default_factory=MatchDebug)
    created_at: Optional[str] = None

    def __post_init__(self):
        # Generate match_id if not provided
        if not self.match_id:
            self.match_id = str(uuid.uuid4())

        # Set timestamp if not provided
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

        # Validate: at least one of web/pdf must be present
        if self.web is None and self.pdf is None:
            raise ValueError("MatchResult must have at least one of web or pdf")

        # Determine status from score if not explicitly set
        if self.status is None:
            if self.web is None or self.pdf is None:
                self.status = MatchStatus.NO_MATCH
            elif self.score.overall >= 0.8:
                self.status = MatchStatus.EXACT
            elif self.score.overall >= 0.5:
                self.status = MatchStatus.PARTIAL
            elif self.score.overall >= 0.25:
                self.status = MatchStatus.LOW_CONF
            else:
                self.status = MatchStatus.NO_MATCH

    @property
    def is_matched(self) -> bool:
        """Returns True if both web and pdf are matched"""
        return self.web is not None and self.pdf is not None

    @property
    def is_unmatched_web(self) -> bool:
        """Returns True if this is an unmatched web region"""
        return self.web is not None and self.pdf is None

    @property
    def is_unmatched_pdf(self) -> bool:
        """Returns True if this is an unmatched PDF region"""
        return self.web is None and self.pdf is not None

    def to_legacy_syncpair(self) -> 'SyncPair':
        """
        Convert to legacy SyncPair format for backward compatibility

        Returns a SyncPair with the same data in the old format
        """
        from .paragraph_matcher import SyncPair

        return SyncPair(
            web_id=self.web.source_id if self.web else "",
            pdf_id=self.pdf.source_id if self.pdf else "",
            web_text=self.web.text if self.web else "",
            pdf_text=self.pdf.text if self.pdf else "",
            similarity=self.score.overall,
            web_bbox=self.web.bbox.to_tuple() if self.web else None,
            pdf_bbox=self.pdf.bbox.to_tuple() if self.pdf else None
        )

    @classmethod
    def from_legacy_syncpair(
        cls,
        pair: 'SyncPair',
        web_page: int = 0,
        pdf_page: int = 0
    ) -> 'MatchResult':
        """
        Create MatchResult from legacy SyncPair

        Args:
            pair: Legacy SyncPair object
            web_page: Web page index (default: 0)
            pdf_page: PDF page index (default: 0)

        Returns:
            MatchResult with data from SyncPair
        """
        # Create web entity if web_id is present
        web_entity = None
        if pair.web_id and pair.web_id.strip():
            web_entity = MatchEntity(
                source_id=pair.web_id,
                page=web_page,
                bbox=BBox.from_tuple(pair.web_bbox) if pair.web_bbox else BBox(0, 0, 0, 0),
                text=pair.web_text or ""
            )

        # Create pdf entity if pdf_id is present
        pdf_entity = None
        if pair.pdf_id and pair.pdf_id.strip():
            pdf_entity = MatchEntity(
                source_id=pair.pdf_id,
                page=pdf_page,
                bbox=BBox.from_tuple(pair.pdf_bbox) if pair.pdf_bbox else BBox(0, 0, 0, 0),
                text=pair.pdf_text or ""
            )

        # Create score
        score = MatchScore(
            overall=pair.similarity,
            text=pair.similarity,  # Legacy only has one score
            confidence=1.0
        )

        # Determine status from similarity
        if pair.similarity >= 0.8:
            status = MatchStatus.EXACT
        elif pair.similarity >= 0.5:
            status = MatchStatus.PARTIAL
        elif pair.similarity >= 0.25:
            status = MatchStatus.LOW_CONF
        else:
            status = MatchStatus.NO_MATCH

        return cls(
            match_id=str(uuid.uuid4()),
            web=web_entity,
            pdf=pdf_entity,
            score=score,
            status=status
        )


# Schema version for tracking
MATCH_SCHEMA_VERSION = "1.0.0"
