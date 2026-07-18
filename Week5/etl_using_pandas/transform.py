import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

NORTHEAST = {
    "Connecticut", "Maine", "Massachusetts", "New Hampshire", "New Jersey",
    "New York", "Pennsylvania", "Rhode Island", "Vermont",
}
MIDWEST = {
    "Illinois", "Indiana", "Iowa", "Kansas", "Michigan", "Minnesota",
    "Missouri", "Nebraska", "North Dakota", "Ohio", "South Dakota", "Wisconsin",
}
SOUTH = {
    "Alabama", "Arkansas", "Delaware", "Florida", "Georgia", "Kentucky",
    "Louisiana", "Maryland", "Mississippi", "North Carolina", "Oklahoma",
    "South Carolina", "Tennessee", "Texas", "Virginia", "West Virginia",
}
WEST = {
    "Alaska", "Arizona", "California", "Colorado", "Hawaii", "Idaho",
    "Montana", "Nevada", "New Mexico", "Oregon", "Utah", "Washington", "Wyoming",
}

VALID_STATUS = {"completed", "cancelled", "no_show"}


def derive_driver_dim(driver_df: pd.DataFrame) -> pd.DataFrame:
    df = driver_df.copy()
    now = pd.Timestamp.now()
    conditions = [
        df["joined_at"] >= now - pd.DateOffset(months=6),
        df["joined_at"] >= now - pd.DateOffset(years=1),
        df["joined_at"] >= now - pd.DateOffset(years=2),
    ]
    choices = ["0-6 months", "6-12 months", "1-2 years"]
    df["tenure_bucket"] = np.select(conditions, choices, default="2+ years")
    return df


def derive_passenger_dim(passenger_df: pd.DataFrame) -> pd.DataFrame:
    df = passenger_df.copy()
    df["cohort_month"] = df["created_at"].dt.strftime("%Y-%m")
    return df


def derive_location_dim(location_df: pd.DataFrame) -> pd.DataFrame:
    df = location_df.copy()
    conditions = [
        df["country"] != "USA",
        df["state_province"].isin(NORTHEAST),
        df["state_province"].isin(MIDWEST),
        df["state_province"].isin(SOUTH),
        df["state_province"].isin(WEST),
    ]
    choices = ["International", "Northeast", "Midwest", "South", "West"]
    df["region"] = np.select(conditions, choices, default="International")
    return df


def _drop_unmatched(df: pd.DataFrame, key_col: str, label: str) -> pd.DataFrame:
    missing = df[key_col].isna()
    if missing.any():
        logger.warning(f"{missing.sum()} trip(s) missing {label} — skipped")
    return df[~missing]


FACT_COLUMNS = [
    "source_trip_id", "date_key", "driver_key", "passenger_key",
    "pickup_location_key", "dropoff_location_key",
    "payment_method_key", "promo_code_key",
    "base_fare", "tip_amount", "discount_amount", "fare_amount",
    "distance_km", "status", "duration_minutes",
    "driver_rating", "passenger_rating",
    "surge_multiplier", "requested_at",
]


def transform_trips(trips_df: pd.DataFrame, lookups: dict) -> pd.DataFrame:
    if trips_df.empty:
        logger.info("No trips extracted — nothing to transform")
        # Empty input still needs the output schema — quality.py and load.py
        # index into columns like fare_amount/driver_key unconditionally.
        return pd.DataFrame(columns=FACT_COLUMNS)

    initial_count = len(trips_df)
    df = trips_df.copy()

    df["date_key"] = df["requested_at"].dt.strftime("%Y%m%d").astype(int)
    df = df[df["date_key"].isin(lookups["date"]["date_key"])]
    if len(df) < initial_count:
        logger.warning(f"{initial_count - len(df)} trip(s) outside of dim_date range — skipped")

    df = df.merge(lookups["driver"], on="driver_id", how="left")
    df = _drop_unmatched(df, "driver_key", "driver_key (dim_driver)")

    df = df.merge(lookups["passenger"], on="passenger_id", how="left")
    df = _drop_unmatched(df, "passenger_key", "passenger_key (dim_passenger)")

    pickup_lookup = lookups["location"].rename(
        columns={"location_id": "pickup_location_id", "location_key": "pickup_location_key"}
    )
    df = df.merge(pickup_lookup, on="pickup_location_id", how="left")
    df = _drop_unmatched(df, "pickup_location_key", "pickup_location_key (dim_location)")

    dropoff_lookup = lookups["location"].rename(
        columns={"location_id": "dropoff_location_id", "location_key": "dropoff_location_key"}
    )
    df = df.merge(dropoff_lookup, on="dropoff_location_id", how="left")
    df = _drop_unmatched(df, "dropoff_location_key", "dropoff_location_key (dim_location)")

    # payment_method_id / promo_code_id are nullable in trips (e.g. no_show trips
    # have no payment method) and fact_trips allows NULL for both — a row is only
    # dropped when the OLTP row *has* a value that the merge failed to resolve.
    df = df.merge(lookups["payment_method"], on="payment_method_id", how="left")
    bad_pm = df["payment_method_id"].notna() & df["payment_method_key"].isna()
    if bad_pm.any():
        logger.warning(f"{bad_pm.sum()} trip(s) with unknown payment_method_id — skipped")
    df = df[~bad_pm]

    df = df.merge(lookups["promo_code"], on="promo_code_id", how="left")
    bad_promo = df["promo_code_id"].notna() & df["promo_code_key"].isna()
    if bad_promo.any():
        logger.warning(f"{bad_promo.sum()} trip(s) with unknown promo_code_id — skipped")
    df = df[~bad_promo]

    for col in ("driver_key", "passenger_key", "pickup_location_key",
                "dropoff_location_key", "payment_method_key", "promo_code_key"):
        df[col] = df[col].astype("Int64")

    df["base_fare"] = df["base_fare"].fillna(0)
    df["tip_amount"] = df["tip_amount"].fillna(0)
    df["surge_multiplier"] = df["surge_multiplier"].fillna(0)
    df["discount_amount"] = df["discount_amount"].fillna(0)
    df["fare_amount"] = (
        df["base_fare"] * df["surge_multiplier"] + df["tip_amount"] - df["discount_amount"]
    ).round(2)

    completed = (df["status"] == "completed") & df["completed_at"].notna()
    df["duration_minutes"] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df.loc[completed, "duration_minutes"] = (
        (df.loc[completed, "completed_at"] - df.loc[completed, "requested_at"]).dt.total_seconds() / 60
    ).round(1)

    df = df.rename(columns={"trip_id": "source_trip_id"})
    result = df[FACT_COLUMNS].reset_index(drop=True)

    logger.info(f"Transformed {len(result)} rows, skipped {initial_count - len(result)}")
    return result
