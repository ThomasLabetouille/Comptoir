# -*- coding: utf-8 -*-
"""(Re)genere data/comptoir.db a partir de data/catalogue.json.

    python3 outils/construire_base_sql.py

Le pipeline complet est : FICHES (dans construire_catalogue.py) -> valide ->
catalogue.json -> ce script -> comptoir.db. La base ne source jamais FICHES
directement : elle passe par le JSON deja valide, pour n'avoir qu'un seul
chemin "source de verite -> catalogue publie".
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from comptoir.base_donnees import CHEMIN_PAR_DEFAUT, construire  # noqa: E402
from comptoir.catalogue import charger  # noqa: E402
from comptoir.schema import valider_catalogue  # noqa: E402


def principal() -> int:
    fiches = charger()
    problemes = valider_catalogue(fiches)
    if problemes:
        print(f"{len(problemes)} probleme(s) dans data/catalogue.json, base NON construite :")
        for probleme in problemes:
            print(f"  - {probleme}")
        return 1

    construire(fiches)
    print(f"{len(fiches)} fiches inserees dans {CHEMIN_PAR_DEFAUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
