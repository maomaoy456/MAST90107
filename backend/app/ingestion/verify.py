"""Compare the latest normalized snapshot to its source without displaying raw values."""
from decimal import Decimal
import math

from sqlalchemy import select

from app.ingestion import adapters
from app.ingestion.normalize import identity
from app.ingestion.readers import ID, read_file
from app.ingestion.service import OBSERVATIONS, VERSIONS
from app.models import ImportBatch, Student


def equivalent(actual, expected):
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(equivalent(actual[k], expected[k]) for k in actual)
    if isinstance(actual, float) and isinstance(expected, float):
        # MySQL JSON double serialization can differ by an IEEE-754 rounding bit.
        # For Excel day serials this tolerance is < 0.01 ms, below stored timestamp precision.
        return math.isclose(actual, expected, rel_tol=0, abs_tol=1e-10)
    return actual == expected


def verify_file(factory, path, source, key):
    frame, digest = read_file(path, source)
    with factory() as session:
        batch = session.scalar(select(ImportBatch).where(ImportBatch.source == source,
            ImportBatch.file_sha256 == digest, ImportBatch.importer_version == VERSIONS[source],
            ImportBatch.status == "completed"))
        if batch is None:
            return False
        rows = {r.source_row: r for r in session.scalars(select(OBSERVATIONS[source]).where(
            OBSERVATIONS[source].batch_id == batch.id))}
        digests = {s.id: s.identity_digest for s in session.scalars(select(Student))}
        # A complete source verification should fail if any row was rejected.
        if len(rows) != len(frame):
            return False
        for row_number, raw in enumerate(frame.to_dict("records"), start=2):
            stored = rows.get(row_number)
            if stored is None or digests.get(stored.student_id) != identity(raw[ID], key):
                return False
            for name, expected in getattr(adapters, source)(raw).items():
                actual = getattr(stored, name)
                if isinstance(actual, Decimal) and expected is not None:
                    expected = Decimal(str(expected)).quantize(Decimal("0.0001"))
                if not equivalent(actual, expected):
                    return False
    return True
