"""Read-only input reconciliation. Report aggregate diagnostics, never identity values."""
import hashlib
import json
from pathlib import Path

import pandas as pd

from app.config import Settings, PROJECT_ROOT

FILES = {
    "engagement": "Canvas Engagement_Final.xlsx",
    "assignment": "canvas_assignment_activity_all_courses_anonymised.xlsx",
    "badge": "Issuer Badge Awards - Annonymised 2.csv",
}
ID_COLUMN = "Student_ID_anonymised"
TARGET_NAMES = {"Understanding Treaty", "PBS: Autism Affirming Practice"}


def identity_set(frame):
    values = frame[ID_COLUMN].dropna().astype(str).str.strip()
    return set(values[values.ne("")])


def protected_count(value):
    value = int(value)
    return {"value": value, "suppressed": False}


def inspect_sources(root: Path):
    expected = json.loads((PROJECT_ROOT / "docs" / "raw-data.sha256.json").read_text())
    frames = {}
    integrity = {}
    for source, name in FILES.items():
        path = root / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        integrity[source] = digest == expected[name]
        frames[source] = pd.read_csv(path) if path.suffix == ".csv" else pd.read_excel(path)
    e, a, b = (frames[s] for s in ("engagement", "assignment", "badge"))
    es, ass = identity_set(e), identity_set(a)
    offering_e = e[["canvas_subject_id", "subject_code"]].drop_duplicates()
    offering_a = a[["course_canvas_id", "course_sis_id"]].drop_duplicates()
    pairs_e = set(map(tuple, offering_e.itertuples(index=False, name=None)))
    pairs_a = set(map(tuple, offering_a.itertuples(index=False, name=None)))
    target_badges = b[b["Badge Class Name"].isin(TARGET_NAMES)]
    dates = pd.to_datetime(e["start_date"], unit="D", origin="1899-12-30", errors="coerce")
    return {
        "read_only": True,
        "original_hashes_match": integrity,
        "rows": {s: protected_count(len(df)) for s, df in frames.items()},
        "students": {name: protected_count(n) for name, n in {
            "assignment": len(ass), "engagement": len(es), "intersection": len(ass & es),
            "assignment_only": len(ass - es), "engagement_only": len(es - ass),
        }.items()},
        "reconciliation_passed": len(ass) == 443 and len(es) == 385 and len(ass & es) == 385
            and len(ass - es) == 58 and len(pairs_a) == 9 and pairs_a == pairs_e,
        "matched_offerings": protected_count(len(pairs_a & pairs_e)),
        "diagnostics": {
            "assignment_missing_attempt_rows": protected_count(a["attempt"].isna().sum()),
            "assignment_zero_maximum_rows": protected_count(a["points_possible"].eq(0).sum()),
            "assignment_duplicate_student_assignment_rows": protected_count(a.duplicated([ID_COLUMN, "assignment_id"]).sum()),
            "target_badge_rows": protected_count(len(target_badges)),
            "target_badge_missing_identity_rows": protected_count(target_badges[ID_COLUMN].isna().sum()),
            "target_badge_revoked_rows": protected_count(target_badges["Revoked"].eq(True).sum()),
            "engagement_invalid_start_dates": protected_count(dates.isna().sum()),
        },
        "engagement_observed_dates": {
            "first": dates.min().date().isoformat(), "last": dates.max().date().isoformat(),
            "meaning": "Observed source dates; not confirmed offering start/end boundaries",
        },
        "import_requires": [
            "Convert Excel serial dates explicitly; confirm timezone before assigning UTC instants.",
            "Preserve missing attempt as unknown, never fabricate attempt 1.",
            "Preserve zero-point self-assessment items; do not divide by zero or apply weighted grading.",
            "Preserve both view and participation counts and first/last viewed timestamps.",
            "Resolve badges by course identity and unique Engagement membership; do not infer ambiguous offerings from dates.",
            "Use a project HMAC identity secret before persisting linked student identities.",
        ],
    }


def main():
    try:
        report = inspect_sources(Settings().raw_data_root)
        print(json.dumps(report, indent=2))
        print("Read-only preflight reconciliation " + ("passed." if report["reconciliation_passed"] else "failed."))
        return 0 if report["reconciliation_passed"] and all(report["original_hashes_match"].values()) else 1
    except Exception:
        print("Preflight failed; check source files and expected columns. Raw values were not printed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
