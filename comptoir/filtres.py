"""Le filtrage dur : la partie que le modele de langage ne fait jamais.

Regle du projet : tout ce qui est verifiable - un prix, une date, une capacite,
une formule - est decide ici, en Python. Un modele de langage sert a comprendre
la demande et a rediger la reponse, jamais a trancher si 3200 est inferieur a 3500.

Consequence pratique : ce module n'importe aucun modele, ne fait aucun appel
reseau, et se teste entierement hors ligne.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .demande import Demande
from .schema import sans_accent

# Hypothese simplificatrice du prototype, assumee et documentee :
# un enfant de moins de 12 ans paie 70 % du prix adulte. Un vrai catalogue
# porte cette regle par fiche et par periode.
AGE_TARIF_ENFANT = 12
PART_ENFANT = 0.7


# --------------------------------------------------------------------------
# Prix
# --------------------------------------------------------------------------

def parts_payantes(demande: Demande) -> float:
    parts = float(demande.adultes)
    for age in demande.enfants_ages:
        parts += PART_ENFANT if age < AGE_TARIF_ENFANT else 1.0
    return parts


def durees_possibles(fiche: dict, demande: Demande) -> list[int]:
    """Durees de la fiche compatibles avec la duree demandee."""
    if demande.duree_nuits is None:
        return sorted(fiche["durees_nuits"])
    return [n for n in fiche["durees_nuits"] if n == demande.duree_nuits]


def prix_total(fiche: dict, demande: Demande, nuits: int) -> int:
    prix_pp = fiche["prix_pp_par_duree"][str(nuits)]
    return round(prix_pp * parts_payantes(demande))


def meilleur_prix(fiche: dict, demande: Demande) -> tuple[int, int] | None:
    """(prix_total, nuits) le moins cher parmi les durees compatibles."""
    options = [(prix_total(fiche, demande, n), n) for n in durees_possibles(fiche, demande)]
    return min(options) if options else None


# --------------------------------------------------------------------------
# Criteres durs
# --------------------------------------------------------------------------

def _correspond_destination(fiche: dict, cible: str) -> bool:
    cible_n = sans_accent(cible)
    if not cible_n:
        return True
    for champ in (fiche["pays"], fiche["region"], *fiche.get("alias", [])):
        champ_n = sans_accent(champ)
        if cible_n == champ_n or cible_n in champ_n or champ_n in cible_n:
            return True
    return False


def critere_destination(fiche: dict, demande: Demande) -> bool:
    if not demande.destinations:
        return True
    return any(_correspond_destination(fiche, cible) for cible in demande.destinations)


def critere_duree(fiche: dict, demande: Demande) -> bool:
    return bool(durees_possibles(fiche, demande))


def critere_periode(fiche: dict, demande: Demande) -> bool:
    """Le sejour doit tenir entierement dans la fenetre demandee ET dans une
    periode d'ouverture de l'etablissement."""
    if demande.date_debut is None and demande.date_fin is None:
        return True

    debut_voulu = date.fromisoformat(demande.date_debut) if demande.date_debut else date.min
    fin_voulue = date.fromisoformat(demande.date_fin) if demande.date_fin else date.max

    nuits_mini = demande.duree_nuits or min(fiche["durees_nuits"])

    for periode in fiche["periodes_ouverture"]:
        ouverture = date.fromisoformat(periode["debut"])
        fermeture = date.fromisoformat(periode["fin"])
        debut = max(debut_voulu, ouverture)
        fin = min(fin_voulue, fermeture)
        if fin - debut >= timedelta(days=nuits_mini):
            return True
    return False


def critere_capacite(fiche: dict, demande: Demande) -> bool:
    return demande.voyageurs <= fiche["capacite_max_chambre"]


def critere_enfants(fiche: dict, demande: Demande) -> bool:
    if not demande.enfants_ages:
        return True
    return bool(fiche["enfants_acceptes"])


def critere_club_enfants(fiche: dict, demande: Demande) -> bool:
    """Un client qui demande un club enfants demande qu'il accueille SES enfants."""
    if not demande.club_enfants_requis:
        return True
    club = fiche.get("club_enfants")
    if not club:
        return False
    if not demande.enfants_ages:
        return True
    return any(club["age_min"] <= age <= club["age_max"] for age in demande.enfants_ages)


def critere_formule(fiche: dict, demande: Demande) -> bool:
    if not demande.formules:
        return True
    return fiche["formule"] in demande.formules


def critere_depart(fiche: dict, demande: Demande) -> bool:
    if demande.depart is None:
        return True
    return demande.depart in fiche["aeroports_depart"]


def critere_budget(fiche: dict, demande: Demande) -> bool:
    if demande.budget_total_max is None and demande.budget_pp_max is None:
        return True
    for nuits in durees_possibles(fiche, demande):
        total = prix_total(fiche, demande, nuits)
        if demande.budget_total_max is not None and total > demande.budget_total_max:
            continue
        if demande.budget_pp_max is not None:
            if fiche["prix_pp_par_duree"][str(nuits)] > demande.budget_pp_max:
                continue
        return True
    return False


CRITERES: dict[str, callable] = {
    "destination": critere_destination,
    "duree": critere_duree,
    "periode": critere_periode,
    "capacite": critere_capacite,
    "enfants": critere_enfants,
    "club_enfants": critere_club_enfants,
    "formule": critere_formule,
    "depart": critere_depart,
    "budget": critere_budget,
}

# Du plus facile a assouplir pour un client au moins facile.
ORDRE_DE_NEGOCIATION = (
    "budget",
    "periode",
    "duree",
    "formule",
    "depart",
    "club_enfants",
    "capacite",
    "destination",
)

LIBELLES = {
    "destination": "la destination",
    "duree": "la duree du sejour",
    "periode": "les dates",
    "capacite": "le nombre de voyageurs par chambre",
    "enfants": "la presence d'enfants",
    "club_enfants": "l'exigence d'un club enfants adapte a l'age",
    "formule": "la formule de restauration",
    "depart": "l'aeroport de depart",
    "budget": "le budget",
}


# --------------------------------------------------------------------------
# Resultat
# --------------------------------------------------------------------------

@dataclass
class Proposition:
    fiche: dict
    prix_total: int
    nuits: int


@dataclass
class Resultat:
    propositions: list[Proposition] = field(default_factory=list)
    # Pour chaque critere : combien de fiches passeraient si on relachait
    # UNIQUEMENT ce critere. C'est ce chiffre qui permet de dire au client
    # quoi assouplir, au lieu de lui repondre "aucun resultat".
    debloquerait: dict[str, int] = field(default_factory=dict)
    prix_minimum_atteignable: int | None = None

    def __bool__(self) -> bool:
        return bool(self.propositions)

    def diagnostic(self) -> str:
        """Phrase a afficher quand rien ne correspond."""
        if self.propositions:
            return f"{len(self.propositions)} sejour(s) correspondent a la demande."

        # L'ordre n'est pas celui du nombre d'options : un agent negocie d'abord
        # le budget et les dates, et touche a la destination en dernier recours.
        pistes = [
            (self.debloquerait[critere], critere)
            for critere in ORDRE_DE_NEGOCIATION
            if self.debloquerait.get(critere, 0) > 0
        ]
        if not pistes:
            return (
                "Aucun sejour ne correspond, et relacher un seul critere ne suffirait pas. "
                "Il faut revoir la demande plus largement."
            )

        morceaux = []
        for nombre, critere in pistes[:3]:
            detail = LIBELLES[critere]
            if critere == "budget" and self.prix_minimum_atteignable is not None:
                detail += f" (le moins cher qui correspond est a {self.prix_minimum_atteignable} EUR au total)"
            morceaux.append(f"{detail} : {nombre} option(s) s'ouvriraient")
        return "Aucun sejour ne correspond. En relachant un seul critere - " + " ; ".join(morceaux) + "."


def filtrer(catalogue: list[dict], demande: Demande) -> Resultat:
    """Applique tous les criteres durs, et mesure ce qui bloque quand rien ne passe."""
    retenues: list[Proposition] = []
    echecs_par_fiche: dict[str, set[str]] = {}

    for fiche in catalogue:
        echecs = {nom for nom, teste in CRITERES.items() if not teste(fiche, demande)}
        echecs_par_fiche[fiche["id"]] = echecs
        if not echecs:
            meilleur = meilleur_prix(fiche, demande)
            if meilleur is None:
                # Ne devrait pas arriver : critere_duree l'aurait deja ecartee.
                continue
            prix, nuits = meilleur
            retenues.append(Proposition(fiche=fiche, prix_total=prix, nuits=nuits))

    retenues.sort(key=lambda p: p.prix_total)

    # Une fiche "debloquee par X" est une fiche dont X est le SEUL critere en echec.
    debloquerait = {nom: 0 for nom in CRITERES}
    for echecs in echecs_par_fiche.values():
        if len(echecs) == 1:
            debloquerait[next(iter(echecs))] += 1

    prix_minimum = None
    candidats = [
        fiche
        for fiche in catalogue
        if echecs_par_fiche[fiche["id"]] == {"budget"}
    ]
    if candidats:
        prix_possibles = []
        for fiche in candidats:
            for nuits in durees_possibles(fiche, demande):
                prix_possibles.append(prix_total(fiche, demande, nuits))
        if prix_possibles:
            prix_minimum = min(prix_possibles)

    return Resultat(
        propositions=retenues,
        debloquerait=debloquerait,
        prix_minimum_atteignable=prix_minimum,
    )
