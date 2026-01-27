"""
audit_ids.py - ID Integrity Audit Tool

Purpose: Detect ID mismatches, duplicates, and format errors in web_id/pdf_id/area_code

Usage:
    python OCR/scripts/audit_ids.py --format=json
    python OCR/scripts/audit_ids.py --format=csv
    python OCR/scripts/audit_ids.py --format=console

Exit Codes:
    0: All checks PASS
    1: One or more checks FAIL
"""

import sys
import json
import csv
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from collections import Counter


class ErrorType(str, Enum):
    """Error classification for ID integrity issues"""
    ID_FORMAT_MISMATCH = "ID_FORMAT_MISMATCH"  # ID doesn't match W-XXX or P-XXX pattern
    MISSING_MAPPING = "MISSING_MAPPING"  # SyncPair.web_id not found in web_regions
    DUPLICATE_ID = "DUPLICATE_ID"  # Same area_code appears multiple times
    CROSS_MEDIA_COLLISION = "CROSS_MEDIA_COLLISION"  # Web/PDF ID collision
    PAGE_INDEX_OUT_OF_RANGE = "PAGE_INDEX_OUT_OF_RANGE"  # Page index exceeds bounds
    MISSING_AREA_CODE = "MISSING_AREA_CODE"  # area_code is None or empty


@dataclass
class IDError:
    """Represents a single ID integrity error"""
    error_type: ErrorType
    entity_type: str  # "SyncPair" | "WebRegion" | "PDFRegion"
    entity_id: str  # The problematic ID value
    expected: str
    actual: str
    detail: str
    page: int = None
    bbox: Tuple[int, int, int, int] = None
    source: str = None  # "web" | "pdf"


@dataclass
class AuditReport:
    """Complete audit report"""
    timestamp: str
    status: str  # "PASS" | "FAIL"
    total_errors: int
    checks: Dict[str, Any]
    errors: List[IDError]


class IDAuditor:
    """ID Integrity Auditor"""

    # ID format patterns
    WEB_ID_PATTERN = re.compile(r'^W-\d{3}$')
    PDF_ID_PATTERN = re.compile(r'^P-\d{3}$')
    SEL_ID_PATTERN = re.compile(r'^SEL_\d{3}$')

    def __init__(self):
        self.errors: List[IDError] = []

    def audit(
        self,
        sync_pairs: List[Any],
        web_regions: List[Any],
        pdf_regions: List[Any]
    ) -> AuditReport:
        """
        Perform complete ID integrity audit

        Args:
            sync_pairs: List of SyncPair objects
            web_regions: List of Web Region objects (with area_code)
            pdf_regions: List of PDF Region objects (with area_code)

        Returns:
            AuditReport with all findings
        """
        self.errors = []

        # Extract IDs and build maps
        web_ids = self._extract_ids(web_regions, "web")
        pdf_ids = self._extract_ids(pdf_regions, "pdf")

        # Build ID maps for quick lookup
        web_map = {self._get_area_code(r): r for r in web_regions}
        pdf_map = {self._get_area_code(r): r for r in pdf_regions}

        # Run checks
        checks = {
            "web_id_format": self._check_id_format(web_ids, "web"),
            "pdf_id_format": self._check_id_format(pdf_ids, "pdf"),
            "web_id_duplicate": self._check_duplicates(web_ids, "web"),
            "pdf_id_duplicate": self._check_duplicates(pdf_ids, "pdf"),
            "web_id_missing": self._check_missing_ids(web_regions, "web"),
            "pdf_id_missing": self._check_missing_ids(pdf_regions, "pdf"),
            "web_id_match": self._check_syncpair_match(sync_pairs, web_map, "web"),
            "pdf_id_match": self._check_syncpair_match(sync_pairs, pdf_map, "pdf"),
            "cross_media_collision": self._check_cross_media_collision(web_ids, pdf_ids),
        }

        # Generate report
        status = "PASS" if len(self.errors) == 0 else "FAIL"

        return AuditReport(
            timestamp=datetime.now().isoformat(),
            status=status,
            total_errors=len(self.errors),
            checks=checks,
            errors=self.errors
        )

    def _extract_ids(self, regions: List[Any], source: str) -> List[Tuple[str, Any]]:
        """Extract (ID, region) tuples from regions"""
        ids = []
        for r in regions:
            area_code = self._get_area_code(r)
            if area_code:
                ids.append((area_code, r))
        return ids

    def _get_area_code(self, region: Any) -> str:
        """Get area_code from region object (supports multiple attribute names)"""
        return (
            getattr(region, 'area_code', None) or
            getattr(region, 'id', None) or
            getattr(region, 'web_id', None) or
            getattr(region, 'pdf_id', None)
        )

    def _get_bbox(self, region: Any) -> Tuple[int, int, int, int]:
        """Get bbox from region object"""
        bbox = getattr(region, 'bbox', None) or getattr(region, 'rect', None)
        if bbox and len(bbox) == 4:
            return tuple(bbox)
        return None

    def _get_page(self, region: Any) -> int:
        """Get page index from region object"""
        return getattr(region, 'page', None) or getattr(region, 'page_index', 0)

    def _check_id_format(self, ids: List[Tuple[str, Any]], source: str) -> Dict[str, Any]:
        """Check if IDs match expected format (W-XXX or P-XXX)"""
        pattern = self.WEB_ID_PATTERN if source == "web" else self.PDF_ID_PATTERN
        expected_prefix = "W-" if source == "web" else "P-"

        valid_count = 0
        invalid_count = 0

        for id_str, region in ids:
            # Allow SEL_ prefix for manual selections
            if self.SEL_ID_PATTERN.match(id_str):
                valid_count += 1
                continue

            if not pattern.match(id_str):
                self.errors.append(IDError(
                    error_type=ErrorType.ID_FORMAT_MISMATCH,
                    entity_type=f"{source.title()}Region",
                    entity_id=id_str,
                    expected=f"{expected_prefix}XXX format",
                    actual=id_str,
                    detail=f"ID format does not match {expected_prefix}XXX pattern",
                    page=self._get_page(region),
                    bbox=self._get_bbox(region),
                    source=source
                ))
                invalid_count += 1
            else:
                valid_count += 1

        return {
            "status": "PASS" if invalid_count == 0 else "FAIL",
            "valid": valid_count,
            "invalid": invalid_count,
            "total": len(ids)
        }

    def _check_duplicates(self, ids: List[Tuple[str, Any]], source: str) -> Dict[str, Any]:
        """Check for duplicate IDs"""
        id_counts = Counter(id_str for id_str, _ in ids)
        duplicates = [(id_str, count) for id_str, count in id_counts.items() if count > 1]

        for id_str, count in duplicates:
            self.errors.append(IDError(
                error_type=ErrorType.DUPLICATE_ID,
                entity_type=f"{source.title()}Region",
                entity_id=id_str,
                expected="1 (unique)",
                actual=str(count),
                detail=f"ID appears {count} times (should be unique)",
                source=source
            ))

        return {
            "status": "PASS" if len(duplicates) == 0 else "FAIL",
            "duplicates": duplicates,
            "total": len(ids)
        }

    def _check_missing_ids(self, regions: List[Any], source: str) -> Dict[str, Any]:
        """Check for missing or empty area_code"""
        missing_count = 0

        for i, region in enumerate(regions):
            area_code = self._get_area_code(region)
            if not area_code or area_code.strip() == "":
                self.errors.append(IDError(
                    error_type=ErrorType.MISSING_AREA_CODE,
                    entity_type=f"{source.title()}Region",
                    entity_id=f"region_index_{i}",
                    expected="non-empty string",
                    actual="None or empty",
                    detail=f"Region at index {i} has no area_code",
                    page=self._get_page(region),
                    bbox=self._get_bbox(region),
                    source=source
                ))
                missing_count += 1

        return {
            "status": "PASS" if missing_count == 0 else "FAIL",
            "missing": missing_count,
            "total": len(regions)
        }

    def _check_syncpair_match(
        self,
        sync_pairs: List[Any],
        region_map: Dict[str, Any],
        source: str
    ) -> Dict[str, Any]:
        """Check if SyncPair IDs match region area_codes"""
        id_field = "web_id" if source == "web" else "pdf_id"
        matched = 0
        unmatched = 0
        empty = 0

        for pair in sync_pairs:
            pair_id = getattr(pair, id_field, "")

            # Skip empty IDs (unmatched pairs)
            if not pair_id or pair_id.strip() == "":
                empty += 1
                continue

            if pair_id not in region_map:
                self.errors.append(IDError(
                    error_type=ErrorType.MISSING_MAPPING,
                    entity_type="SyncPair",
                    entity_id=pair_id,
                    expected=f"{pair_id} exists in {source}_regions",
                    actual=f"{pair_id} NOT FOUND in {source}_regions",
                    detail=f"SyncPair.{id_field}={pair_id} has no corresponding region",
                    source=source
                ))
                unmatched += 1
            else:
                matched += 1

        return {
            "status": "PASS" if unmatched == 0 else "FAIL",
            "matched": matched,
            "unmatched": unmatched,
            "empty": empty,
            "total": len(sync_pairs)
        }

    def _check_cross_media_collision(
        self,
        web_ids: List[Tuple[str, Any]],
        pdf_ids: List[Tuple[str, Any]]
    ) -> Dict[str, Any]:
        """Check for ID collisions between web and pdf"""
        web_id_set = {id_str for id_str, _ in web_ids}
        pdf_id_set = {id_str for id_str, _ in pdf_ids}

        collisions = web_id_set & pdf_id_set

        for id_str in collisions:
            self.errors.append(IDError(
                error_type=ErrorType.CROSS_MEDIA_COLLISION,
                entity_type="CrossMedia",
                entity_id=id_str,
                expected="unique across web/pdf",
                actual=f"appears in both web and pdf",
                detail=f"ID {id_str} exists in both web_regions and pdf_regions"
            ))

        return {
            "status": "PASS" if len(collisions) == 0 else "FAIL",
            "collisions": list(collisions),
            "total_web": len(web_ids),
            "total_pdf": len(pdf_ids)
        }


def format_console_report(report: AuditReport) -> str:
    """Format report for console output"""
    lines = []
    lines.append("=" * 60)
    lines.append("🔍 ID Integrity Audit Report")
    lines.append("=" * 60)
    lines.append(f"Timestamp: {report.timestamp}")
    lines.append(f"Status: {'✅ PASS' if report.status == 'PASS' else '❌ FAIL'}")
    lines.append(f"Total Errors: {report.total_errors}")
    lines.append("")

    # Checks summary
    for check_name, result in report.checks.items():
        status_icon = "✅" if result["status"] == "PASS" else "❌"
        lines.append(f"[{status_icon}] {check_name.replace('_', ' ').title()}")

        # Details
        if check_name.endswith("_format"):
            lines.append(f"  Valid: {result['valid']}/{result['total']}")
            if result['invalid'] > 0:
                lines.append(f"  ⚠️ Invalid: {result['invalid']}")

        elif check_name.endswith("_duplicate"):
            if result['duplicates']:
                lines.append(f"  ⚠️ Duplicates found: {result['duplicates']}")

        elif check_name.endswith("_missing"):
            if result['missing'] > 0:
                lines.append(f"  ⚠️ Missing IDs: {result['missing']}/{result['total']}")

        elif check_name.endswith("_match"):
            lines.append(f"  Matched: {result['matched']}/{result['total']}")
            if result['unmatched'] > 0:
                lines.append(f"  ⚠️ Unmatched: {result['unmatched']}")
            if result['empty'] > 0:
                lines.append(f"  Empty (expected): {result['empty']}")

        elif check_name == "cross_media_collision":
            if result['collisions']:
                lines.append(f"  ⚠️ Collisions: {result['collisions']}")

        lines.append("")

    # Error details
    if report.errors:
        lines.append("=" * 60)
        lines.append("Error Details:")
        lines.append("=" * 60)

        for i, error in enumerate(report.errors, 1):
            lines.append(f"\n[Error #{i}] {error.error_type.value}")
            lines.append(f"  Entity: {error.entity_type}")
            lines.append(f"  ID: {error.entity_id}")
            lines.append(f"  Expected: {error.expected}")
            lines.append(f"  Actual: {error.actual}")
            lines.append(f"  Detail: {error.detail}")
            if error.source:
                lines.append(f"  Source: {error.source}")
            if error.page is not None:
                lines.append(f"  Page: {error.page}")
            if error.bbox:
                lines.append(f"  BBox: {error.bbox}")

    lines.append("\n" + "=" * 60)
    lines.append(f"Summary: {report.total_errors} errors found")
    lines.append("=" * 60)

    return "\n".join(lines)


def format_json_report(report: AuditReport) -> str:
    """Format report as JSON"""
    report_dict = asdict(report)
    # Convert errors to dict
    report_dict['errors'] = [asdict(e) for e in report.errors]
    return json.dumps(report_dict, indent=2, ensure_ascii=False)


def format_csv_report(report: AuditReport) -> str:
    """Format report as CSV"""
    from io import StringIO
    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Error_Type", "Entity_Type", "Entity_ID", "Expected", "Actual",
        "Detail", "Source", "Page", "BBox"
    ])

    # Rows
    for error in report.errors:
        writer.writerow([
            error.error_type.value,
            error.entity_type,
            error.entity_id,
            error.expected,
            error.actual,
            error.detail,
            error.source or "",
            error.page if error.page is not None else "",
            str(error.bbox) if error.bbox else ""
        ])

    return output.getvalue()


def save_report(report: AuditReport, format_type: str, output_dir: Path):
    """Save report to file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if format_type == "json":
        output_file = output_dir / f"audit_ids_{timestamp}.json"
        content = format_json_report(report)
    elif format_type == "csv":
        output_file = output_dir / f"audit_ids_{timestamp}.csv"
        content = format_csv_report(report)
    else:
        output_file = output_dir / f"audit_ids_{timestamp}.txt"
        content = format_console_report(report)

    output_file.write_text(content, encoding="utf-8")
    print(f"\n✅ Report saved: {output_file}")
    return output_file


def main():
    """Main entry point for CLI usage"""
    import argparse

    parser = argparse.ArgumentParser(description="ID Integrity Audit Tool")
    parser.add_argument("--format", choices=["console", "json", "csv"], default="console",
                        help="Output format (default: console)")
    parser.add_argument("--output-dir", type=str, default="exports",
                        help="Output directory for reports (default: exports)")
    parser.add_argument("--test", action="store_true",
                        help="Run with dummy test data")

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)

    if args.test:
        # Run with dummy test data
        from dataclasses import dataclass

        @dataclass
        class DummyRegion:
            area_code: str
            rect: tuple
            page: int = 0

        @dataclass
        class DummySyncPair:
            web_id: str
            pdf_id: str

        # Create test data
        web_regions = [
            DummyRegion("W-001", (100, 200, 500, 250)),
            DummyRegion("W-002", (100, 300, 500, 350)),
            DummyRegion("W-003", (100, 400, 500, 450)),
        ]

        pdf_regions = [
            DummyRegion("P-001", (120, 180, 480, 230)),
            DummyRegion("P-002", (120, 280, 480, 330)),
            DummyRegion("P-003", (120, 380, 480, 430)),
        ]

        sync_pairs = [
            DummySyncPair("W-001", "P-001"),
            DummySyncPair("W-002", "P-002"),
            DummySyncPair("W-003", "P-003"),
        ]

        print("Running with test data...")

    else:
        print("❌ Error: Live data mode not implemented")
        print("💡 Hint: Use --test flag for testing, or integrate with your application")
        print("\nIntegration Example:")
        print("  from OCR.scripts.audit_ids import IDAuditor")
        print("  auditor = IDAuditor()")
        print("  report = auditor.audit(sync_pairs, web_regions, pdf_regions)")
        sys.exit(1)

    # Run audit
    auditor = IDAuditor()
    report = auditor.audit(sync_pairs, web_regions, pdf_regions)

    # Output
    if args.format == "console":
        print(format_console_report(report))
    elif args.format == "json":
        print(format_json_report(report))
    elif args.format == "csv":
        print(format_csv_report(report))

    # Save report
    save_report(report, args.format, output_dir)

    # Exit code
    sys.exit(0 if report.status == "PASS" else 1)


if __name__ == "__main__":
    main()
