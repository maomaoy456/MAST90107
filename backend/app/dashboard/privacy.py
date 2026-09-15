from app.dashboard.contracts import Metric, TableRow


def metric(value, students, reason=None):
    """Publish aggregate values; student identifiers never enter the contract."""
    if value is None:
        return Metric(reason="not_available")
    return Metric(value=round(float(value), 4) if isinstance(value, float) else value)


def partition(groups, *, reason=None):
    return [TableRow(key=key, label=label, metrics={"students": metric(len(members), members)})
            for key, label, members in groups]
