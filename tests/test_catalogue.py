# -*- coding: utf-8 -*-
"""Le catalogue est la matiere premiere : s'il est faux, tout le reste ment."""

import importlib.util
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from comptoir.catalogue import charger  # noqa: E402
from comptoir.schema import valider_catalogue  # noqa: E402


def test_catalogue_valide():
    problemes = valider_catalogue(charger())
    assert problemes == [], "\n".join(problemes)


def test_catalogue_non_vide():
    assert len(charger()) >= 30


def test_fichier_synchronise_avec_le_generateur():
    """data/catalogue.json doit etre exactement ce que produit le generateur.

    Sans ce test, une fiche modifiee a la main dans le JSON serait ecrasee
    silencieusement au prochain lancement du script.
    """
    chemin = RACINE / "outils" / "construire_catalogue.py"
    spec = importlib.util.spec_from_file_location("construire_catalogue", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    attendu = json.loads(json.dumps(module.FICHES, ensure_ascii=False))
    assert charger() == attendu, (
        "data/catalogue.json ne correspond plus a outils/construire_catalogue.py "
        "- relancer: python3 outils/construire_catalogue.py"
    )
