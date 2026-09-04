# -*- coding: utf-8 -*-
"""Extraction texte -> Demande, testee sans reseau et sans Ollama.

appeler_ollama() n'est pas testee ici : elle a besoin d'un modele reellement
lance, sur la machine de l'utilisateur. Ce fichier teste les deux etapes qui
ne dependent d'aucun reseau - extraire_json() et nettoyer() - et les teste
avec des reponses DELIBEREMENT imparfaites : c'est precisement le genre de
sorties qu'un modele produit en pratique (balises markdown, champs inventes,
types approximatifs, valeurs hors limites).
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from comptoir.extraction import ErreurExtraction, extraire_json, nettoyer  # noqa: E402


# --------------------------------------------------------------------------
# extraire_json : isoler le JSON d'une reponse de modele
# --------------------------------------------------------------------------

def test_json_brut_sans_habillage():
    assert extraire_json('{"adultes": 2}') == {"adultes": 2}


def test_json_entoure_de_balises_markdown():
    brut = '```json\n{"adultes": 2, "destinations": ["Crete"]}\n```'
    assert extraire_json(brut) == {"adultes": 2, "destinations": ["Crete"]}


def test_json_entoure_de_balises_markdown_sans_langage():
    brut = '```\n{"adultes": 4}\n```'
    assert extraire_json(brut) == {"adultes": 4}


def test_json_precede_de_prose():
    brut = 'Voici la demande extraite :\n{"adultes": 2, "budget_total_max": 2000}'
    assert extraire_json(brut) == {"adultes": 2, "budget_total_max": 2000}


def test_json_avec_accolades_imbriquees():
    brut = '{"adultes": 2, "club": {"age_min": 4, "age_max": 12}}'
    assert extraire_json(brut) == {"adultes": 2, "club": {"age_min": 4, "age_max": 12}}


def test_absence_totale_de_json_leve_une_erreur():
    try:
        extraire_json("Desole, je n'ai pas compris la demande.")
        assert False, "aurait du lever ErreurExtraction"
    except ErreurExtraction:
        pass


def test_json_tronque_leve_une_erreur():
    try:
        extraire_json('{"adultes": 2, "destinations": ["Crete"')
        assert False, "aurait du lever ErreurExtraction"
    except ErreurExtraction:
        pass


def test_json_syntaxiquement_invalide_leve_une_erreur():
    try:
        extraire_json('{"adultes": 2, "destinations": [Crete, Sicile]}')  # chaines non citees
        assert False, "aurait du lever ErreurExtraction"
    except ErreurExtraction:
        pass


# --------------------------------------------------------------------------
# nettoyer : un dict qui n'est fiable ni sur la forme ni sur le fond
# --------------------------------------------------------------------------

def test_demande_complete_et_propre():
    demande = nettoyer({
        "adultes": 2,
        "enfants_ages": [8, 14],
        "destinations": ["Crete", "Sicile"],
        "date_debut": "2027-07-15",
        "date_fin": "2027-07-31",
        "duree_nuits": 7,
        "budget_total_max": 3500,
        "formules": ["tout_compris"],
        "depart": "TLS",
        "club_enfants_requis": False,
        "ambiance": ["famille"],
    })
    assert demande.adultes == 2
    assert demande.enfants_ages == [8, 14]
    assert demande.destinations == ["Crete", "Sicile"]
    assert demande.date_debut == "2027-07-15"
    assert demande.duree_nuits == 7
    assert demande.budget_total_max == 3500
    assert demande.formules == ["tout_compris"]
    assert demande.depart == "TLS"
    assert demande.non_precise == []


def test_dict_vide_donne_les_defauts_sans_avertissement():
    demande = nettoyer({})
    assert demande.adultes == 2
    assert demande.enfants_ages == []
    assert demande.non_precise == []  # rien n'a ete "invente puis ecarte" : tout etait juste absent


def test_champ_inconnu_du_modele_est_ignore_sans_planter():
    """Un modele qui ajoute 'raisonnement' ou 'commentaire' ne doit jamais
    faire planter l'extraction : seuls les champs connus sont lus."""
    demande = nettoyer({"adultes": 2, "raisonnement": "le client semble pressé", "commentaire": "ok"})
    assert demande.adultes == 2


def test_formule_inconnue_est_ecartee_et_signalee():
    demande = nettoyer({"formules": ["all_inclusive"]})  # pas le vocabulaire du catalogue
    assert demande.formules == []
    assert any("all_inclusive" in avert for avert in demande.non_precise)


def test_formule_avec_variantes_de_casse_et_espaces_est_acceptee():
    demande = nettoyer({"formules": ["Tout Compris"]})
    assert demande.formules == ["tout_compris"]


def test_aeroport_invalide_est_ecarte_et_signale():
    demande = nettoyer({"depart": "Toulouse"})  # pas un code IATA
    assert demande.depart is None
    assert any("depart" in avert for avert in demande.non_precise)


def test_aeroport_minuscule_est_normalise():
    demande = nettoyer({"depart": "tls"})
    assert demande.depart == "TLS"


def test_age_enfant_donne_en_chaine_est_converti():
    demande = nettoyer({"enfants_ages": ["8", "14"]})
    assert demande.enfants_ages == [8, 14]


def test_age_enfant_hors_limites_est_ecarte_et_signale():
    demande = nettoyer({"enfants_ages": [8, 45, -1]})
    assert demande.enfants_ages == [8]
    assert demande.non_precise.count("age d'un enfant") == 2


def test_budget_donne_en_chaine_est_converti():
    demande = nettoyer({"budget_total_max": "3500"})
    assert demande.budget_total_max == 3500


def test_budget_negatif_est_ecarte_et_signale():
    demande = nettoyer({"budget_total_max": -100})
    assert demande.budget_total_max is None
    assert "budget" in demande.non_precise


def test_date_mal_formee_est_ecartee_et_signalee():
    demande = nettoyer({"date_debut": "15 juillet 2027"})  # pas ISO
    assert demande.date_debut is None
    assert "dates" in demande.non_precise


def test_club_enfants_requis_ne_tombe_pas_dans_le_piege_de_bool_de_chaine():
    """bool('false') vaut True en Python pur - un piege classique qu'une
    extraction depuis du JSON/texte ne doit jamais reproduire."""
    assert nettoyer({"club_enfants_requis": "false"}).club_enfants_requis is False
    assert nettoyer({"club_enfants_requis": "true"}).club_enfants_requis is True
    assert nettoyer({"club_enfants_requis": False}).club_enfants_requis is False
    assert nettoyer({}).club_enfants_requis is False


def test_non_precise_fourni_par_le_modele_est_conserve():
    demande = nettoyer({"adultes": 2, "non_precise": ["budget", "dates exactes"]})
    assert "budget" in demande.non_precise
    assert "dates exactes" in demande.non_precise


def test_non_precise_du_modele_et_avertissements_internes_se_cumulent():
    demande = nettoyer({"non_precise": ["budget"], "depart": "Toulouse"})
    assert "budget" in demande.non_precise
    assert any("depart" in a for a in demande.non_precise)


def test_ambiance_texte_libre_n_est_jamais_rejetee():
    """Contrairement a 'formules', 'ambiance' ne sert qu'au classement -
    aucune raison de la valider contre une liste fermee."""
    demande = nettoyer({"ambiance": ["zen", "un peu bohème"]})
    assert demande.ambiance == ["zen", "un peu bohème"]
