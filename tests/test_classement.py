# -*- coding: utf-8 -*-
"""Classement sur criteres souples : entierement deterministe, sans reseau
ni modele - juste des comparaisons sur des champs de fiche, comme le reste
du moteur. Rien ici ne depend d'Ollama.
"""

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from comptoir.classement import classer, score_ambiance, score_note, score_plage  # noqa: E402
from comptoir.demande import Demande  # noqa: E402
from comptoir.filtres import Proposition  # noqa: E402

FICHE_CALME_PLAGE = {
    "id": "calme-plage",
    "ambiance": ["calme", "plage"],
    "note_clients": 9.0,
    "distance_plage_m": 50,
}
FICHE_ANIMATION_LOIN = {
    "id": "animation-loin",
    "ambiance": ["animation", "famille"],
    "note_clients": 6.0,
    "distance_plage_m": 1800,
}
FICHE_SANS_INFOS = {
    "id": "sans-infos",
    "ambiance": [],
}


# --------------------------------------------------------------------------
# score_ambiance
# --------------------------------------------------------------------------

def test_score_ambiance_nul_si_client_ne_precise_rien():
    demande = Demande()
    assert score_ambiance(FICHE_CALME_PLAGE, demande) == 0.0


def test_score_ambiance_correspondance_totale():
    demande = Demande(ambiance=["calme", "plage"])
    assert score_ambiance(FICHE_CALME_PLAGE, demande) == 1.0


def test_score_ambiance_correspondance_partielle():
    demande = Demande(ambiance=["calme", "sportif"])
    assert score_ambiance(FICHE_CALME_PLAGE, demande) == 0.5


def test_score_ambiance_insensible_aux_accents_et_a_la_casse():
    demande = Demande(ambiance=["CALME", "Plage"])
    assert score_ambiance(FICHE_CALME_PLAGE, demande) == 1.0


def test_score_ambiance_aucune_correspondance():
    demande = Demande(ambiance=["luxe"])
    assert score_ambiance(FICHE_CALME_PLAGE, demande) == 0.0


# --------------------------------------------------------------------------
# score_note
# --------------------------------------------------------------------------

def test_score_note_normalisee_sur_10():
    assert score_note(FICHE_CALME_PLAGE) == 0.9


def test_score_note_neutre_si_absente():
    assert score_note(FICHE_SANS_INFOS) == 0.5


# --------------------------------------------------------------------------
# score_plage
# --------------------------------------------------------------------------

def test_score_plage_proche_est_haut():
    assert score_plage(FICHE_CALME_PLAGE) > 0.9


def test_score_plage_loin_est_bas():
    assert score_plage(FICHE_ANIMATION_LOIN) == pytest.approx(0.1)


def test_score_plage_neutre_si_absente():
    assert score_plage(FICHE_SANS_INFOS) == 0.5


def test_score_plage_jamais_negatif_meme_tres_loin():
    fiche = {"distance_plage_m": 50000}
    assert score_plage(fiche) == 0.0


# --------------------------------------------------------------------------
# classer
# --------------------------------------------------------------------------

def test_classer_priorise_lambiance_demandee():
    demande = Demande(ambiance=["calme", "plage"])
    props = [
        Proposition(fiche=FICHE_ANIMATION_LOIN, prix_total=1000, nuits=7),
        Proposition(fiche=FICHE_CALME_PLAGE, prix_total=1500, nuits=7),
    ]
    classees = classer(props, demande)
    # calme-plage est plus cher mais correspond exactement a la demande :
    # il doit passer devant, sinon le classement ne sert a rien.
    assert classees[0].fiche["id"] == "calme-plage"


def test_classer_ne_perd_et_ninvente_aucune_proposition():
    demande = Demande()
    props = [
        Proposition(fiche=FICHE_CALME_PLAGE, prix_total=1500, nuits=7),
        Proposition(fiche=FICHE_ANIMATION_LOIN, prix_total=1000, nuits=7),
        Proposition(fiche=FICHE_SANS_INFOS, prix_total=800, nuits=7),
    ]
    classees = classer(props, demande)
    assert {p.fiche["id"] for p in classees} == {p.fiche["id"] for p in props}
    assert len(classees) == len(props)


def test_classer_egalite_de_score_garde_lordre_du_prix():
    # Demande vide -> score_ambiance nul pour tout le monde ; si les deux
    # fiches ont aussi la meme note et la meme distance, seul l'ordre de
    # depart (deja trie par prix par filtrer()) doit dicter le resultat.
    demande = Demande()
    fiche_a = {"id": "a", "ambiance": [], "note_clients": 7.0, "distance_plage_m": 300}
    fiche_b = {"id": "b", "ambiance": [], "note_clients": 7.0, "distance_plage_m": 300}
    props = [
        Proposition(fiche=fiche_a, prix_total=900, nuits=7),   # le moins cher, en tete
        Proposition(fiche=fiche_b, prix_total=1200, nuits=7),
    ]
    classees = classer(props, demande)
    assert [p.fiche["id"] for p in classees] == ["a", "b"]


def test_classer_liste_vide_ne_plante_pas():
    assert classer([], Demande()) == []
