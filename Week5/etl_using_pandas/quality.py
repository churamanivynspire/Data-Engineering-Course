"""
quality.py
----------
Week 5 pipeline module (pandas) — Quality gate

Responsibilities:
  - Run data quality checks on the transformed fact DataFrame BEFORE load
  - Raise DataQualityError (halts pipeline) if any check fails
  - Log a quality summary even when all checks pass

The quality gate is the pipeline's immune system.
A loud failure here is far better than silent bad data in the warehouse.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


class DataQualityError(Exception):
    """
    Raised when a data quality check fails.
    Signals the pipeline to halt — nothing gets loaded.

    Include the check name and failure details in the message
    so on-call engineers can act without reading the code.
    """
    pass


def check_row_count(df: pd.DataFrame, min_rows: int = 1) -> dict:
    """Fail if the transformed row count is below a minimum threshold."""
    count = len(df)
    return {
        "check": "row_count",
        "passed": count >= min_rows,
        "detail": f"{count} rows (min: {min_rows})"
    }


def check_no_negative_fares(df: pd.DataFrame) -> dict:
    """Fail if any row has fare_amount <= 0."""
    bad = int((df["fare_amount"] < 0).sum())
    return {
        "check": "no_negative_fares",
        "passed": bad == 0,
        "detail": f"{bad} rows with fare_amount <= 0"
    }


def check_no_null_driver_keys(df: pd.DataFrame) -> dict:
    """Fail if any row is missing a driver_key."""
    bad = int(df["driver_key"].isna().sum())
    return {
        "check": "no_null_driver_keys",
        "passed": bad == 0,
        "detail": f"{bad} rows with NULL driver_key"
    }


def check_completed_have_duration(df: pd.DataFrame) -> dict:
    """Fail if any completed trip is missing duration_minutes."""
    bad = int(((df["status"] == "completed") & df["duration_minutes"].isna()).sum())
    return {
        "check": "completed_have_duration",
        "passed": bad == 0,
        "detail": f"{bad} completed trips with NULL duration_minutes"
    }


def check_valid_status(df: pd.DataFrame) -> dict:
    """Fail if any row has an unrecognised status value."""
    valid = {"completed", "cancelled", "no_show"}
    bad = int((~df["status"].isin(valid)).sum())
    return {
        "check": "valid_status",
        "passed": bad == 0,
        "detail": f"{bad} rows with invalid status"
    }


def run_quality_checks(df: pd.DataFrame) -> dict:
    """
    Run all quality checks on the transformed fact DataFrame.

    Returns a summary dict if all checks pass.
    Raises DataQualityError immediately on the first failure.

    Args:
        df: transformed fact rows from the transform layer

    Returns:
        {'passed': True, 'checks': [...check results...], 'row_count': N}

    Raises:
        DataQualityError: with details of the failing check
    """
    checks = [
        check_row_count(df),
        check_no_negative_fares(df),
        check_no_null_driver_keys(df),
        check_completed_have_duration(df),
        check_valid_status(df),
    ]

    failed = [c for c in checks if not c["passed"]]

    if failed:
        first = failed[0]
        raise DataQualityError(
            f"Quality check failed: {first['check']} — {first['detail']}"
        )

    summary = {
        "passed": True,
        "checks": checks,
        "row_count": len(df)
    }

    logger.info(f"Quality gate passed: {len(df):,} rows, {len(checks)} checks")
    for c in checks:
        logger.debug(f"  {c['check']}: {c['detail']}")

    return summary
