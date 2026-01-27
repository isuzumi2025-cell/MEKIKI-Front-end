"""
Simplified unit tests for match schema validation (Phase 1 / Unit 2).

Tests core functionality of the actual implementation without assumptions.
"""

import pytest
from dataclasses import dataclass
from typing import Optional

# Import schema classes
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from sdk.similarity.match_schema import (
    BBox, MatchEntity, MatchScore, MatchResult, MatchStatus
)
from sdk.similarity.schema_validator import (
    MatchSchemaValidator, ValidationErrorType
)


# ============================================================================
# BBox Tests
# ============================================================================

class TestBBox:
    """Test BBox dataclass and conversions."""

    def test_bbox_creation(self):
        """Valid BBox creation."""
        bbox = BBox(x1=10, y1=20, x2=110, y2=50)
        assert bbox.x1 == 10
        assert bbox.y1 == 20
        assert bbox.x2 == 110
        assert bbox.y2 == 50

    def test_bbox_to_tuple(self):
        """BBox → tuple conversion."""
        bbox = BBox(x1=10, y1=20, x2=110, y2=50)
        assert bbox.to_tuple() == (10, 20, 110, 50)

    def test_bbox_from_tuple(self):
        """tuple → BBox conversion."""
        bbox = BBox.from_tuple((10, 20, 110, 50))
        assert bbox.x1 == 10
        assert bbox.y1 == 20
        assert bbox.x2 == 110
        assert bbox.y2 == 50


# ============================================================================
# MatchEntity Tests
# ============================================================================

class TestMatchEntity:
    """Test MatchEntity validation."""

    def test_valid_web_entity(self):
        """Valid Web entity with W-XXX ID."""
        entity = MatchEntity(
            source_id="W-001",
            page=0,
            bbox=BBox(x1=10, y1=20, x2=110, y2=50),
            text="Sample text"
        )
        assert entity.source_id == "W-001"
        assert entity.page == 0

    def test_valid_pdf_entity(self):
        """Valid PDF entity with P-XXX ID."""
        entity = MatchEntity(
            source_id="P-042",
            page=5,
            bbox=BBox(x1=50, y1=100, x2=200, y2=150),
            text="PDF sample"
        )
        assert entity.source_id == "P-042"
        assert entity.page == 5

    def test_valid_sel_entity(self):
        """Valid manual selection entity with SEL_XXX ID."""
        entity = MatchEntity(
            source_id="SEL_001",
            page=0,
            bbox=BBox(x1=0, y1=0, x2=100, y2=100),
            text="Manual selection"
        )
        assert entity.source_id == "SEL_001"


# ============================================================================
# MatchScore Tests
# ============================================================================

class TestMatchScore:
    """Test MatchScore validation."""

    def test_valid_score(self):
        """Valid score in range [0.0, 1.0]."""
        score = MatchScore(overall=0.85, text=0.90, layout=0.80, confidence=1.0)
        assert 0.0 <= score.overall <= 1.0
        assert 0.0 <= score.text <= 1.0
        assert score.layout == 0.80


# ============================================================================
# Backward Compatibility Tests
# ============================================================================

class TestBackwardCompatibility:
    """Test conversion between MatchResult and legacy SyncPair."""

    def test_to_legacy_syncpair(self):
        """MatchResult → SyncPair conversion."""
        from sdk.similarity.match_schema import MatchDebug

        match = MatchResult(
            match_id="M-001",
            web=MatchEntity(
                source_id="W-001",
                page=0,
                bbox=BBox(x1=10, y1=20, x2=110, y2=50),
                text="Web text"
            ),
            pdf=MatchEntity(
                source_id="P-001",
                page=0,
                bbox=BBox(x1=50, y1=100, x2=200, y2=150),
                text="PDF text"
            ),
            score=MatchScore(overall=0.95, text=0.98),
            status=MatchStatus.EXACT,
            debug=MatchDebug(notes="test")
        )

        sync_pair = match.to_legacy_syncpair()

        # Check basic fields
        assert sync_pair.web_id == "W-001"
        assert sync_pair.pdf_id == "P-001"
        assert sync_pair.similarity == 0.95
        assert sync_pair.web_text == "Web text"
        assert sync_pair.pdf_text == "PDF text"

    def test_from_legacy_syncpair_basic(self):
        """Basic SyncPair → MatchResult conversion (no bbox)."""
        # Mock SyncPair structure (minimal)
        @dataclass
        class MockSyncPair:
            web_id: str
            pdf_id: str
            similarity: float
            web_text: str
            pdf_text: str
            web_bbox: Optional[tuple] = None
            pdf_bbox: Optional[tuple] = None

        sync_pair = MockSyncPair(
            web_id="W-002",
            pdf_id="P-002",
            similarity=0.87,
            web_text="Legacy web",
            pdf_text="Legacy pdf"
        )

        match = MatchResult.from_legacy_syncpair(sync_pair)

        assert match.web.source_id == "W-002"
        assert match.pdf.source_id == "P-002"
        assert match.score.overall == 0.87
        assert match.web.text == "Legacy web"
        assert match.pdf.text == "Legacy pdf"
        assert match.status == MatchStatus.EXACT

    def test_roundtrip_conversion(self):
        """MatchResult → SyncPair → MatchResult roundtrip."""
        from sdk.similarity.match_schema import MatchDebug

        original = MatchResult(
            match_id="M-999",
            web=MatchEntity(
                source_id="W-999",
                page=0,
                bbox=BBox(x1=10, y1=20, x2=110, y2=50),
                text="Roundtrip test"
            ),
            pdf=MatchEntity(
                source_id="P-999",
                page=0,
                bbox=BBox(x1=50, y1=100, x2=200, y2=150),
                text="Roundtrip test"
            ),
            score=MatchScore(overall=0.88, text=0.90),
            status=MatchStatus.PARTIAL,
            debug=MatchDebug(notes="test")
        )

        sync_pair = original.to_legacy_syncpair()
        restored = MatchResult.from_legacy_syncpair(sync_pair)

        # Check key fields preserved
        assert restored.web.source_id == original.web.source_id
        assert restored.pdf.source_id == original.pdf.source_id
        assert restored.score.overall == original.score.overall
        assert restored.web.bbox.to_tuple() == original.web.bbox.to_tuple()
        assert restored.pdf.bbox.to_tuple() == original.pdf.bbox.to_tuple()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
