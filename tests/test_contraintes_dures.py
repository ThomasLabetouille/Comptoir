# -*- coding: utf-8 -*-
"""La metrique bloquante du projet : zero contrainte dure violee.

Point important : ce fichier NE reutilise PAS les fonctions de comptoir.filtres
pour verifier les resultats. Il re-implemente les controles a la main, en clair.
Un test qui verifie le code avec le code qu'il teste ne prouve rien - il se
contente de confirmer que la fonction est d'accord avec elle-meme.
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from comptoir.catalogue import charger  # noqa: E402
from comptoir.demande import Demande  # noqa: E402
from comptoir.filtres import AGE_TARIF_ENFANT, PART_ENFANT, filtrer  # noqa: E402
from comptoir.schema import sans_accent  # noqa: E402

CATALOGUE = charger()
REQUETES = [
    json.loads(ligne)
    for ligne in (RACINE / "tests" / "requetes.jsonl").read_text(encoding="utf-8").splitlines()
    if ligne.strip()
]

IDS = [requete["id"] for requete in REQUETES]


def violations(fiche: dict, demande: Demande, nuits: int, prix: int) -> list[str]:
    """Controles ecrits a la main, independamment du moteur."""
    faux = []

    if demande.destinations:
        champs = [fiche["pays"], fiche["region"], *fiche.get("alias", [])]
        champs = [sans_accent(c) for c in champs]
        if not any(
            sans_accent(d) in c or c in sans_accent(d)
            for d in demande.destinations
            for c in champs
        ):
            faux.append("destination")

    if nuits not in fiche["durees_nuits"]:
        faux.append("duree")
    if demande.duree_nuits is not None and nuits != demande.duree_nuits:
        faux.append("duree demandee")

    if demande.date_debut or demande.date_fin:
        debut = date.fromisoformat(demande.date_debut) if demande.date_debut else date.min
        fin = date.fromisoformat(demande.date_fin) if demande.date_fin else date.max
        tient = False
        for periode in fiche["periodes_ouverture"]:
            d = max(debut, date.fromisoformat(periode["debut"]))
            f = min(fin, date.fromisoformat(periode["fin"]))
            if f - d >= timedelta(days=nuits):
                tient = True
        if not tient:
            faux.append("periode")

    if demande.adultes + len(demande.enfants_ages) > fiche["capacite_max_chambre"]:
        faux.append("capacite")

    if demande.enfants_ages and not fiche["enfants_acceptes"]:
        faux.append("enfants")

    if demande.club_enfants_requis:
        club = fiche.get("club_enfants")
        if not club:
            faux.append("club_enfants absent")
        elif demande.enfants_ages and not any(
            club["age_min"] <= age <= club["age_max"] for age in demande.enfants_ages
        ):
            faux.append("club_enfants hors tranche d'age")

    if demande.formules and fiche["formule"] not in demande.formules:
        faux.append("formule")

    if demande.depart and demande.depart not in fiche["aeroports_depart"]:
        faux.append("depart")

    parts = demande.adultes + sum(
        PART_ENFANT if age < AGE_TARIF_ENFANT else 1.0 for age in demande.enfants_ages
    )
    attendu = round(fiche["prix_pp_par_duree"][str(nuits)] * parts)
    if prix != attendu:
        faux.append(f"prix annonce {prix} au lieu de {attendu}")
    if demande.budget_total_max is not None and prix > demande.budget_total_max:
        faux.append(f"budget total depasse ({prix} > {demande.budget_total_max})")
    if demande.budget_pp_max is not None:
        if fiche["prix_pp_par_duree"][str(nuits)] > demande.budget_pp_max:
            faux.append("budget par personne depasse")

    return faux


@pytest.mark.parametrize("requete", REQUETES, ids=IDS)
def test_aucune_contrainte_dure_violee(requete):
    """Metrique 1 du projet. Doit rester a zero, sans exception."""
    demande = Demande.depuis_dict(requete["demande"])
    resultat = filtrer(CATALOGUE, demande)
    for proposition in resultat.propositions:
        faux = violations(proposition.fiche, demande, proposition.nuits, proposition.prix_total)
        assert not faux, f"{requete['id']} / {proposition.fiche['id']} : {faux}"


@pytest.mark.parametrize("requete", REQUETES, ids=IDS)
def test_resultat_conforme_a_l_attendu(requete):
    demande = Demande.depuis_dict(requete["demande"])
    resultat = filtrer(CATALOGUE, demande)
    attendu = requete["attendu"]

    if attendu.get("insoluble"):
        assert not resultat.propositions, (
            f"{requete['id']} devait etre insoluble, "
            f"{len(resultat.propositions)} proposition(s) trouvee(s)"
        )
        critere = attendu["critere_a_relacher"]
        assert resultat.debloquerait.get(critere, 0) > 0, (
            f"{requete['id']} : relacher '{critere}' devait ouvrir des options, "
            f"or debloquerait={resultat.debloquerait}"
        )
    else:
        assert len(resultat.propositions) >= attendu["au_moins"], (
            f"{requete['id']} : {len(resultat.propositions)} proposition(s), "
            f"au moins {attendu['au_moins']} attendue(s)"
        )


def test_abstention_sur_les_cas_insolubles():
    """Metrique 3 : ne jamais proposer quelque chose quand rien ne correspond,
    et toujours dire quoi assouplir."""
    insolubles = [r for r in REQUETES if r["attendu"].get("insoluble")]
    assert len(insolubles) >= 5, "trop peu de cas insolubles dans le jeu de test"

    for requete in insolubles:
        resultat = filtrer(CATALOGUE, Demande.depuis_dict(requete["demande"]))
        assert not resultat.propositions
        message = resultat.diagnostic()
        assert message.startswith("Aucun sejour ne correspond")
        assert "option(s) s'ouvriraient" in message, requete["id"]


def test_les_propositions_sont_triees_par_prix():
    demande = Demande(adultes=2, duree_nuits=7, formules=["tout_compris"])
    resultat = filtrer(CATALOGUE, demande)
    prix = [proposition.prix_total for proposition in resultat.propositions]
    assert prix == sorted(prix)
