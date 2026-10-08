"""
Entitle Tracking — Forks

Records internal forks and custom distributions in the shared tamper-evident
record store.

Unlike deployments, a fork record is documentary: it captures software lineage
(source version, fork name, maintainer, environment) and does not consult an
entitlement or the revocation history. It is written unconditionally so the
record of what was forked, and by whom, is always preserved.
"""
from ..record_types import RECORD_TYPE_FORK
from ..records import RecordStore


def record_fork(*, store, product, source_version, fork_name, maintainer, environment=None, notes=None):
    record_store = RecordStore(store)
    return record_store.append(
        RECORD_TYPE_FORK,
        {
            "product_id": product,
            "source_version": source_version,
            "fork_name": fork_name,
            "maintainer": maintainer,
            "environment": environment,
            "notes": notes,
        },
    )
