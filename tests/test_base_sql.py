# -*- coding: utf-8 -*-
"""Verifie le portage SQL en le comparant au moteur Python deja teste,
plutot qu'en lui faisant confiance parce qu'il "a l'air correct".

comptoir.base_donnees.candidats() couvre en SQL les criteres d'appartenance
a un ensemble (destination, depart, duree, formule, capacite, enfants,
club_enfants). Ce fichier recompose ensuite le resultat complet en reutilisant
les fonctions Python DEJA testees pour la periode et le prix
(critere_periode, critere_budget, meilleur_prix - voir test_contraintes_dures.py)
et verifie que le resultat final est identique, fiche par fiche, prix par
prix, a celui de comptoir.filtres.filtrer() sur les 20 memes requetes.

Une base separee est construite dans un dossier temporaire pour chaque
session de tests (voir la fixture `base`) : ces tests ne dependent jamais de
data/comptoir.db et ne le modifient pas.
"""

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from comptoir.base_donnees import candidats, connecter, construire  # noqa: E402
from comptoir.catalogue import charger  # noqa: E402
from comptoir.demande import Demande  # noqa: E402
from comptoir.filtres import (  # noqa: E402
    Proposition,
    critere_budget,
    critere_destination,
    critere_periode,
    filtrer,
    meilleur_prix,
)

CATALOGUE = charger()
FICHES_PAR_ID = {fiche["id"]: fiche for fiche in CATALOGUE}

REQUETES = [
    json.loads(ligne)
    for ligne in (RACINE / "tests" / "requetes.jsonl").read_text(encoding="utf-8").splitlines()
    if ligne.strip()
]
IDS = [requete["id"] for requete in REQUETES]


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    """Une base SQLite construite une seule fois pour tout ce fichier."""
    chemin = tmp_path_factory.mktemp("comptoir_sql") / "comptoir.db"
    construire(CATALOGUE, chemin=chemin)
    conn = connecter(chemin)
    yield conn
    conn.close()


def resultat_recompose(conn, demande: Demande) -> list[Proposition]:
    """Le meme resultat que filtrer(), en composant SQL (ensemble) + Python
    (periode, prix) - c'est exactement ce que ferait l'application reelle."""
    propositions = []
    for identifiant in candidats(conn, demande):
        fiche = FICHES_PAR_ID[identifiant]
        if not critere_periode(fiche, demande):
            continue
        if not critere_budget(fiche, demande):
            continue
        meilleur = meilleur_prix(fiche, demande)
        if meilleur is None:
            continue
        prix, nuits = meilleur
        propositions.append(Proposition(fiche=fiche, prix_total=prix, nuits=nuits))
    propositions.sort(key=lambda p: p.prix_total)
    return propositions


@pytest.mark.parametrize("requete", REQUETES, ids=IDS)
def test_sql_produit_exactement_le_meme_resultat_que_python(base, requete):
    demande = Demande.depuis_dict(requete["demande"])

    attendu = filtrer(CATALOGUE, demande).propositions
    obtenu = resultat_recompose(base, demande)

    attendu_tuples = [(p.fiche["id"], p.prix_total, p.nuits) for p in attendu]
    obtenu_tuples = [(p.fiche["id"], p.prix_total, p.nuits) for p in obtenu]

    assert obtenu_tuples == attendu_tuples, (
        f"{requete['id']} : SQL+Python donne {obtenu_tuples}, "
        f"Python seul donnait {attendu_tuples}"
    )


def test_sans_filtre_toutes_les_fiches_sont_candidates(base):
    assert candidats(base, Demande(adultes=1)) == set(FICHES_PAR_ID)


def test_une_duree_qu_aucune_fiche_ne_propose_ne_retourne_rien(base):
    assert candidats(base, Demande(adultes=2, duree_nuits=1)) == set()


def test_alias_fonctionne_en_sql_comme_en_python(base):
    """'Ocean Indien' n'est ni un pays ni une region : seul l'alias le sait.

    Compare l'ensemble brut retourne par le SQL (candidats() ignore encore
    periode/budget) au meme critere applique en Python sur tout le catalogue
    - pas au resultat final de filtrer(), qui inclurait des filtres que la
    requete SQL ne fait pas encore a ce stade."""
    demande = Demande(adultes=2, destinations=["Ocean Indien"])
    attendu = {f["id"] for f in CATALOGUE if critere_destination(f, demande)}
    assert attendu, "aucune fiche du catalogue ne porte cet alias : le test ne teste rien"
    assert candidats(base, demande) == attendu


def test_construire_est_idempotent(tmp_path):
    """Reconstruire au meme endroit ne doit ni echouer ni laisser un etat
    incoherent (fichier temporaire orphelin, base a moitie ecrite)."""
    chemin = tmp_path / "comptoir.db"
    construire(CATALOGUE, chemin=chemin)
    construire(CATALOGUE, chemin=chemin)
    conn = connecter(chemin)
    try:
        assert conn.execute("SELECT COUNT(*) FROM fiches").fetchone()[0] == len(CATALOGUE)
    finally:
        conn.close()
