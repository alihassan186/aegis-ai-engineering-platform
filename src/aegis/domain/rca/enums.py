"""RCA finding, review, and version vocabulary (FR-033, FR-035)."""

from enum import StrEnum


class RcaFindingStatus(StrEnum):
    """What the model claims. Low confidence stays a hypothesis (FR-033)."""

    CONFIRMED = "confirmed"
    HYPOTHESIS = "hypothesis"


class RcaReviewStatus(StrEnum):
    """Human gate (FR-034). 4.8 persists pending_review; HTTP accept is 4.9."""

    PENDING_REVIEW = "pending_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class RcaVersionKind(StrEnum):
    """FR-035 versions are rows, not chat history."""

    ORIGINAL = "original"
    AMENDED = "amended"
