"""Read-only plausibility audit; activity-hour patterns cannot prove a timezone."""
import json
import pandas as pd

from app.config import Settings


def main():
    frame = pd.read_excel(Settings().raw_data_root / "Canvas Engagement_Final.xlsx")
    results = {}
    for column in ("first_viewed", "last_viewed"):
        dates = pd.to_datetime(frame[column], unit="D", origin="1899-12-30").dt.round("ms")
        shifted = dates.dt.tz_localize("UTC").dt.tz_convert("Australia/Melbourne")
        results[column] = {
            "melbourne_assumption_07_to_22_pct": round(float(dates.dt.hour.between(7, 22).mean() * 100), 2),
            "utc_assumption_07_to_22_pct": round(float(shifted.dt.hour.between(7, 22).mean() * 100), 2),
        }
    start = pd.to_datetime(frame.start_date, unit="D", origin="1899-12-30")
    first = pd.to_datetime(frame.first_viewed, unit="D", origin="1899-12-30")
    results["start_date"] = {
        "all_midnight": bool(start.dt.normalize().eq(start).all()),
        "all_match_first_viewed_calendar_date": bool(start.dt.date.eq(first.dt.date).all()),
    }
    results["source_name_matches_subject_code"] = bool(frame["Source.Name"].eq(frame.subject_code + "_Canvas.csv").all())
    results["interpretation"] = "Retain Melbourne as provisional for naive engagement times; row-weighted evidence only."
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
