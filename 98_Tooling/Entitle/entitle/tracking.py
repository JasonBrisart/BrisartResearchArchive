"""
File: entitle/tracking.py

Purpose
-------
Record where Entitle-managed software is deployed and where it came from. Deployments are
  governed: one is recorded only if the entitlement verifies, grants can_run, is not revoked and
  has room under its deployment limit. Forks and provenance are documentary and are always
  recorded when their fields are filled in, so lineage is never lost to a policy check.

Communication / relationships
-----------------------------
Imports entitle/common.py (require_text), entitle/entitlements.py (verify_entitlement),
  entitle/records.py (the deployment, fork and provenance record types) and entitle/revoke.py
  (is_revoked); the RecordStore is passed in by the caller. Imported by cli.py (track deploy,
  fork and provenance) and gui/tabs.py (Deploy and Fork / Provenance tabs). Listing records is
  RecordStore.filter, called directly. Covered by tests/test_tracking.py.

Settings / parameters
---------------------
deploy_from_file(issuer, subject, product, master_key, entitlement_path, host, store,
  environment=None, notes=None) verifies the file and then calls register_deployment(store,
  entitlement, host, environment=None, notes=None), which takes an already verified
  EntitlementResult. The limit is rights.deployment_limit (None means unlimited), counted per
  product, subject and entitlement_id. record_fork(store, product, source_version, fork_name,
  maintainer, environment=None, notes=None) and record_provenance(store, product, origin,
  version, custodian, previous_version=None, notes=None) append and return one record.

Edge cases
----------
Refusals are returned, never raised, and write nothing: {"recorded": False, "reason": ...} with
  entitlement_denied:<reason>, run_right_not_granted, entitlement_revoked or
  deployment_limit_reached (which also reports deployment_limit and deployments_used). The
  revocation check, the count and the append run in one store transaction, so concurrent
  deployments from any number of processes cannot exceed the limit. The file is verified before
  the lock is taken, so encryption never holds the store. If 97_Encryption cannot be linked,
  deploy_from_file raises EncryptionNotFoundError before touching the store. Files written by
  the previous encryption deploy like current ones. A blank host, or a blank required fork or
  provenance field, raises ValueError before anything is written.

Known limitations
-----------------
The host is whatever the caller types; nothing proves a deployment happened there. Deployments
  are counted, not de-duplicated, so recording the same host twice uses two of the limit, and a
  deployment cannot be released. Fork and provenance records are not checked against any
  earlier record.

Examples
--------
From the directory containing run.py:

    from tempfile import TemporaryDirectory
    from entitle.records import RecordStore
    from entitle.rights import EntitlementResult
    from entitle.tracking import register_deployment

    entitlement = EntitlementResult.allowed_result({
        "product_id": "Demo", "subject_id": "Lab", "issuer_id": "Issuer", "entitlement_id": "e-1",
        "rights": {"can_run": True, "deployment_limit": 1},
    })
    with TemporaryDirectory() as folder:
        store = RecordStore(f"{folder}/entitle_records.log")
        assert register_deployment(store, entitlement, host="node-1")["recorded"]
        refused = register_deployment(store, entitlement, host="node-2")
        assert refused["reason"] == "deployment_limit_reached"
"""

from .common import require_text
from .entitlements import verify_entitlement
from .records import (
    RECORD_TYPE_DEPLOYMENT,
    RECORD_TYPE_FORK,
    RECORD_TYPE_PROVENANCE,
)
from .revoke import is_revoked


def count_deployments(store, product_id, subject_id, entitlement_id):
    def matches(record):
        data = record["data"]
        return (
            data.get("product_id") == product_id
            and data.get("subject_id") == subject_id
            and data.get("entitlement_id") == entitlement_id
        )

    return len(store.filter(record_type=RECORD_TYPE_DEPLOYMENT, predicate=matches))


def _refused(reason, **details):
    return {"recorded": False, "reason": reason, "record": None, **details}


def register_deployment(store, entitlement, host, environment=None, notes=None):
    require_text(host=host)
    if not entitlement.allowed:
        return _refused(f"entitlement_denied:{entitlement.reason}")
    if not entitlement.has_right("can_run"):
        return _refused("run_right_not_granted")
    product_id = entitlement.payload.get("product_id")
    subject_id = entitlement.payload.get("subject_id")
    entitlement_id = entitlement.payload.get("entitlement_id")
    limit = entitlement.get_limit("deployment_limit", default=1)
    with store.transaction():
        if is_revoked(store, entitlement_id):
            return _refused("entitlement_revoked")
        used = count_deployments(store, product_id, subject_id, entitlement_id)
        if limit is not None and used >= limit:
            return _refused("deployment_limit_reached", deployment_limit=limit, deployments_used=used)
        record = store.append(
            RECORD_TYPE_DEPLOYMENT,
            {
                "product_id": product_id,
                "subject_id": subject_id,
                "issuer_id": entitlement.payload.get("issuer_id"),
                "entitlement_id": entitlement_id,
                "host": host,
                "environment": environment,
                "notes": notes,
            },
        )
    return {
        "recorded": True,
        "reason": "deployment_recorded",
        "record": record,
        "deployment_limit": limit,
        "deployments_used": used + 1,
    }


def deploy_from_file(*, issuer, subject, product, master_key, entitlement_path, host, store, environment=None, notes=None):
    entitlement = verify_entitlement(
        issuer=issuer, subject=subject, product=product, master_key=master_key, path=entitlement_path,
    )
    return register_deployment(store, entitlement, host=host, environment=environment, notes=notes)


def record_fork(store, *, product, source_version, fork_name, maintainer, environment=None, notes=None):
    require_text(product=product, source_version=source_version, fork_name=fork_name, maintainer=maintainer)
    return store.append(
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


def record_provenance(store, *, product, origin, version, custodian, previous_version=None, notes=None):
    require_text(product=product, origin=origin, version=version, custodian=custodian)
    return store.append(
        RECORD_TYPE_PROVENANCE,
        {
            "product_id": product,
            "origin": origin,
            "version": version,
            "previous_version": previous_version,
            "custodian": custodian,
            "notes": notes,
        },
    )
