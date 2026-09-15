import pandas as pd
from app.preflight import identity_set, protected_count


def test_preflight_reports_aggregate_counts():
    assert protected_count(4) == {"value": 4, "suppressed": False}
    assert protected_count(5) == {"value": 5, "suppressed": False}
    assert protected_count(0) == {"value": 0, "suppressed": False}


def test_identity_reconciliation_ignores_empty_cells():
    df = pd.DataFrame({"Student_ID_anonymised": [None, "", "  ", " test ", "test"]})
    assert identity_set(df) == {"test"}
