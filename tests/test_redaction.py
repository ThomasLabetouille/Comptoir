# -*- coding: utf-8 -*-
"""Rediger et verifier, testes sans reseau et sans Ollama.

appeler_ollama() n'est pas testee ici, pour la meme raison que dans
test_extraction.py : elle a besoin d'un modele reellement lance, sur la
machine de l'utilisateur. Ce fichier teste verifier() et assembler() avec
des sorties de modele simulees, y compris deliberement malhonnetes - fiche
jamais presentee, champ qui n'existe pas dans la fiche citee, prix invente
qui ne correspond pas au prix reellement calcule pour cette demande.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from comptoir.demande import Demande  # noqa: E402
from comptoir.filtres import Proposition  # noqa: E402
from comptoir.redaction import (  # noqa: E402
    ErreurRedaction,
    assembler,
    extraire_json,
    verifier,
)

FICHE_KALLISTE = {
    "id": "kalliste-crete",
    "nom": "Club Kalliste",
    "gamme": "club",
    "pays": "Grece",
    "region": "Crete",
    "aeroports_depart": ["TLS", "ORY"],
    "durees_nuits": [7],
    "prix_pp_par_duree": {"7": 890},
    "formule": "tout_compris",
    "capacite_max_chambre": 4,
    "enfants_acceptes": True,
    "periodes_ouverture": [{"debut": "2027-04-15", "fin": "2027-10-25"}],
    "ambiance": ["famille", "plage"],
    "equipements": ["piscine", "club enfants"],
    "points_forts": ["Plage de sable a 150 m"],
    "points_faibles": ["Restaurant unique : file d'attente au diner en haute saison"],
    "club_enfants": {"age_min": 4, "age_max": 12},
    "note_clients": 7.8,
}

PROPOSITIONS = [Proposition(fiche=FICHE_KALLISTE, prix_total=3293, nuits=7)]


# --------------------------------------------------------------------------
# extraire_json : deja teste en detail dans test_extraction.py via le meme
# module partage (_json_modele) - on verifie juste que la delegation marche
# et que l'erreur levee est bien celle du bon pipeline.
# --------------------------------------------------------------------------

def test_json_entoure_de_balises_markdown():
    brut = '```json\n{"intro": "Bonjour"}\n```'
    assert extraire_json(brut) == {"intro": "Bonjour"}


def test_absence_de_json_leve_erreur_redaction_pas_erreur_extraction():
    try:
        extraire_json("je ne sais pas quoi repondre")
        assert False, "aurait du lever ErreurRedaction"
    except ErreurRedaction:
        pass


# --------------------------------------------------------------------------
# verifier : le coeur du filet
# --------------------------------------------------------------------------

def test_affirmations_valides_sont_conservees():
    brut = {
        "intro": "Deux options en Crete pour votre budget.",
        "propositions": [
            {
                "id": "kalliste-crete",
                "affirmations": [
                    {"champ": "prix_total", "texte": "3293 EUR pour 7 nuits"},
                    {"champ": "nuits", "texte": "un sejour de 7 nuits"},
                    {"champ": "points_faibles", "texte": "restaurant unique, file d'attente au diner"},
                ],
            }
        ],
    }
    redaction = verifier(brut, PROPOSITIONS)
    assert redaction.intro == "Deux options en Crete pour votre budget."
    assert len(redaction.propositions) == 1
    assert len(redaction.propositions[0].affirmations) == 3
    assert redaction.rejetees == []


def test_fiche_jamais_presentee_est_rejetee_en_bloc():
    brut = {
        "intro": "",
        "propositions": [
            {
                "id": "hotel-invente-par-le-modele",
                "affirmations": [{"champ": "nom", "texte": "Un tres bel hotel"}],
            }
        ],
    }
    redaction = verifier(brut, PROPOSITIONS)
    assert redaction.propositions == []
    assert len(redaction.rejetees) == 1
    assert "hotel-invente-par-le-modele" in redaction.rejetees[0]


def test_champ_qui_nexiste_pas_dans_la_fiche_est_rejete():
    brut = {
        "intro": "",
        "propositions": [
            {
                "id": "kalliste-crete",
                "affirmations": [
                    {"champ": "piscine_a_debordement", "texte": "une piscine a debordement magnifique"},
                    {"champ": "prix_total", "texte": "3293 EUR"},
                ],
            }
        ],
    }
    redaction = verifier(brut, PROPOSITIONS)
    # Le champ invente est rejete, mais l'affirmation valide a cote survit.
    assert len(redaction.propositions[0].affirmations) == 1
    assert redaction.propositions[0].affirmations[0].champ == "prix_total"
    assert any("non citable" in r for r in redaction.rejetees)


def test_prix_qui_ne_correspond_pas_au_prix_reel_est_rejete():
    brut = {
        "intro": "",
        "propositions": [
            {
                "id": "kalliste-crete",
                "affirmations": [{"champ": "prix_total", "texte": "2500 EUR, une bonne affaire"}],
            }
        ],
    }
    redaction = verifier(brut, PROPOSITIONS)
    # 2500 n'est pas le prix reel (3293) pour cette demande -> proposition
    # entierement rejetee, aucune affirmation ne survit.
    assert redaction.propositions == []
    assert any("2500" in r and "3293" in r for r in redaction.rejetees)


def test_champ_present_dans_le_dict_mais_hors_liste_blanche_est_rejete():
    # "id" existe bien dans FICHE_KALLISTE, mais n'est pas dans CHAMPS_CITABLES :
    # ce n'est pas une affirmation utile a un client.
    brut = {
        "intro": "",
        "propositions": [
            {"id": "kalliste-crete", "affirmations": [{"champ": "id", "texte": "kalliste-crete"}]}
        ],
    }
    redaction = verifier(brut, PROPOSITIONS)
    assert redaction.propositions == []
    assert any("non citable" in r for r in redaction.rejetees)


def test_champ_vide_dans_la_fiche_est_rejete():
    fiche_sans_points_faibles = dict(FICHE_KALLISTE, points_faibles=[])
    propositions = [Proposition(fiche=fiche_sans_points_faibles, prix_total=3293, nuits=7)]
    brut = {
        "intro": "",
        "propositions": [
            {
                "id": "kalliste-crete",
                "affirmations": [{"champ": "points_faibles", "texte": "aucun point faible notable"}],
            }
        ],
    }
    redaction = verifier(brut, propositions)
    assert redaction.propositions == []
    assert any("absent ou vide" in r for r in redaction.rejetees)


def test_bloc_de_proposition_mal_forme_ne_fait_pas_planter_la_verification():
    brut = {"intro": "Bonjour", "propositions": ["ceci n'est pas un dict", 42, None]}
    redaction = verifier(brut, PROPOSITIONS)
    assert redaction.propositions == []
    assert len(redaction.rejetees) == 3


def test_affirmation_mal_formee_ne_fait_pas_planter_la_verification():
    brut = {
        "intro": "",
        "propositions": [{"id": "kalliste-crete", "affirmations": ["pas un dict", {"champ": "prix_total"}]}],
    }
    redaction = verifier(brut, PROPOSITIONS)
    # "pas un dict" et {"champ": "prix_total"} (sans "texte") sont chacun
    # rejetes, puis la proposition elle-meme est ecartee faute d'avoir gardé
    # une seule affirmation valide : trois rejets journalises, aucun crash.
    assert redaction.propositions == []
    assert len(redaction.rejetees) == 3


def test_reponse_du_modele_completement_vide_ne_plante_pas():
    redaction = verifier({}, PROPOSITIONS)
    assert redaction.intro == ""
    assert redaction.propositions == []
    assert redaction.rejetees == []


# --------------------------------------------------------------------------
# taux_de_verification : la mesure de tracabilite
# --------------------------------------------------------------------------

def test_taux_de_verification_avec_tout_retenu():
    brut = {
        "intro": "",
        "propositions": [
            {"id": "kalliste-crete", "affirmations": [{"champ": "prix_total", "texte": "3293 EUR"}]}
        ],
    }
    redaction = verifier(brut, PROPOSITIONS)
    assert redaction.taux_de_verification() == 1.0


def test_taux_de_verification_avec_rejets_partiels():
    brut = {
        "intro": "",
        "propositions": [
            {
                "id": "kalliste-crete",
                "affirmations": [
                    {"champ": "prix_total", "texte": "3293 EUR"},
                    {"champ": "piscine_a_debordement", "texte": "magnifique"},
                ],
            }
        ],
    }
    redaction = verifier(brut, PROPOSITIONS)
    assert redaction.taux_de_verification() == 0.5


def test_taux_de_verification_none_quand_rien_nest_produit():
    redaction = verifier({}, PROPOSITIONS)
    assert redaction.taux_de_verification() is None


# --------------------------------------------------------------------------
# assembler : la Redaction verifiee -> le texte final
# --------------------------------------------------------------------------

def test_assembler_avec_une_proposition_retenue():
    brut = {
        "intro": "Une option en Crete.",
        "propositions": [
            {
                "id": "kalliste-crete",
                "affirmations": [
                    {"champ": "prix_total", "texte": "3293 EUR pour 7 nuits"},
                    {"champ": "points_faibles", "texte": "restaurant unique"},
                ],
            }
        ],
    }
    texte = assembler(verifier(brut, PROPOSITIONS))
    assert "Une option en Crete." in texte
    assert "3293 EUR pour 7 nuits" in texte
    assert "restaurant unique" in texte


def test_assembler_quand_tout_est_rejete_ne_montre_rien_de_faux():
    brut = {
        "intro": "",
        "propositions": [
            {"id": "kalliste-crete", "affirmations": [{"champ": "prix_total", "texte": "2500 EUR"}]}
        ],
    }
    texte = assembler(verifier(brut, PROPOSITIONS))
    assert "2500" not in texte
    assert texte  # jamais une chaine vide : le client doit voir un message
