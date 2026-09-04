# -*- coding: utf-8 -*-
"""outils/mesurer.py oriente vers de vrais appels a Ollama - ce fichier ne
teste donc que la mecanique autour (parsing, agregation, gestion des
echecs), avec extraire() et rediger() remplaces, sans reseau.
"""

import sys
from pathlib import Path
from unittest.mock import patch

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from comptoir.catalogue import charger  # noqa: E402
from comptoir.demande import Demande  # noqa: E402
from comptoir.extraction import ErreurExtraction  # noqa: E402
from comptoir.redaction import ErreurRedaction, Redaction  # noqa: E402
from outils.mesurer import charger_requetes, mesurer_une_requete, resumer  # noqa: E402

CATALOGUE = charger()


def test_charger_requetes_retrouve_les_20_requetes_du_jeu_de_test():
    requetes = charger_requetes()
    assert len(requetes) == 20
    assert {r["id"] for r in requetes} == {f"q{n:02d}" for n in range(1, 21)}


def test_erreur_extraction_est_journalisee_pas_fatale():
    requete = {"id": "q99", "texte": "peu importe", "attendu": {"au_moins": 1}}
    with patch("outils.mesurer.extraire", side_effect=ErreurExtraction("Ollama injoignable")):
        ligne = mesurer_une_requete(requete, CATALOGUE, hote="http://x", modele="m")
    assert ligne["erreur_extraction"] == "Ollama injoignable"
    assert "nombre_propositions" not in ligne


def test_requete_insoluble_correctement_detectee():
    requete = {
        "id": "q99",
        "texte": "budget ridicule",
        "attendu": {"insoluble": True, "critere_a_relacher": "budget"},
    }
    demande_bidon = Demande(adultes=2, budget_total_max=1)
    with patch("outils.mesurer.extraire", return_value=demande_bidon):
        ligne = mesurer_une_requete(requete, CATALOGUE, hote="http://x", modele="m")
    assert ligne["nombre_propositions"] == 0
    assert ligne["insoluble_attendu"] is True
    assert ligne["insoluble_obtenu"] is True


def test_erreur_redaction_est_journalisee_pas_fatale():
    requete = {"id": "q99", "texte": "on est deux, Crete", "attendu": {"au_moins": 1}}
    demande = Demande(adultes=2, destinations=["Crete"])
    with patch("outils.mesurer.extraire", return_value=demande), \
         patch("outils.mesurer.rediger", side_effect=ErreurRedaction("Ollama injoignable")):
        ligne = mesurer_une_requete(requete, CATALOGUE, hote="http://x", modele="m")
    assert ligne["nombre_propositions"] > 0
    assert ligne["erreur_redaction"] == "Ollama injoignable"


def test_taux_de_verification_remonte_jusquau_resume():
    requete = {"id": "q99", "texte": "on est deux, Crete", "attendu": {"au_moins": 1}}
    demande = Demande(adultes=2, destinations=["Crete"])
    redaction = Redaction(intro="", propositions=[], rejetees=[], nombre_produites=4)
    with patch("outils.mesurer.extraire", return_value=demande), \
         patch("outils.mesurer.rediger", return_value=("texte", redaction)):
        ligne = mesurer_une_requete(requete, CATALOGUE, hote="http://x", modele="m")
    assert ligne["affirmations_produites"] == 4
    assert ligne["taux_de_verification"] == 0.0  # aucune affirmation retenue sur 4 produites


def test_resumer_calcule_lextraction_lastention_et_la_tracabilite():
    lignes = [
        {"erreur_extraction": "injoignable"},
        {"insoluble_attendu": True, "insoluble_obtenu": True, "nombre_propositions": 0},
        {"insoluble_attendu": True, "insoluble_obtenu": False, "nombre_propositions": 2},
        {"insoluble_attendu": False, "nombre_propositions": 1, "taux_de_verification": 1.0},
        {"insoluble_attendu": False, "nombre_propositions": 1, "taux_de_verification": 0.5},
    ]
    resume = resumer(lignes)
    assert resume["total_requetes"] == 5
    assert resume["extraction_reussie"] == "4/5"
    assert resume["abstention_correcte"] == "1/2"
    assert resume["tracabilite_moyenne"] == 0.75
    assert resume["tracabilite_sur_n_reponses"] == 2


def test_resumer_sans_requete_insoluble_dans_le_lot():
    resume = resumer([{"insoluble_attendu": False, "nombre_propositions": 1, "taux_de_verification": 1.0}])
    assert resume["abstention_correcte"] == "n/a"


def test_resumer_sans_aucune_tracabilite_mesurable():
    resume = resumer([{"erreur_extraction": "x"}])
    assert resume["tracabilite_moyenne"] is None
