"""Installation-scoped request addressing (FD-1/62).

Resolve typed path selections before repository services consume them.
Identity-bound selectors are not translated.
"""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import model as m
from span.core.recording import RecordingValidationError
from span.ports.evidence import RegisteredRepositoryRoots


class AddressingService:
    def __init__(self, roots: RegisteredRepositoryRoots) -> None:
        self._roots = roots

    def _locator(self, repository_id: str, locator: str) -> tuple[str, str]:
        path, separator, symbol = locator.partition(":")
        try:
            owner, relative = self._roots.resolve(repository_id, path)
        except ValueError as exc:
            raise RecordingValidationError(
                "path ownership cannot be resolved",
                public_identity=locator,
                public_cause="select a path inside exactly one registered owner",
            ) from exc
        return owner, relative + separator + symbol

    def _surface(
        self, repository_id: str, surface: m.SurfaceReference
    ) -> tuple[str, m.SurfaceReference]:
        if surface.kind.is_declared:
            return repository_id, surface
        owner, locator = self._locator(repository_id, surface.locator)
        return owner, _dataclasses.replace(surface, locator=locator)

    def obtain(self, request: m.AskRequest) -> m.AskRequest:
        """Canonicalize pure path-addressed obtain, never identity selectors."""
        if request.evidence is not None or request.continuation is not None:
            return request
        selector = request.selector
        if isinstance(selector, m.RecordedQuestionSelector):
            owner, surface = self._surface(selector.repository_id, selector.surface)
            return _dataclasses.replace(
                request,
                selector=_dataclasses.replace(
                    selector, repository_id=owner, surface=surface
                ),
            )
        if request.repository_id is None:
            return request
        if request.surface is not None:
            owner, surface = self._surface(request.repository_id, request.surface)
            return _dataclasses.replace(request, repository_id=owner, surface=surface)
        if request.reference is not None:
            owner, locator = self._locator(request.repository_id, request.reference)
            return _dataclasses.replace(request, repository_id=owner, reference=locator)
        return request

    def changes(self, request: m.ReconsiderRequest) -> tuple[m.ReconsiderRequest, ...]:
        """Partition path roots before the single shared traversal."""
        if request.challenge is not None:
            raise ValueError("challenge is identity-addressed")
        paths: dict[str, list[str]] = {}
        surfaces: dict[str, list[m.SurfaceKey]] = {}
        for path in request.changed_paths:
            owner, locator = self._locator(request.bound_repository_id, path)
            paths.setdefault(owner, []).append(locator)
        for surface in request.changed_surfaces:
            owner, reference = self._surface(
                surface.repository_id, m.SurfaceReference(surface.kind, surface.locator)
            )
            surfaces.setdefault(owner, []).append(
                m.SurfaceKey(owner, reference.kind, reference.locator)
            )
        return tuple(
            m.ReconsiderRequest(
                repository_id=owner,
                changed_paths=tuple(dict.fromkeys(paths.get(owner, ()))),
                changed_surfaces=tuple(dict.fromkeys(surfaces.get(owner, ()))),
            )
            for owner in sorted(set(paths) | set(surfaces))
        )
