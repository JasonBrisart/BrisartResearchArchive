"""
Entitle Tracking — Deployments

Records *governed* deployments of Entitle-managed software into the shared
tamper-evident record store.

A deployment is only recorded if a valid Entitle entitlement grants ``can_run``,
the entitlement has not been revoked, and the entitlement's ``deployment_limit``
is not already reached. This is the only tracking concern that consults the
entitlement and the revocation history before writing; forks and provenance are
documentary and live in their own modules.
"""
from ..record_types import RECORD_TYPE_DEPLOYMENT
from ..records import RecordStore


def count_deployments(store, product_id, subject_id, entitlement_id):
    def matches(record):
        data = record.get("data", {})
        return (
            data.get("product_id") == product_id
            and data.get("subject_id") == subject_id
            and data.get("entitlement_id") == entitlement_id
        )

    return len(store.filter(record_type=RECORD_TYPE_DEPLOYMENT, predicate=matches))


def register_deployment(store, entitlement, host, environment=None, notes=None):
    """
    Record a deployment if the entitlement authorizes it.

    Returns a result dict describing whether the deployment was recorded, the
    reason, and (when recorded) the resulting record.
    """
    if not entitlement.allowed:
        return {
            "recorded": False,
            "reason": f"entitlement_denied:{entitlement.reason}",
            "record": None,
        }
    if not entitlement.has_right("can_run"):
        return {
            "recorded": False,
            "reason": "run_right_not_granted",
            "record": None,
        }
    product_id = entitlement.payload.get("product_id")
    subject_id = entitlement.payload.get("subject_id")
    entitlement_id = entitlement.payload.get("entitlement_id")

    from ..revoke import is_revoked
    if is_revoked(store, entitlement_id):
        return {
            "recorded": False,
            "reason": "entitlement_revoked",
            "record": None,
        }

    limit = entitlement.get_limit("deployment_limit", default=1)
    used = count_deployments(store, product_id, subject_id, entitlement_id)
    if limit is not None and used >= limit:
        return {
            "recorded": False,
            "reason": "deployment_limit_reached",
            "record": None,
            "deployment_limit": limit,
            "deployments_used": used,
        }

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


def deploy_from_file(
    *,
    issuer,
    subject,
    product,
    master_key,
    entitlement_path,
    host,
    store,
    environment=None,
    notes=None,
):
    """
    Verify a protected entitlement file and, if it authorizes it, record a
    governed deployment. Single source of truth used by both the CLI and the GUI.
    """
    from ..bsr_adapter import verify_protected_entitlement
    master_key_bytes = master_key if isinstance(master_key, bytes) else master_key.encode("utf-8")
    entitlement = verify_protected_entitlement(
        path=entitlement_path,
        master_key=master_key_bytes,
        expected_product_id=product,
        issuer_id=issuer,
        subject_id=subject,
    )
    record_store = RecordStore(store)
    return register_deployment(
        store=record_store,
        entitlement=entitlement,
        host=host,
        environment=environment,
        notes=notes,
    )
