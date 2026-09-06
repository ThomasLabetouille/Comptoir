# -*- coding: utf-8 -*-
"""La conversion d'un export vers le format du moteur.

Un export reel comporte toujours des lignes incompletes ou mal saisies. Ce
qui compte n'est donc pas seulement qu'une ligne correcte se convertisse,
mais qu'une ligne fautive soit refusee avec une raison lisible, sans
interrompre les autres et sans etre devinee.
"""

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from comptoir.schema import valider_catalogue  # noqa: E402
from outils.convertir_catalogue import (  # noqa: E402
    LigneRefusee,
    convertir,
    convertir_ligne,
    lire_csv,
    principal,
)

EXEMPLE = RACINE / "data" / "exemple_import.csv"


def ligne_valide(**remplacements) -> dict:
    """Une ligne d'export correcte, que chaque test abime a sa facon."""
    ligne = {
        "reference": "lagune-djerba",
        "libelle": "Club Lagune",
        "gamme": "club",
        "pays": "Tunisie",
        "region": "Djerba",
        "aeroports": "TLS|ORY",
        "durees": "7|10",
        "prix_par_personne": "690|880",
        "formule": "tout_compris",
        "capacite_chambre": "4",
        "enfants_acceptes": "oui",
        "ouverture": "2027-03-20..2027-11-05",
        "ambiance": "famille|plage",
        "equipements": "piscine|wifi gratuit",
        "points_forts": "Plage privee a 80 m",
        "points_faibles": "Animation sonore le soir",
        "club_enfants": "3-12",
        "note": "8,2",
        "distance_plage": "80",
        "alias": "Jerba",
    }
    ligne.update(remplacements)
    return ligne


# --------------------------------------------------------------------------
# le fichier d'exemple livre avec le projet
# --------------------------------------------------------------------------


def test_l_exemple_livre_se_convertit():
    fiches, refus = convertir(lire_csv(EXEMPLE, ";", "utf-8-sig"))
    assert len(fiches) == 3
    assert len(refus) == 1


def test_la_ligne_fautive_de_l_exemple_est_nommee_et_expliquee():
    """La quatrieme fiche vend trois durees mais n'en tarife que deux."""
    _fiches, refus = convertir(lire_csv(EXEMPLE, ";", "utf-8-sig"))
    assert "ligne 5" in refus[0]
    assert "prix" in refus[0]


def test_le_catalogue_produit_passe_la_validation_d_ensemble():
    fiches, _refus = convertir(lire_csv(EXEMPLE, ";", "utf-8-sig"))
    assert valider_catalogue(fiches) == []


# --------------------------------------------------------------------------
# la traduction d'une ligne
# --------------------------------------------------------------------------


def test_les_listes_sont_decoupees():
    fiche = convertir_ligne(ligne_valide())
    assert fiche["aeroports_depart"] == ["TLS", "ORY"]
    assert fiche["ambiance"] == ["famille", "plage"]
    assert fiche["points_faibles"] == ["Animation sonore le soir"]


def test_les_durees_et_les_prix_sont_apparies():
    fiche = convertir_ligne(ligne_valide(durees="7|10|14", prix_par_personne="690|880|1090"))
    assert fiche["prix_pp_par_duree"] == {"7": 690, "10": 880, "14": 1090}


def test_les_codes_aeroport_sont_mis_en_majuscules():
    fiche = convertir_ligne(ligne_valide(aeroports="tls|ory"))
    assert fiche["aeroports_depart"] == ["TLS", "ORY"]


def test_une_duree_sans_prix_est_refusee():
    with pytest.raises(LigneRefusee, match="prix"):
        convertir_ligne(ligne_valide(durees="7|10|14", prix_par_personne="690|880"))


def test_un_prix_non_numerique_est_refuse():
    with pytest.raises(LigneRefusee, match="entier"):
        convertir_ligne(ligne_valide(prix_par_personne="690|sur demande"))


def test_une_periode_mal_formee_est_refusee():
    with pytest.raises(LigneRefusee, match="debut..fin"):
        convertir_ligne(ligne_valide(ouverture="2027-03-20 au 2027-11-05"))


def test_un_oui_non_incomprehensible_est_refuse():
    with pytest.raises(LigneRefusee, match="ni oui ni non"):
        convertir_ligne(ligne_valide(enfants_acceptes="selon la chambre"))


def test_une_colonne_absente_de_l_export_est_refusee_lisiblement():
    """Un export dont il manque une colonne ne doit pas planter le script :
    c'est le cas le plus frequent quand on branche un nouveau fournisseur."""
    ligne = ligne_valide()
    del ligne["ouverture"]
    with pytest.raises(LigneRefusee, match="colonne 'ouverture' absente"):
        convertir_ligne(ligne)


def test_un_club_enfants_vide_n_ajoute_pas_le_champ():
    fiche = convertir_ligne(ligne_valide(club_enfants="", enfants_acceptes="non"))
    assert "club_enfants" not in fiche


def test_une_tranche_d_ages_mal_ecrite_est_refusee():
    with pytest.raises(LigneRefusee, match="club enfants"):
        convertir_ligne(ligne_valide(club_enfants="a partir de 3 ans"))


def test_les_champs_optionnels_absents_ne_sont_pas_inventes():
    fiche = convertir_ligne(ligne_valide(note="", distance_plage="", alias=""))
    assert "note_clients" not in fiche
    assert "distance_plage_m" not in fiche
    assert "alias" not in fiche


# --------------------------------------------------------------------------
# le script en ligne de commande
# --------------------------------------------------------------------------


def test_sans_sortie_rien_n_est_ecrit(tmp_path, capsys):
    destination = tmp_path / "catalogue.json"
    code = principal([str(EXEMPLE)])
    assert code == 0
    assert not destination.exists()
    assert "Relancez avec --sortie" in capsys.readouterr().out


def test_avec_sortie_le_catalogue_est_ecrit_et_relisible(tmp_path):
    destination = tmp_path / "sous-dossier" / "catalogue.json"
    code = principal([str(EXEMPLE), "--sortie", str(destination)])
    assert code == 0

    fiches = json.loads(destination.read_text(encoding="utf-8"))
    assert len(fiches) == 3
    assert valider_catalogue(fiches) == []
