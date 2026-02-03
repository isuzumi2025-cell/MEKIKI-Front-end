"""
schema_validator.py - Schema Validation for MatchResult (Phase 1.2)

Purpose: Validate MatchResult schema integrity and detect errors

Error Classifications:
- MISSING_FIELD: Required field is missing
- INVALID_BBOX: BBox is out of range or invalid
- INVALID_PAGE: Page index is out of range
- INVALID_SCORE: Score is out of valid range [0.0, 1.0]
- INVALID_ID_FORMAT: ID format doesn't match expected pattern
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re

from .match_schema import MatchResult, MatchEntity, BBox


class ValidationErrorType(str, Enum):
    """Validation error types"""
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_BBOX = "INVALID_BBOX"
    INVALID_PAGE = "INVALID_PAGE"
    INVALID_SCORE = "INVALID_SCORE"
    INVALID_ID_FORMAT = "INVALID_ID_FORMAT"
    BBOX_OUT_OF_RANGE = "BBOX_OUT_OF_RANGE"
    PAGE_OUT_OF_RANGE = "PAGE_OUT_OF_RANGE"


@dataclass
class ValidationError:
    """Represents a single validation error"""
    error_type: ValidationErrorType
    field_path: str  # e.g., "web.bbox.x1"
    expected: str
    actual: str
    detail: str
    severity: str = "ERROR"  # "ERROR" | "WARNING"


@dataclass
class ValidationResult:
    """Result of schema validation"""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]

    @property
    def total_issues(self) -> int:
        return len(self.errors) + len(self.warnings)


class MatchSchemaValidator:
    """
    Validator for MatchResult schema

    Validates:
    - Required fields
    - BBox ranges (must be within image dimensions)
    - Page ranges (must be within document page count)
    - Score ranges (0.0-1.0)
    - ID formats (W-XXX, P-XXX)
    """

    # ID format patterns
    WEB_ID_PATTERN = re.compile(r'^W-\d{3}$')
    PDF_ID_PATTERN = re.compile(r'^P-\d{3}$')
    SEL_ID_PATTERN = re.compile(r'^SEL_\d{3}$')

    def __init__(
        self,
        web_image_size: Optional[Tuple[int, int]] = None,
        pdf_image_size: Optional[Tuple[int, int]] = None,
        web_page_count: Optional[int] = None,
        pdf_page_count: Optional[int] = None
    ):
        """
        Initialize validator with context

        Args:
            web_image_size: (width, height) of web image for bbox validation
            pdf_image_size: (width, height) of pdf image for bbox validation
            web_page_count: Total number of web pages
            pdf_page_count: Total number of pdf pages
        """
        self.web_image_size = web_image_size
        self.pdf_image_size = pdf_image_size
        self.web_page_count = web_page_count
        self.pdf_page_count = pdf_page_count

    def validate(self, match: MatchResult) -> ValidationResult:
        """
        Validate a MatchResult

        Args:
            match: MatchResult to validate

        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []

        # Validate required fields
        if not match.match_id:
            errors.append(ValidationError(
                error_type=ValidationErrorType.MISSING_FIELD,
                field_path="match_id",
                expected="non-empty string",
                actual="None or empty",
                detail="match_id is required"
            ))

        # Validate web entity
        if match.web is not None:
            web_errors, web_warnings = self._validate_entity(
                match.web, "web", self.web_image_size, self.web_page_count
            )
            errors.extend(web_errors)
            warnings.extend(web_warnings)

        # Validate pdf entity
        if match.pdf is not None:
            pdf_errors, pdf_warnings = self._validate_entity(
                match.pdf, "pdf", self.pdf_image_size, self.pdf_page_count
            )
            errors.extend(pdf_errors)
            warnings.extend(pdf_warnings)

        # Validate score
        score_errors, score_warnings = self._validate_score(match.score)
        errors.extend(score_errors)
        warnings.extend(score_warnings)

        # Validate at least one entity present
        if match.web is None and match.pdf is None:
            errors.append(ValidationError(
                error_type=ValidationErrorType.MISSING_FIELD,
                field_path="web|pdf",
                expected="at least one of web or pdf",
                actual="both None",
                detail="MatchResult must have at least one entity"
            ))

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _validate_entity(
        self,
        entity: MatchEntity,
        prefix: str,
        image_size: Optional[Tuple[int, int]],
        page_count: Optional[int]
    ) -> Tuple[List[ValidationError], List[ValidationError]]:
        """Validate a MatchEntity"""
        errors = []
        warnings = []

        # Validate source_id
        if not entity.source_id:
            errors.append(ValidationError(
                error_type=ValidationErrorType.MISSING_FIELD,
                field_path=f"{prefix}.source_id",
                expected="non-empty string",
                actual="None or empty",
                detail=f"{prefix}.source_id is required"
            ))
        else:
            # Validate ID format
            pattern = self.WEB_ID_PATTERN if prefix == "web" else self.PDF_ID_PATTERN
            if not pattern.match(entity.source_id) and not self.SEL_ID_PATTERN.match(entity.source_id):
                warnings.append(ValidationError(
                    error_type=ValidationErrorType.INVALID_ID_FORMAT,
                    field_path=f"{prefix}.source_id",
                    expected=f"{'W' if prefix == 'web' else 'P'}-XXX format",
                    actual=entity.source_id,
                    detail=f"ID format doesn't match expected pattern",
                    severity="WARNING"
                ))

        # Validate page
        if entity.page < 0:
            errors.append(ValidationError(
                error_type=ValidationErrorType.INVALID_PAGE,
                field_path=f"{prefix}.page",
                expected="page >= 0",
                actual=str(entity.page),
                detail="Page index cannot be negative"
            ))

        if page_count is not None and entity.page >= page_count:
            errors.append(ValidationError(
                error_type=ValidationErrorType.PAGE_OUT_OF_RANGE,
                field_path=f"{prefix}.page",
                expected=f"page < {page_count}",
                actual=str(entity.page),
                detail=f"Page index {entity.page} exceeds page count {page_count}"
            ))

        # Validate bbox
        if entity.bbox is None:
            errors.append(ValidationError(
                error_type=ValidationErrorType.MISSING_FIELD,
                field_path=f"{prefix}.bbox",
                expected="BBox object",
                actual="None",
                detail=f"{prefix}.bbox is required"
            ))
        else:
            bbox_errors, bbox_warnings = self._validate_bbox(
                entity.bbox, f"{prefix}.bbox", image_size
            )
            errors.extend(bbox_errors)
            warnings.extend(bbox_warnings)

        # Validate text
        if not entity.text and entity.text is not None:
            warnings.append(ValidationError(
                error_type=ValidationErrorType.MISSING_FIELD,
                field_path=f"{prefix}.text",
                expected="non-empty string",
                actual="empty string",
                detail=f"{prefix}.text is empty (warning only)",
                severity="WARNING"
            ))

        return errors, warnings

    def _validate_bbox(
        self,
        bbox: BBox,
        field_path: str,
        image_size: Optional[Tuple[int, int]]
    ) -> Tuple[List[ValidationError], List[ValidationError]]:
        """Validate a BBox"""
        errors = []
        warnings = []

        # Validate bbox coordinates are non-negative
        if bbox.x1 < 0 or bbox.y1 < 0 or bbox.x2 < 0 or bbox.y2 < 0:
            errors.append(ValidationError(
                error_type=ValidationErrorType.INVALID_BBOX,
                field_path=field_path,
                expected="all coordinates >= 0",
                actual=f"({bbox.x1}, {bbox.y1}, {bbox.x2}, {bbox.y2})",
                detail="BBox coordinates cannot be negative"
            ))

        # Validate bbox width and height are positive
        if bbox.width <= 0 or bbox.height <= 0:
            errors.append(ValidationError(
                error_type=ValidationErrorType.INVALID_BBOX,
                field_path=field_path,
                expected="width > 0, height > 0",
                actual=f"width={bbox.width}, height={bbox.height}",
                detail="BBox must have positive width and height"
            ))

        # Validate bbox is within image bounds
        if image_size is not None:
            img_width, img_height = image_size

            if bbox.x2 > img_width or bbox.y2 > img_height:
                errors.append(ValidationError(
                    error_type=ValidationErrorType.BBOX_OUT_OF_RANGE,
                    field_path=field_path,
                    expected=f"bbox within image ({img_width}x{img_height})",
                    actual=f"bbox=({bbox.x1}, {bbox.y1}, {bbox.x2}, {bbox.y2})",
                    detail=f"BBox exceeds image bounds"
                ))

            # Warning for bbox very close to edge (possible cropping issue)
            if bbox.x1 == 0 or bbox.y1 == 0 or bbox.x2 == img_width or bbox.y2 == img_height:
                warnings.append(ValidationError(
                    error_type=ValidationErrorType.INVALID_BBOX,
                    field_path=field_path,
                    expected="bbox not touching image edge",
                    actual=f"bbox=({bbox.x1}, {bbox.y1}, {bbox.x2}, {bbox.y2})",
                    detail="BBox touches image edge (possible cropping)",
                    severity="WARNING"
                ))

        return errors, warnings

    def _validate_score(
        self,
        score
    ) -> Tuple[List[ValidationError], List[ValidationError]]:
        """Validate a MatchScore"""
        errors = []
        warnings = []

        # Validate overall score
        if not (0.0 <= score.overall <= 1.0):
            errors.append(ValidationError(
                error_type=ValidationErrorType.INVALID_SCORE,
                field_path="score.overall",
                expected="0.0 <= score <= 1.0",
                actual=str(score.overall),
                detail="Overall score must be in [0.0, 1.0]"
            ))

        # Validate text score
        if not (0.0 <= score.text <= 1.0):
            errors.append(ValidationError(
                error_type=ValidationErrorType.INVALID_SCORE,
                field_path="score.text",
                expected="0.0 <= score <= 1.0",
                actual=str(score.text),
                detail="Text score must be in [0.0, 1.0]"
            ))

        # Validate confidence
        if not (0.0 <= score.confidence <= 1.0):
            errors.append(ValidationError(
                error_type=ValidationErrorType.INVALID_SCORE,
                field_path="score.confidence",
                expected="0.0 <= confidence <= 1.0",
                actual=str(score.confidence),
                detail="Confidence must be in [0.0, 1.0]"
            ))

        return errors, warnings


def validate_match_batch(
    matches: List[MatchResult],
    web_image_size: Optional[Tuple[int, int]] = None,
    pdf_image_size: Optional[Tuple[int, int]] = None,
    web_page_count: Optional[int] = None,
    pdf_page_count: Optional[int] = None
) -> Tuple[List[ValidationResult], int, int]:
    """
    Validate a batch of MatchResults

    Args:
        matches: List of MatchResult to validate
        web_image_size: Web image size for bbox validation
        pdf_image_size: PDF image size for bbox validation
        web_page_count: Web page count
        pdf_page_count: PDF page count

    Returns:
        Tuple of (results, total_errors, total_warnings)
    """
    validator = MatchSchemaValidator(
        web_image_size=web_image_size,
        pdf_image_size=pdf_image_size,
        web_page_count=web_page_count,
        pdf_page_count=pdf_page_count
    )

    results = []
    total_errors = 0
    total_warnings = 0

    for match in matches:
        result = validator.validate(match)
        results.append(result)
        total_errors += len(result.errors)
        total_warnings += len(result.warnings)

    return results, total_errors, total_warnings
