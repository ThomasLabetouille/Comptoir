"""Les demandes de suite : « meme chose mais pas plus de 3000 euros ».

Le client ne repete pas ce qu'il vient de dire. La phrase seule est donc
incomplete, et la lire isolement donne une demande fausse - c'est exactement
ce que la mesure en conditions reelles avait montre sur q03 et q07.

La reprise est faite par du code (`fusionner`), a partir de la liste des
champs que la derniere phrase a reellement renseignes (`champs_fournis`). Le
modele n'a jamais a decider ce qui reste valable d'un tour a l'autre.
"""

from unittest.mock import patch

from comptoir.demande import Demande, fusionner
from comptoir.extraction import champs_fournis, extraire


def demande_de_reference() -> Demande:
    """Ce que le client avait dit au tour precedent (q02 du jeu de test)."""
    return Demande(
        adultes=2,
        enfants_ages=[8, 14],
        destinations=["Crete", "Sicile"],
        date_debut="2027-07-15",
        date_fin="2027-07-31",
        duree_nuits=7,
        formules=["tout_compris"],
        depart="TLS",
        budget_total_max=3500,
    )


# --------------------------------------------------------------------------
# fusionner
# --------------------------------------------------------------------------


def test_un_champ_fourni_ecrase_l_ancien():
    precedente = demande_de_reference()
    nouvelle = Demande(budget_total_max=3000)
    fusion = fusionner(precedente, nouvelle, {"budget_total_max"})
    assert fusion.budget_total_max == 3000


def test_un_champ_absent_de_la_phrase_est_repris_tel_quel():
    precedente = demande_de_reference()
    nouvelle = Demande(budget_total_max=3000)
    fusion = fusionner(precedente, nouvelle, {"budget_total_max"})

    assert fusion.destinations == ["Crete", "Sicile"]
    assert fusion.enfants_ages == [8, 14]
    assert fusion.date_debut == "2027-07-15"
    assert fusion.duree_nuits == 7
    assert fusion.depart == "TLS"
    assert fusion.formules == ["tout_compris"]
    assert fusion.voyageurs == 4


def test_une_destination_donnee_remplace_la_precedente():
    precedente = demande_de_reference()
    nouvelle = Demande(destinations=["Crete"])
    fusion = fusionner(precedente, nouvelle, {"destinations"})

    assert fusion.destinations == ["Crete"]
    assert fusion.budget_total_max == 3500


def test_non_precise_n_est_jamais_herite():
    precedente = demande_de_reference()
    precedente.non_precise = ["budget"]
    nouvelle = Demande(budget_total_max=3000, non_precise=["formule"])
    fusion = fusionner(precedente, nouvelle, {"budget_total_max"})

    assert fusion.non_precise == ["formule"]


def test_le_client_peut_retirer_l_exigence_de_club_enfants():
    precedente = demande_de_reference()
    precedente.club_enfants_requis = True
    nouvelle = Demande(club_enfants_requis=False)
    fusion = fusionner(precedente, nouvelle, {"club_enfants_requis"})

    assert fusion.club_enfants_requis is False


def test_les_listes_heritees_sont_copiees():
    """Sans copie, modifier la demande fusionnee modifierait la precedente."""
    precedente = demande_de_reference()
    nouvelle = Demande(budget_total_max=3000)
    fusion = fusionner(precedente, nouvelle, {"budget_total_max"})

    fusion.destinations.append("Malte")
    assert precedente.destinations == ["Crete", "Sicile"]


# --------------------------------------------------------------------------
# champs_fournis
# --------------------------------------------------------------------------


def test_champ_present_et_valide_compte_comme_fourni():
    donnees = {"budget_total_max": 3000, "destinations": ["Crete"]}
    demande = Demande(budget_total_max=3000, destinations=["Crete"])
    fournis = champs_fournis(donnees, demande)

    assert "budget_total_max" in fournis
    assert "destinations" in fournis


def test_champ_propose_mais_ecarte_ne_compte_pas_comme_fourni():
    """Le modele a propose une date, `nettoyer()` l'a refusee : la demande
    precedente garde la sienne plutot que de la perdre."""
    donnees = {"date_debut": "juillet prochain"}
    demande = Demande(date_debut=None, non_precise=["date de debut"])
    assert "date_debut" not in champs_fournis(donnees, demande)


def test_adultes_absent_de_la_reponse_n_est_pas_fourni():
    """La Demande vaut 2 adultes par defaut : sans la cle, impossible de
    savoir si le client l'a dit. On ne l'ecrase donc pas."""
    donnees = {"budget_total_max": 3000}
    demande = Demande(adultes=2, budget_total_max=3000)
    assert "adultes" not in champs_fournis(donnees, demande)


def test_adultes_present_dans_la_reponse_est_fourni():
    donnees = {"adultes": 3}
    demande = Demande(adultes=3)
    assert "adultes" in champs_fournis(donnees, demande)


def test_club_enfants_present_a_false_est_fourni():
    donnees = {"club_enfants_requis": False}
    demande = Demande(club_enfants_requis=False)
    assert "club_enfants_requis" in champs_fournis(donnees, demande)


# --------------------------------------------------------------------------
# extraire(precedente=...)
# --------------------------------------------------------------------------


REPONSE_SUITE = '{"budget_total_max": 3000}'


def test_extraire_sans_precedente_lit_la_phrase_seule():
    """Le comportement d'avant, inchange : rien n'est repris."""
    with patch("comptoir.extraction.appeler_ollama", return_value=REPONSE_SUITE):
        demande = extraire("Meme chose mais pas plus de 3000 euros.")

    assert demande.budget_total_max == 3000
    assert demande.destinations == []
    assert demande.voyageurs == 2


def test_extraire_avec_precedente_complete_la_demande():
    """Le cas q03 : la phrase ne parle que du budget, la demande reste
    celle de quatre voyageurs en Crete ou en Sicile."""
    with patch("comptoir.extraction.appeler_ollama", return_value=REPONSE_SUITE):
        demande = extraire(
            "Meme chose mais pas plus de 3000 euros.",
            precedente=demande_de_reference(),
        )

    assert demande.budget_total_max == 3000
    assert demande.destinations == ["Crete", "Sicile"]
    assert demande.voyageurs == 4
    assert demande.formules == ["tout_compris"]
    assert demande.depart == "TLS"


def test_extraire_avec_precedente_laisse_le_modele_corriger_un_critere():
    """Le cas q07 : « pareil mais en Crete » ne garde pas la Sicile."""
    with patch("comptoir.extraction.appeler_ollama", return_value='{"destinations": ["Crete"]}'):
        demande = extraire("Pareil mais en Crete.", precedente=demande_de_reference())

    assert demande.destinations == ["Crete"]
    assert demande.voyageurs == 4
