"""Chargement du catalogue."""

from __future__ import annotations

import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CHEMIN_PAR_DEFAUT = RACINE / "data" / "catalogue.json"


def charger(chemin: Path | str | None = None) -> list[dict]:
    chemin = Path(chemin) if chemin else CHEMIN_PAR_DEFAUT
    with open(chemin, encoding="utf-8") as flux:
        donnees = json.load(flux)
    if not isinstance(donnees, list):
        raise ValueError(f"{chemin}: le catalogue doit etre une liste de fiches")
    return donnees


def par_id(fiches: list[dict]) -> dict[str, dict]:
    return {fiche["id"]: fiche for fiche in fiches}
