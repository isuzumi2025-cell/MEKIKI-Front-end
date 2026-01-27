"""
test_audit_ids.py - Unit tests for ID integrity audit

Run:
    pytest OCR/tests/test_audit_ids.py -v
"""

import pytest
from dataclasses import dataclass
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from OCR.scripts.audit_ids import IDAuditor, ErrorType


@dataclass
class DummyRegion:
    """Dummy region for testing"""
    area_code: str
    rect: tuple
    page: int = 0


@dataclass
class DummySyncPair:
    """Dummy SyncPair for testing"""
    web_id: str
    pdf_id: str
    web_text: str = ""
    pdf_text: str = ""
    similarity: float = 0.0


class TestIDAuditor:
    """Test suite for IDAuditor"""

    def test_perfect_match(self):
        """Test: All IDs match perfectly"""
        auditor = IDAuditor()

        web_regions = [
            DummyRegion("W-001", (100, 200, 500, 250)),
            DummyRegion("W-002", (100, 300, 500, 350)),
        ]

        pdf_regions = [
            DummyRegion("P-001", (120, 180, 480, 230)),
            DummyRegion("P-002", (120, 280, 480, 330)),
        ]

        sync_pairs = [
            DummySyncPair("W-001", "P-001"),
            DummySyncPair("W-002", "P-002"),
        ]

        report = auditor.audit(sync_pairs, web_regions, pdf_regions)

        assert report.status == "PASS"
        assert report.total_errors == 0
        assert report.checks["web_id_match"]["status"] == "PASS"
        assert report.checks["pdf_id_match"]["status"] == "PASS"

    def test_id_format_mismatch(self):
        """Test: Detect invalid ID format"""
        auditor = IDAuditor()

        web_regions = [
            DummyRegion("W001", (100, 200, 500, 250)),  # Missing hyphen
            DummyRegion("WEB-002", (100, 300, 500, 350)),  # Wrong prefix
        ]

        pdf_regions = []
        sync_pairs = []

        report = auditor.audit(sync_pairs, web_regions, pdf_regions)

        assert report.status == "FAIL"
        assert report.total_errors == 2
        assert any(e.error_type == ErrorType.ID_FORMAT_MISMATCH for e in report.errors)

    def test_duplicate_ids(self):
        """Test: Detect duplicate IDs"""
        auditor = IDAuditor()

        web_regions = [
            DummyRegion("W-001", (100, 200, 500, 250)),
            DummyRegion("W-001", (100, 300, 500, 350)),  # Duplicate
        ]

        pdf_regions = []
        sync_pairs = []

        report = auditor.audit(sync_pairs, web_regions, pdf_regions)

        assert report.status == "FAIL"
        assert report.total_errors == 1
        assert any(e.error_type == ErrorType.DUPLICATE_ID for e in report.errors)

    def test_missing_area_code(self):
        """Test: Detect missing area_code"""
        auditor = IDAuditor()

        web_regions = [
            DummyRegion("", (100, 200, 500, 250)),  # Empty area_code
            DummyRegion("W-002", (100, 300, 500, 350)),
        ]

        pdf_regions = []
        sync_pairs = []

        report = auditor.audit(sync_pairs, web_regions, pdf_regions)

        assert report.status == "FAIL"
        assert report.total_errors == 1
        assert any(e.error_type == ErrorType.MISSING_AREA_CODE for e in report.errors)

    def test_syncpair_mismatch(self):
        """Test: Detect SyncPair ID mismatch with regions"""
        auditor = IDAuditor()

        web_regions = [
            DummyRegion("W-001", (100, 200, 500, 250)),
            DummyRegion("W-002", (100, 300, 500, 350)),
        ]

        pdf_regions = [
            DummyRegion("P-001", (120, 180, 480, 230)),
        ]

        sync_pairs = [
            DummySyncPair("W-001", "P-001"),  # OK
            DummySyncPair("W-999", "P-001"),  # W-999 not in web_regions
        ]

        report = auditor.audit(sync_pairs, web_regions, pdf_regions)

        assert report.status == "FAIL"
        assert report.total_errors == 1
        assert any(e.error_type == ErrorType.MISSING_MAPPING for e in report.errors)
        assert any(e.entity_id == "W-999" for e in report.errors)

    def test_cross_media_collision(self):
        """Test: Detect ID collision between web and pdf"""
        auditor = IDAuditor()

        web_regions = [
            DummyRegion("W-001", (100, 200, 500, 250)),
        ]

        pdf_regions = [
            DummyRegion("W-001", (120, 180, 480, 230)),  # Same ID as web
        ]

        sync_pairs = []

        report = auditor.audit(sync_pairs, web_regions, pdf_regions)

        assert report.status == "FAIL"
        # Expect 2 errors: CROSS_MEDIA_COLLISION + ID_FORMAT_MISMATCH (PDF should be P-XXX)
        assert report.total_errors == 2
        assert any(e.error_type == ErrorType.CROSS_MEDIA_COLLISION for e in report.errors)

    def test_sel_prefix_allowed(self):
        """Test: SEL_ prefix is allowed for manual selections"""
        auditor = IDAuditor()

        web_regions = [
            DummyRegion("SEL_001", (100, 200, 500, 250)),  # Manual selection
            DummyRegion("W-002", (100, 300, 500, 350)),
        ]

        pdf_regions = []
        sync_pairs = []

        report = auditor.audit(sync_pairs, web_regions, pdf_regions)

        assert report.status == "PASS"
        assert report.total_errors == 0

    def test_empty_syncpair_ids_allowed(self):
        """Test: Empty SyncPair IDs are allowed (unmatched pairs)"""
        auditor = IDAuditor()

        web_regions = [
            DummyRegion("W-001", (100, 200, 500, 250)),
        ]

        pdf_regions = [
            DummyRegion("P-001", (120, 180, 480, 230)),
        ]

        sync_pairs = [
            DummySyncPair("W-001", ""),  # Unmatched web
            DummySyncPair("", "P-001"),  # Unmatched pdf
        ]

        report = auditor.audit(sync_pairs, web_regions, pdf_regions)

        # Empty IDs should not cause errors (they represent unmatched pairs)
        assert report.status == "PASS"
        assert report.total_errors == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
