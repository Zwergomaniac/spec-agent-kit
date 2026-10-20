"""Installation des Kits in ein Zielprojekt: ``sak init``, ``upgrade``, ``doctor`` (Spec 005)."""

from __future__ import annotations


class InstallError(Exception):
    """Fachliche Ablehnung. ``errors`` sind ``{path, message}``; es wurde nichts geschrieben."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        super().__init__("; ".join(f"{e['path']}: {e['message']}" for e in errors))
        self.errors = errors

    @classmethod
    def single(cls, path: str, message: str) -> InstallError:
        return cls([{"path": path, "message": message}])
