# -*- coding: utf-8 -*-
"""Interroger le moteur en ligne de commande, sans modele de langage.

    python3 outils/chercher.py q02        # rejoue une requete du jeu de test
    python3 outils/chercher.py --toutes   # les rejoue toutes

Tant que l'extraction automatique n'existe pas (semaine 2), la demande
structuree est lue telle quelle dans tests/requetes.jsonl.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from comptoir.catalogue import charger  # noqa: E402
from comptoir.demande import Demande  # noqa: E402
from comptoir.filtres import filtrer  # noqa: E402

REQUETES = RACINE / "tests" / "requetes.jsonl"


def charger_requetes() -> dict[str, dict]:
    lignes = REQUETES.read_text(encoding="utf-8").splitlines()
    return {r["id"]: r for r in (json.loads(l) for l in lignes if l.strip())}


def afficher(requete: dict, catalogue: list[dict]) -> None:
    demande = Demande.depuis_dict(requete["demande"])
    resultat = filtrer(catalogue, demande)

    print("=" * 78)
    print(f"[{requete['id']}] Le client dit :")
    print(f"  « {requete['texte']} »")
    print()
    print(f"  {demande.voyageurs} voyageur(s)", end="")
    if demande.destinations:
        print(f" | {', '.join(demande.destinations)}", end="")
    if demande.duree_nuits:
        print(f" | {demande.duree_nuits} nuits", end="")
    if demande.budget_total_max:
        print(f" | max {demande.budget_total_max} EUR", end="")
    print()
    print()

    if not resultat:
        print("  " + resultat.diagnostic())
        print()
        return

    for rang, proposition in enumerate(resultat.propositions[:3], 1):
        fiche = proposition.fiche
        print(f"  {rang}. {fiche['nom']} - {fiche['region']}, {fiche['pays']}")
        print(
            f"     {proposition.nuits} nuits, {fiche['formule'].replace('_', ' ')}, "
            f"{proposition.prix_total} EUR au total "
            f"({fiche['prix_pp_par_duree'][str(proposition.nuits)]} EUR/personne)"
        )
        print(f"     + {fiche['points_forts'][0]}")
        print(f"     - {fiche['points_faibles'][0]}")
        print()

    reste = len(resultat.propositions) - 3
    if reste > 0:
        print(f"  ({reste} autre(s) sejour(s) correspondent aussi)")
        print()


def principal(argv: list[str]) -> int:
    catalogue = charger()
    requetes = charger_requetes()

    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        print("Requetes disponibles :", ", ".join(requetes))
        return 0

    if argv[0] == "--toutes":
        for requete in requetes.values():
            afficher(requete, catalogue)
        return 0

    identifiant = argv[0]
    if identifiant not in requetes:
        print(f"Requete inconnue : {identifiant}")
        print("Disponibles :", ", ".join(requetes))
        return 1

    afficher(requetes[identifiant], catalogue)
    return 0


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv[1:]))
