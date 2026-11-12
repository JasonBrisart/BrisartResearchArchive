"""
File: entitle/tracking.py

Purpose
-------
Record where Entitle-managed software is deployed and where it came from. Deployments are
  governed seats: one is recorded only if the entitlement verifies, grants can_run, is not
  revoked, the host does not already hold a seat, and a seat is free under the deployment
  limit; releasing a host gives its seat back. Forks and provenance are documentary and are
  always recorded when their fields are filled in, so lineage is never lost to a policy check.

Communication / relationships
-----------------------------
Imports entitle/common.py (require_identifier, require_text), entitle/entitlements.py
  (verify_entitlement), entitle/records.py (the deployment, release, fork and provenance record
  types) and entitle/revoke.py (is_revoked); the RecordStore is passed in. Imported by cli.py
  (track deploy, release, fork and provenance) and gui/tabs.py (Deploy and Fork / Provenance
  tabs). Covered by tests/test_tracking.py.

Settings / parameters
---------------------
deploy_from_file(issuer, subject, product, entitlement_path, host, store, master_key=None,
  public_keys=None, revocation_list=None, environment=None, notes=None) verifies the file and
  calls register_deployment(store, entitlement, host, environment=None, notes=None), which takes
  an already verified EntitlementResult. release_deployment(store, product, subject,
  entitlement_id, host, reason=None) frees a seat. active_hosts() returns {host: seats held},
  deployments minus releases, per product, subject and entitlement_id; count_deployments() is
  their sum. The limit is rights.deployment_limit (None is unlimited).

Edge cases
----------
Refusals are returned, never raised, and write nothing: {"recorded": False, "reason": ...} with
  entitlement_denied:<reason>, run_right_not_granted, entitlement_revoked,
  already_deployed_on_host or deployment_limit_reached (the last two also report
  deployment_limit and deployments_used); a release of a host that holds no seat returns
  {"released": False, "reason": "no_active_deployment_on_host"}. The revocation check, the seat
  count and the append run in one store transaction, so concurrent deployments and releases from
  any number of processes cannot exceed the limit. The file is verified before the lock is
  taken. A deployment from a signed file records the signing key ID. A host or entitlement ID
  with spaces at either end, and a blank required field, raise ValueError before anything is
  written. Logs written before 0.7.0 have no release records; every deployment in them counts.

Known limitations
-----------------
The host is whatever the caller types; nothing proves a deployment happened there or that a
  released host stopped running the software. A seat is held until it is released: there is no
  lease that expires on its own, because that needs a server. Fork and provenance records are
  not checked against earlier records.

Examples
--------
From the directory containing run.py:

    from tempfile import TemporaryDirectory
    from entitle.records import RecordStore
    from entitle.rights import EntitlementResult
    from entitle.tracking import register_deployment, release_deployment

    entitlement = EntitlementResult.allowed_result({
        "product_id": "Demo", "subject_id": "Lab", "issuer_id": "Issuer", "entitlement_id": "e-1",
        "rights": {"can_run": True, "deployment_limit": 1},
    })
    with TemporaryDirectory() as folder:
        store = RecordStore(f"{folder}/entitle_records.log")
        assert register_deployment(store, entitlement, host="node-1")["recorded"]
        refused = register_deployment(store, entitlement, host="node-2")
        assert refused["reason"] == "deployment_limit_reached"
        release_deployment(store, product="Demo", subject="Lab", entitlement_id="e-1",
                           host="node-1")
        assert register_deployment(store, entitlement, host="node-2")["recorded"]
"""

from .common import require_identifier, require_text
from .entitlements import verify_entitlement
from .records import (
    RECORD_TYPE_DEPLOYMENT,
    RECORD_TYPE_FORK,
    RECORD_TYPE_PROVENANCE,
    RECORD_TYPE_RELEASE,
)
from .revoke import is_revoked


def _matches(product_id, subject_id, entitlement_id):
    def matches(record):
        data = record["data"]
        return (
            data.get("product_id") == product_id
            and data.get("subject_id") == subject_id
            and data.get("entitlement_id") == entitlement_id
        )

    return matches


def active_hosts(store, product_id, subject_id, entitlement_id):
    """{host: active deployments on it}: deployments minus releases, for one entitlement."""
    active = {}
    matches = _matches(product_id, subject_id, entitlement_id)
    for record in store.read_all():
        if not matches(record):
            continue
        host = record["data"].get("host")
        if record.get("record_type") == RECORD_TYPE_DEPLOYMENT:
            active[host] = active.get(host, 0) + 1
        elif record.get("record_type") == RECORD_TYPE_RELEASE and active.get(host, 0) > 0:
            active[host] -= 1
    return {host: count for host, count in active.items() if count > 0}


def count_deployments(store, product_id, subject_id, entitlement_id):
    """Seats in use: deployments not yet released."""
    return sum(active_hosts(store, product_id, subject_id, entitlement_id).values())


def _refused(reason, **details):
    return {"recorded": False, "reason": reason, "record": None, **details}


def register_deployment(store, entitlement, host, environment=None, notes=None):
    require_identifier(host=host)
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
        hosts = active_hosts(store, product_id, subject_id, entitlement_id)
        used = sum(hosts.values())
        if host in hosts:
            return _refused("already_deployed_on_host", deployment_limit=limit, deployments_used=used)
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
                **({"signed_by": entitlement.signed_by} if getattr(entitlement, "signed_by", None) else {}),
            },
        )
    return {
        "recorded": True,
        "reason": "deployment_recorded",
        "record": record,
        "deployment_limit": limit,
        "deployments_used": used + 1,
    }


def release_deployment(store, *, product, subject, entitlement_id, host, reason=None):
    """Free the seat a host holds, so the entitlement can be deployed elsewhere."""
    require_text(product=product, subject=subject)
    require_identifier(entitlement_id=entitlement_id, host=host)
    with store.transaction():
        hosts = active_hosts(store, product, subject, entitlement_id)
        if host not in hosts:
            return {"released": False, "reason": "no_active_deployment_on_host", "record": None}
        record = store.append(
            RECORD_TYPE_RELEASE,
            {"product_id": product, "subject_id": subject, "entitlement_id": entitlement_id, "host": host,
             "reason": reason},
        )
    return {"released": True, "reason": "deployment_released", "record": record,
            "deployments_used": sum(hosts.values()) - 1}


def deploy_from_file(
    *, issuer, subject, product, entitlement_path, host, store, master_key=None, public_keys=None,
    revocation_list=None, environment=None, notes=None,
):
    entitlement = verify_entitlement(
        issuer=issuer, subject=subject, product=product, master_key=master_key, public_keys=public_keys,
        revocation_list=revocation_list, path=entitlement_path,
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
