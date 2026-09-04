"""Schema d'une fiche sejour et validation d'un catalogue.

Volontairement sans dependance externe : le catalogue est la matiere premiere
de tout le reste, sa validation doit pouvoir tourner partout, tout de suite.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

GAMMES = {
    "club",
    "club_premium",
    "club_evasion",
    "city",
    "circuit",
    "autotour",
    "croisiere",
}

FORMULES = {
    "tout_compris",
    "pension_complete",
    "demi_pension",
    "petit_dejeuner",
    "sans_repas",
}

AMBIANCES = {
    "famille",
    "calme",
    "animation",
    "plage",
    "nature",
    "culture",
    "romantique",
    "sportif",
    "luxe",
    "itinerant",
}

ID_VALIDE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
IATA_VALIDE = re.compile(r"^[A-Z]{3}$")

CHAMPS_REQUIS = (
    "id",
    "nom",
    "gamme",
    "pays",
    "region",
    "aeroports_depart",
    "durees_nuits",
    "formule",
    "prix_pp_par_duree",
    "capacite_max_chambre",
    "enfants_acceptes",
    "periodes_ouverture",
    "ambiance",
    "equipements",
    "points_forts",
    "points_faibles",
)


def sans_accent(texte: str) -> str:
    """Normalise pour comparer 'Crete', 'Crète' et 'CRETE'."""
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn").lower().strip()


def _parse_date(valeur: str) -> date:
    return date.fromisoformat(valeur)


def valider_fiche(fiche: dict) -> list[str]:
    """Retourne la liste des problemes trouves. Liste vide = fiche valide."""
    problemes: list[str] = []
    ident = fiche.get("id", "<sans id>")

    def souci(message: str) -> None:
        problemes.append(f"{ident}: {message}")

    for champ in CHAMPS_REQUIS:
        if champ not in fiche:
            souci(f"champ manquant '{champ}'")
    if problemes:
        return problemes

    if not ID_VALIDE.match(fiche["id"]):
        souci("id invalide (attendu: minuscules et tirets)")

    if not fiche["nom"].strip():
        souci("nom vide")

    if fiche["gamme"] not in GAMMES:
        souci(f"gamme inconnue '{fiche['gamme']}' (attendu: {sorted(GAMMES)})")

    if fiche["formule"] not in FORMULES:
        souci(f"formule inconnue '{fiche['formule']}'")

    aeroports = fiche["aeroports_depart"]
    if not aeroports:
        souci("aucun aeroport de depart")
    for code in aeroports:
        if not IATA_VALIDE.match(code):
            souci(f"code aeroport invalide '{code}' (attendu: 3 majuscules)")

    durees = fiche["durees_nuits"]
    if not durees:
        souci("aucune duree proposee")
    for nuits in durees:
        if not isinstance(nuits, int) or nuits < 1:
            souci(f"duree invalide '{nuits}'")

    prix = fiche["prix_pp_par_duree"]
    if not prix:
        souci("aucun prix")
    for cle, montant in prix.items():
        try:
            nuits = int(cle)
        except (TypeError, ValueError):
            souci(f"cle de prix non numerique '{cle}'")
            continue
        if nuits not in durees:
            souci(f"prix pour {nuits} nuits, mais cette duree n'est pas proposee")
        if not isinstance(montant, int) or montant <= 0:
            souci(f"prix invalide pour {nuits} nuits: '{montant}'")
    for nuits in durees:
        if str(nuits) not in prix:
            souci(f"duree {nuits} nuits proposee sans prix associe")

    if not isinstance(fiche["capacite_max_chambre"], int) or fiche["capacite_max_chambre"] < 1:
        souci("capacite_max_chambre invalide")

    if not isinstance(fiche["enfants_acceptes"], bool):
        souci("enfants_acceptes doit valoir true ou false")

    club = fiche.get("club_enfants")
    if club is not None:
        if not fiche["enfants_acceptes"]:
            souci("club enfants declare alors que les enfants ne sont pas acceptes")
        if not (isinstance(club, dict) and "age_min" in club and "age_max" in club):
            souci("club_enfants doit contenir age_min et age_max")
        elif club["age_min"] >= club["age_max"]:
            souci("club_enfants: age_min doit etre inferieur a age_max")

    periodes = fiche["periodes_ouverture"]
    if not periodes:
        souci("aucune periode d'ouverture")
    for periode in periodes:
        try:
            debut = _parse_date(periode["debut"])
            fin = _parse_date(periode["fin"])
        except (KeyError, ValueError, TypeError):
            souci(f"periode d'ouverture illisible: {periode}")
            continue
        if debut >= fin:
            souci(f"periode d'ouverture inversee: {periode}")

    for valeur in fiche["ambiance"]:
        if valeur not in AMBIANCES:
            souci(f"ambiance inconnue '{valeur}' (attendu: {sorted(AMBIANCES)})")

    if not fiche["points_forts"]:
        souci("aucun point fort")

    # Un catalogue qui ne dit que du bien n'est pas utilisable par un agent :
    # il a besoin de savoir quoi annoncer avant que le client le decouvre sur place.
    if not fiche["points_faibles"]:
        souci("aucun point faible (obligatoire : voir README)")

    for nom_alias in fiche.get("alias", []):
        if not isinstance(nom_alias, str) or not nom_alias.strip():
            souci(f"alias invalide '{nom_alias}'")

    note = fiche.get("note_clients")
    if note is not None and not (0 <= note <= 10):
        souci(f"note_clients hors bornes: {note}")

    return problemes


def valider_catalogue(fiches: list[dict]) -> list[str]:
    """Valide chaque fiche, plus les regles qui portent sur l'ensemble."""
    problemes: list[str] = []
    vus: dict[str, int] = {}

    for index, fiche in enumerate(fiches):
        problemes.extend(valider_fiche(fiche))
        ident = fiche.get("id")
        if ident is not None:
            if ident in vus:
                problemes.append(f"{ident}: identifiant en double (deja vu en position {vus[ident]})")
            else:
                vus[ident] = index

    if not fiches:
        problemes.append("catalogue vide")

    return problemes
