"""Governed initialization within the existing installation receipt owner (FD-88A).

No second setup store or writer: all pending data is administrative provenance
in install.json. The canonical participation service remains the only writer.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import typing
from pathlib import Path

from span.shell.install.constants import INSTALL_VERSION
from span.shell.install.preflight import _repository_mapping
from span.shell.install.receipt import (
    publish_install_bytes,
    read_receipt,
    write_receipt,
)

if typing.TYPE_CHECKING:
    from span.core import model as m
    from span.shell.sqlite_store.functional_pyramid import (
        FunctionalPyramidInstallationStore,
    )

PENDING = "pending_governed_initialization"
ACCEPTED = "governed_initialization"
BOOTSTRAP = ".span/functional-pyramid.json"


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("invalid governed initialization receipt object")
    return dict(value)


def _array(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("invalid governed initialization receipt array")
    return list(value)


def _string(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("invalid governed initialization receipt identity")
    return value


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_bindings(value: object) -> tuple[m.AuthorityBinding, ...]:
    from span.core import model as m

    return tuple(m.from_canonical(m.AuthorityBinding, item) for item in _array(value))


def _existing_roots(data_dir: Path) -> dict[str, str]:
    from span.shell.readiness import probe_store

    roots: dict[str, str] = {}
    for path in sorted(data_dir.glob("*.db")):
        readiness = probe_store(data_dir, path.stem)
        if not readiness.ready or readiness.bound_root is None:
            raise ValueError(f"registered repository store is unavailable: {path.stem}")
        roots[path.stem] = readiness.bound_root
    return roots


def _bindings(data_dir: Path, repository_id: str) -> tuple[m.AuthorityBinding, ...]:
    from span.shell.readiness import installed_authority_bindings

    if not (data_dir / f"{repository_id}.db").exists():
        return ()
    raw = installed_authority_bindings(data_dir, repository_id)
    if raw is None:
        raise ValueError(f"registered authority unavailable: {repository_id}")
    return _canonical_bindings(raw)


@contextlib.contextmanager
def _state(
    data_dir: Path,
) -> typing.Iterator[FunctionalPyramidInstallationStore | None]:
    from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
    from span.shell.sqlite_store.functional_pyramid import (
        FunctionalPyramidInstallationStore,
        functional_pyramid_installation_path,
    )

    path = functional_pyramid_installation_path(data_dir)
    if not path.exists():
        yield None
        return
    with contextlib.closing(
        FunctionalPyramidInstallationStore(
            path, retention=DEFAULT_LIFECYCLE_RETENTION, read_only=True
        )
    ) as state:
        yield state


def _artifact_path(root: Path, locator: str) -> Path:
    path = root
    for part in locator.split("/"):
        if part in ("", ".", ".."):
            raise ValueError(f"noncanonical generated locator: {locator}")
        path = path / part
        if path.is_symlink():
            raise ValueError(f"symlink in generated artifact path: {path}")
    if path.exists() and not path.is_file():
        raise ValueError(f"generated artifact is not a regular file: {path}")
    return path


def _inspect_artifact(
    root: Path,
    locator: str,
    digest: str,
    known: dict[str, object],
    *,
    recovering: bool = False,
) -> None:
    path = _artifact_path(root, locator)
    if not path.exists():
        return
    actual = _digest(path.read_bytes())
    if known.get(locator) != actual and not (recovering and actual == digest):
        raise ValueError(f"unowned or modified generated artifact: {path}")
    if locator != BOOTSTRAP and actual != digest:
        raise ValueError(f"immutable generated declaration collision: {path}")


def _classify(roots: dict[str, Path], mapped: dict[str, str]) -> tuple[
    m.FunctionalPyramidClassification,
    dict[str, dict[str, object]],
    dict[m.FunctionalDocumentIdentity, str],
]:
    from span.core import functional_pyramid as fp
    from span.core import model as m
    from span.shell.filesystem_evidence import FilesystemEvidenceSource

    rows: list[m.FunctionalPyramidClassificationRow] = []
    entries: dict[str, dict[str, object]] = {}
    for repository_id, raw_path in sorted(mapped.items()):
        path = Path(raw_path).resolve(strict=True)
        raw = path.read_bytes()
        classification = fp.decode_functional_pyramid_classification(
            raw.decode("utf-8"), repository_id=repository_id
        )
        rows.extend(classification.rows)
        entries[repository_id] = {
            "root": str(roots[repository_id]),
            "classification": str(path),
            "classification_digest": _digest(raw),
        }
    combined = m.FunctionalPyramidClassification(rows=tuple(rows))
    fingerprints: dict[m.FunctionalDocumentIdentity, str] = {}
    for row in combined.rows:
        if row.repository_id not in mapped:
            raise ValueError(
                "canonical document owner is not a selected governed member"
            )
        identity = m.FunctionalDocumentIdentity(row.repository_id, row.document_ref)
        if identity not in fingerprints:
            source = FilesystemEvidenceSource(
                row.repository_id, str(roots[row.repository_id])
            )
            result = source.read_exact(
                row.repository_id, m.EvidenceRequest(row.document_ref), None
            )
            if isinstance(result, m.EvidenceSourceFailure):
                raise ValueError(f"classified document unavailable: {identity}")
            fingerprints[identity] = result.content_fingerprint
        if row.scope is not None:
            scope = (roots[row.declaring_repository_id] / row.scope).resolve()
            if (
                not scope.is_relative_to(roots[row.declaring_repository_id])
                or not scope.is_dir()
            ):
                raise ValueError(f"declared directory unavailable: {scope}")
    return combined, entries, fingerprints


def _artifacts(
    classification: m.FunctionalPyramidClassification,
) -> tuple[tuple[m.FunctionalPyramidMemberIntent, ...], dict[tuple[str, str], bytes]]:
    from span.core import functional_pyramid as fp
    from span.core import model as m

    derived = fp.derive_functional_pyramid_declarations(classification)
    members = fp.derive_functional_pyramid_member_intents(derived)
    artifacts = {
        (
            repository_id,
            fp.functional_pyramid_declaration_request(
                repository_id, declaration
            ).locator,
        ): fp.encode_functional_pyramid_declaration(repository_id, declaration)
        for repository_id, declaration in derived.declarations
    }
    for member in members:
        artifacts[(member.repository_id, BOOTSTRAP)] = (
            fp.encode_functional_pyramid_bootstrap(
                m.FunctionalPyramidBootstrap(
                    version=2, declaration_sources=member.declaration_sources
                )
            )
        )
    return members, artifacts


def _configuration(
    data_dir: Path,
    entries: dict[str, dict[str, object]],
    classification: m.FunctionalPyramidClassification,
    fingerprints: dict[m.FunctionalDocumentIdentity, str],
    accepted: dict[str, object],
    pending: dict[str, object] | None,
) -> None:
    from span.core import functional_pyramid as fp
    from span.core import model as m

    old: list[m.AuthorityBinding] = []
    owned: list[m.AuthorityBinding] = []
    for repository_id in entries:
        prior = _object(accepted.get(repository_id, {}))
        owned.extend(_canonical_bindings(prior.get("owned_bindings", [])))
        if pending is None:
            old.extend(_bindings(data_dir, repository_id))
        else:
            saved = _object(_object(pending["repositories"])[repository_id])
            old.extend(_canonical_bindings(saved["previous_bindings"]))
    bindings, newly_owned = fp.reconcile_functional_pyramid_bindings(
        classification,
        fingerprints=fingerprints,
        registered=tuple(old),
        previously_owned=tuple(owned),
    )
    for repository_id, entry in entries.items():

        def selected(items: typing.Iterable[m.AuthorityBinding]) -> list[object]:
            return [
                m.to_canonical(binding)
                for binding in items
                if binding.evidence_ref.repository_id == repository_id
            ]

        entry["previous_bindings"] = selected(old)
        entry["bindings"] = selected(bindings)
        entry["owned_bindings"] = selected(newly_owned)
        entry["documents"] = {
            identity.document_ref: digest
            for identity, digest in fingerprints.items()
            if identity.repository_id == repository_id
        }
        if pending is not None:
            current = set(_bindings(data_dir, repository_id))
            if current not in (
                set(_canonical_bindings(entry["previous_bindings"])),
                set(_canonical_bindings(entry["bindings"])),
            ):
                raise ValueError(f"recovery authority conflict: {repository_id}")


def _action(
    data_dir: Path,
    members: tuple[m.FunctionalPyramidMemberIntent, ...],
    entries: dict[str, dict[str, object]],
) -> tuple[m.FunctionalPyramidCandidateSelector | None, str | None, int | None]:
    from span.core import model as m

    selected = {member.repository_id for member in members}
    with _state(data_dir) as state:
        active = (
            set()
            if state is None
            else {
                pyramid_id
                for repository_id in selected
                if (pyramid_id := state.active_pyramid_id(repository_id)) is not None
            }
        )
        if not active:
            return (
                m.FunctionalPyramidCandidateSelector(
                    action=m.FunctionalPyramidAction.ACTIVATE, members=members
                ),
                None,
                None,
            )
        if len(active) != 1 or state is None:
            raise ValueError("governed initialization cannot merge active instances")
        pyramid_id = next(iter(active))
        assert pyramid_id is not None
        version = state.pyramid_version(pyramid_id)
        assert version is not None
        retained = state.pyramid_members(pyramid_id, version)
        if {item.repository_id for item in retained} != selected:
            raise ValueError(
                "governed initialization requires the complete active member set"
            )
        retained_refs = {
            (member.repository_id, ref.locator): ref.revision_or_fingerprint
            for member in retained
            for ref in member.declaration_refs
        }
        intended_refs = {
            (member.repository_id, request.locator): _object(
                entries[member.repository_id]["artifacts"]
            )[request.locator]
            for member in members
            for request in member.declaration_sources
        }
        changed = any(
            set(_canonical_bindings(entry["previous_bindings"]))
            != set(_canonical_bindings(entry["bindings"]))
            for entry in entries.values()
        )
        if retained_refs == intended_refs and not changed:
            return None, pyramid_id.value, version.value
        return (
            m.FunctionalPyramidCandidateSelector(
                action=m.FunctionalPyramidAction.REVISE,
                members=members,
                pyramid_id=pyramid_id,
                expected_version=version,
            ),
            pyramid_id.value,
            version.value,
        )


def prepare(
    data_dir: Path,
    targets: tuple[Path, ...],
    mappings: list[list[str]],
    binding_files: list[list[str]],
    prior: dict[str, object],
) -> tuple[dict[str, object], dict[tuple[str, str], bytes]]:
    """Validate exact input and recoverable intent before any setup mutation."""
    import uuid

    from span.core import model as m

    roots = {target.name: target for target in targets}
    if len(roots) != len(targets):
        raise ValueError("selected repositories must have distinct identities")
    mapped = _repository_mapping(
        mappings,
        selected_repository_ids=set(roots),
        label="Functional Pyramid classification",
    )
    if any(repository_id in mapped for repository_id, _ in binding_files):
        raise ValueError(
            "competing ordinary authority binding input for governed member"
        )
    registered = _existing_roots(data_dir)
    for repository_id, root in roots.items():
        if repository_id in registered and registered[repository_id] != str(root):
            raise ValueError(f"repository root conflict: {repository_id}")
    accepted = _object(prior.get(ACCEPTED, {}))
    pending_value = prior.get(PENDING)
    pending = None if pending_value is None else _object(pending_value)
    classification, entries, fingerprints = _classify(roots, mapped)
    members, artifacts = _artifacts(classification)
    _configuration(data_dir, entries, classification, fingerprints, accepted, pending)
    for repository_id, entry in entries.items():
        known = _object(
            _object(accepted.get(repository_id, {})).get("owned_artifacts", {})
        )
        planned = {
            locator: _digest(data)
            for (owner, locator), data in artifacts.items()
            if owner == repository_id
        }
        if pending is not None:
            saved = _object(_object(pending["repositories"])[repository_id])
            if saved.get("artifacts") != planned:
                raise ValueError("recovery conflict: derived artifacts differ")
        for locator, digest in planned.items():
            _inspect_artifact(
                roots[repository_id],
                locator,
                digest,
                known,
                recovering=pending is not None,
            )
        entry["artifacts"] = planned
        entry["prior_artifacts"] = known
        entry["owned_artifacts"] = {**known, **planned}
    if pending is not None:
        if pending.get("repositories") != entries or pending.get(
            "members"
        ) != m.to_canonical(members):
            raise ValueError("recovery conflict: pending governed input differs")
        _check_pending_participation(data_dir, pending, members)
        return pending, artifacts
    candidate, pyramid_id, version = _action(data_dir, members, entries)
    return {
        "repositories": entries,
        "members": m.to_canonical(members),
        "candidate": m.to_canonical(candidate),
        "request_id": f"governed:{uuid.uuid4().hex}" if candidate is not None else None,
        "prior_pyramid_id": pyramid_id,
        "prior_version": version,
    }, artifacts


def _check_pending_participation(
    data_dir: Path,
    pending: dict[str, object],
    members: tuple[m.FunctionalPyramidMemberIntent, ...],
) -> None:
    from span.core import model as m

    selected = {member.repository_id for member in members}
    with _state(data_dir) as state:
        raw = pending.get("request_id")
        accepted = (
            state.receipt(m.RequestId(_string(raw)))
            if state is not None and raw is not None
            else None
        )
        expected_id = pending.get("prior_pyramid_id")
        expected_version = pending.get("prior_version")
        if accepted is not None:
            if accepted.pyramid_id is None or accepted.version is None:
                raise ValueError("recovery conflict: invalid accepted participation")
            expected_id, expected_version = (
                accepted.pyramid_id.value,
                accepted.version.value,
            )
            if {member.repository_id for member in accepted.members} != selected:
                raise ValueError("recovery conflict: accepted membership differs")
        elif raw is not None and pending.get("accepted_pyramid_id") is not None:
            raise ValueError("recovery conflict: accepted receipt unavailable")
        if state is None:
            if expected_id is not None:
                raise ValueError("recovery conflict: installation state unavailable")
            return
        for repository_id in selected:
            actual = state.active_pyramid_id(repository_id)
            if (None if actual is None else actual.value) != expected_id:
                raise ValueError("recovery conflict: participation changed")
            if actual is not None:
                version = state.pyramid_version(actual)
                if version is None or version.value != expected_version:
                    raise ValueError("recovery conflict: participation version changed")
                if {
                    member.repository_id
                    for member in state.pyramid_members(actual, version)
                } != selected:
                    raise ValueError("recovery conflict: membership changed")


def retain_pending(
    data_dir: Path,
    prior: dict[str, object],
    pending: dict[str, object],
    backup: str | None,
) -> None:
    if PENDING not in prior:
        pending["backup"] = backup
    receipt = {
        "install_version": INSTALL_VERSION,
        "repos": [],
        "host_registration": {},
        **prior,
        PENDING: pending,
    }
    write_receipt(data_dir, receipt)


def publish(
    pending: dict[str, object],
    artifacts: dict[tuple[str, str], bytes],
    *,
    bootstrap: bool,
) -> None:
    for (repository_id, locator), data in sorted(artifacts.items()):
        if (locator == BOOTSTRAP) != bootstrap:
            continue
        entry = _object(_object(pending["repositories"])[repository_id])
        root = Path(_string(entry["root"]))
        _inspect_artifact(
            root,
            locator,
            _digest(data),
            _object(entry["prior_artifacts"]),
            recovering=True,
        )
        path = _artifact_path(root, locator)
        if path.exists() and path.read_bytes() == data:
            continue
        publish_install_bytes(path, data, replace=bootstrap and path.exists())


def bindings_for(
    pending: dict[str, object],
) -> dict[str, tuple[m.AuthorityBinding, ...]]:
    return {
        repository_id: _canonical_bindings(_object(entry)["bindings"])
        for repository_id, entry in _object(pending["repositories"]).items()
    }


def _changed_authorities(pending: dict[str, object]) -> tuple[m.EvidenceRef, ...]:
    entries = _object(pending["repositories"])
    refs: set[m.EvidenceRef] = set()
    for entry in entries.values():
        item = _object(entry)
        old = set(_canonical_bindings(item["previous_bindings"]))
        new = set(_canonical_bindings(item["bindings"]))
        refs.update(binding.evidence_ref for binding in old ^ new)
    return tuple(
        sorted(
            refs,
            key=lambda ref: (
                ref.repository_id,
                ref.evidence_id.value,
                ref.revision_or_fingerprint or "",
            ),
        )
    )


def establish(data_dir: Path, pending: dict[str, object]) -> None:
    """Use the same runtime and participation writer as MCP, including replay."""
    from span.core import model as m
    from span.shell.installation_runtime import open_installation_runtime

    members = tuple(
        m.from_canonical(m.FunctionalPyramidMemberIntent, item)
        for item in _array(pending["members"])
    )
    roots = _existing_roots(data_dir)
    raw = pending["candidate"]
    with open_installation_runtime(
        data_dir,
        repository_locator=roots.__getitem__,
        registered_repository_ids=lambda: tuple(sorted(roots)),
    ) as runtime:
        service = runtime.functional_pyramid
        if service is None:
            raise ValueError("Functional Pyramid installation store unavailable")
        if raw is not None:
            candidate = m.from_canonical(m.FunctionalPyramidCandidateSelector, raw)
            request_id = m.RequestId(_string(pending["request_id"]))
            existing = service.receipt(m.FunctionalPyramidReceiptSelector(request_id))
            if existing is None:
                validation = service.candidate(candidate)
                if not validation.activation_ready:
                    raise ValueError(f"governed candidate rejected: {validation}")
            else:
                for member in members:
                    status = service.status(
                        m.FunctionalPyramidSelector(repository_id=member.repository_id)
                    )
                    if (
                        status.pyramid_id != existing.pyramid_id
                        or status.version != existing.version
                    ):
                        raise ValueError(
                            "recovery conflict: accepted participation changed"
                        )
            recorded = service.record(
                request_id=request_id,
                action=candidate.action,
                members=candidate.members,
                pyramid_id=candidate.pyramid_id,
                expected_version=candidate.expected_version,
                changed_authority_refs=_changed_authorities(pending),
            )
            pyramid_id, version = recorded.pyramid_id, recorded.version
            pending["participation_result"] = m.to_canonical(recorded)
            print(json.dumps(pending["participation_result"], sort_keys=True))
        else:
            pyramid_id = m.FunctionalPyramidId(_string(pending["prior_pyramid_id"]))
            prior_version = pending["prior_version"]
            if type(prior_version) is not int:
                raise ValueError("invalid pending participation version")
            version = m.FunctionalPyramidVersion(prior_version)
        expected = {
            (member.repository_id, request.locator)
            for member in members
            for request in member.declaration_sources
        }
        for member in members:
            status = service.status(
                m.FunctionalPyramidSelector(repository_id=member.repository_id)
            )
            actual = {
                (item.repository_id, ref.locator)
                for item in status.members
                for ref in item.declaration_refs
            }
            if (
                status.state is not m.FunctionalPyramidParticipationState.ACTIVE
                or status.health is not m.FunctionalPyramidHealth.VALID
                or status.pyramid_id != pyramid_id
                or status.version != version
                or expected != actual
            ):
                raise ValueError(
                    f"governed participation verification failed: {member.repository_id}"
                )
        assert pyramid_id is not None and version is not None
        pending["accepted_pyramid_id"] = pyramid_id.value
        pending["accepted_version"] = version.value
    prior = read_receipt(data_dir)
    if prior is None:
        raise ValueError("pending installation receipt unavailable")
    write_receipt(data_dir, {**prior, PENDING: pending})


def finalize(
    receipt: dict[str, object],
    prior: dict[str, object],
    pending: dict[str, object] | None,
) -> None:
    """Promote verified administrative provenance, preserving historical ownership."""
    accepted = _object(prior.get(ACCEPTED, {}))
    if pending is not None:
        for repository_id, raw_entry in _object(pending["repositories"]).items():
            entry = _object(raw_entry)
            entry.pop("previous_bindings")
            entry.pop("prior_artifacts")
            old = _object(accepted.get(repository_id, {}))
            results = _array(old.get("participation_results", []))
            result = pending.get("participation_result")
            if result is not None and result not in results:
                results.append(result)
            entry["participation_results"] = results
            entry["pyramid_id"] = pending["accepted_pyramid_id"]
            entry["version"] = pending["accepted_version"]
            accepted[repository_id] = entry
    if accepted:
        receipt[ACCEPTED] = accepted
