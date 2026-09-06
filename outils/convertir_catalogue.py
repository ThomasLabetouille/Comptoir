# -*- coding: utf-8 -*-
"""Un export CSV de voyagiste -> data/catalogue.json.

Le moteur ne connait pas le catalogue d'un voyagiste en particulier : il
connait une forme de catalogue, decrite par `comptoir/schema.py`. Brancher un
vrai catalogue, c'est donc traduire l'export du voyagiste dans cette forme,
sans toucher au moteur.

Tout le travail tient dans CORRESPONDANCE ci-dessous : a gauche le champ dont
le moteur a besoin, a droite la colonne de l'export qui le remplit. C'est la
seule chose a modifier pour un nouveau catalogue, et elle se remplit en
reunion avec les gens du metier plutot que devant un ecran.

Une ligne qui ne se convertit pas n'interrompt pas la conversion : elle est
refusee, avec son numero et la raison. Un export reel comporte toujours des
lignes incompletes, et il vaut mieux savoir lesquelles que produire un
catalogue a moitie faux.

Lancer :
    python outils/convertir_catalogue.py data/exemple_import.csv
    python outils/convertir_catalogue.py data/exemple_import.csv --sortie data/catalogue.json

Sans --sortie, rien n'est ecrit : le script dit seulement ce qu'il produirait.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from comptoir.schema import valider_catalogue, valider_fiche  # noqa: E402

# Champ attendu par le moteur -> nom de la colonne dans l'export.
# C'est ici, et nulle part ailleurs, qu'on s'adapte a un nouveau fournisseur.
CORRESPONDANCE = {
    "id": "reference",
    "nom": "libelle",
    "gamme": "gamme",
    "pays": "pays",
    "region": "region",
    "aeroports_depart": "aeroports",
    "durees_nuits": "durees",
    "prix_pp_par_duree": "prix_par_personne",
    "formule": "formule",
    "capacite_max_chambre": "capacite_chambre",
    "enfants_acceptes": "enfants_acceptes",
    "periodes_ouverture": "ouverture",
    "ambiance": "ambiance",
    "equipements": "equipements",
    "points_forts": "points_forts",
    "points_faibles": "points_faibles",
    "club_enfants": "club_enfants",
    "note_clients": "note",
    "distance_plage_m": "distance_plage",
    "alias": "alias",
}

# Separateur a l'interieur d'une cellule. Le point-virgule sert deja a separer
# les colonnes dans un export Excel francais.
SEPARATEUR_LISTE = "|"

VRAI = {"oui", "true", "vrai", "1", "o", "y", "yes"}
FAUX = {"non", "false", "faux", "0", "n", ""}


class LigneRefusee(Exception):
    """Cette ligne de l'export n'a pas pu etre convertie."""


def _liste(valeur: str) -> list[str]:
    return [morceau.strip() for morceau in (valeur or "").split(SEPARATEUR_LISTE) if morceau.strip()]


def _entiers(valeur: str, quoi: str) -> list[int]:
    resultat = []
    for morceau in _liste(valeur):
        try:
            resultat.append(int(morceau))
        except ValueError:
            raise LigneRefusee(f"{quoi} : '{morceau}' n'est pas un nombre entier") from None
    return resultat


def _booleen(valeur: str, quoi: str) -> bool:
    net = (valeur or "").strip().lower()
    if net in VRAI:
        return True
    if net in FAUX:
        return False
    raise LigneRefusee(f"{quoi} : '{valeur}' n'est ni oui ni non")


def _periodes(valeur: str) -> list[dict]:
    """« 2027-04-15..2027-10-25 | 2027-12-01..2028-01-05 » -> deux periodes."""
    periodes = []
    for morceau in _liste(valeur):
        bornes = [b.strip() for b in morceau.split("..")]
        if len(bornes) != 2:
            raise LigneRefusee(f"periode d'ouverture : '{morceau}' (attendu : debut..fin)")
        periodes.append({"debut": bornes[0], "fin": bornes[1]})
    return periodes


def _club_enfants(valeur: str) -> dict | None:
    """« 3-12 » -> {age_min: 3, age_max: 12}. Vide -> pas de club."""
    net = (valeur or "").strip()
    if not net:
        return None
    bornes = net.split("-")
    if len(bornes) != 2:
        raise LigneRefusee(f"club enfants : '{net}' (attendu : age_min-age_max)")
    try:
        return {"age_min": int(bornes[0]), "age_max": int(bornes[1])}
    except ValueError:
        raise LigneRefusee(f"club enfants : '{net}' n'est pas une tranche d'ages") from None


def colonne(ligne: dict, champ: str) -> str:
    """La valeur brute de la colonne qui alimente `champ`."""
    nom = CORRESPONDANCE[champ]
    if nom not in ligne:
        raise LigneRefusee(f"colonne '{nom}' absente de l'export (attendue pour '{champ}')")
    return (ligne[nom] or "").strip()


def convertir_ligne(ligne: dict) -> dict:
    """Une ligne de l'export -> une fiche. Leve LigneRefusee si la ligne ne
    peut pas etre traduite ; ne devine jamais une valeur manquante."""
    durees = _entiers(colonne(ligne, "durees_nuits"), "durees")
    prix = _entiers(colonne(ligne, "prix_pp_par_duree"), "prix par personne")
    if len(durees) != len(prix):
        raise LigneRefusee(
            f"{len(durees)} duree(s) pour {len(prix)} prix : chaque duree vendue doit avoir son prix"
        )

    fiche = {
        "id": colonne(ligne, "id"),
        "nom": colonne(ligne, "nom"),
        "gamme": colonne(ligne, "gamme"),
        "pays": colonne(ligne, "pays"),
        "region": colonne(ligne, "region"),
        "aeroports_depart": [code.upper() for code in _liste(colonne(ligne, "aeroports_depart"))],
        "durees_nuits": durees,
        "prix_pp_par_duree": {str(n): p for n, p in zip(durees, prix)},
        "formule": colonne(ligne, "formule"),
        "capacite_max_chambre": _entiers(colonne(ligne, "capacite_max_chambre"), "capacite")[0]
        if colonne(ligne, "capacite_max_chambre")
        else 0,
        "enfants_acceptes": _booleen(colonne(ligne, "enfants_acceptes"), "enfants acceptes"),
        "periodes_ouverture": _periodes(colonne(ligne, "periodes_ouverture")),
        "ambiance": _liste(colonne(ligne, "ambiance")),
        "equipements": _liste(colonne(ligne, "equipements")),
        "points_forts": _liste(colonne(ligne, "points_forts")),
        "points_faibles": _liste(colonne(ligne, "points_faibles")),
    }

    club = _club_enfants(colonne(ligne, "club_enfants"))
    if club is not None:
        fiche["club_enfants"] = club

    note = colonne(ligne, "note_clients")
    if note:
        try:
            fiche["note_clients"] = float(note.replace(",", "."))
        except ValueError:
            raise LigneRefusee(f"note clients : '{note}' n'est pas un nombre") from None

    distance = colonne(ligne, "distance_plage_m")
    if distance:
        fiche["distance_plage_m"] = _entiers(distance, "distance plage")[0]

    alias = _liste(colonne(ligne, "alias"))
    if alias:
        fiche["alias"] = alias

    return fiche


def convertir(lignes: list[dict]) -> tuple[list[dict], list[str]]:
    """Renvoie les fiches converties et la liste des refus, l'un n'empechant
    pas l'autre. Le numero indique est celui de la ligne dans le fichier,
    en-tete comprise : c'est celui qu'affiche un tableur."""
    fiches: list[dict] = []
    refus: list[str] = []

    for numero, ligne in enumerate(lignes, start=2):
        try:
            fiche = convertir_ligne(ligne)
        except LigneRefusee as erreur:
            refus.append(f"ligne {numero} : {erreur}")
            continue

        problemes = valider_fiche(fiche)
        if problemes:
            for probleme in problemes:
                refus.append(f"ligne {numero} : {probleme}")
            continue

        fiches.append(fiche)

    return fiches, refus


def lire_csv(chemin: Path, separateur: str, encodage: str) -> list[dict]:
    with chemin.open(encoding=encodage, newline="") as fichier:
        return list(csv.DictReader(fichier, delimiter=separateur))


def construire_analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(
        description="Convertit un export CSV de catalogue vers le format attendu par le moteur."
    )
    analyseur.add_argument("entree", help="le fichier CSV exporte par le voyagiste")
    analyseur.add_argument(
        "--sortie",
        help="ou ecrire le catalogue converti. Sans cette option, rien n'est ecrit.",
    )
    analyseur.add_argument("--separateur", default=";", help="separateur de colonnes (defaut : ;)")
    analyseur.add_argument("--encodage", default="utf-8-sig", help="encodage du CSV (defaut : utf-8-sig)")
    return analyseur


def principal(argv: list[str]) -> int:
    args = construire_analyseur().parse_args(argv)
    chemin = Path(args.entree)
    if not chemin.exists():
        print(f"Fichier introuvable : {chemin}")
        return 1

    lignes = lire_csv(chemin, args.separateur, args.encodage)
    fiches, refus = convertir(lignes)

    print(f"{len(lignes)} ligne(s) lue(s) dans {chemin}")
    print(f"{len(fiches)} fiche(s) convertie(s), {len(refus)} refusee(s)\n")

    for message in refus:
        print(f"  refuse - {message}")
    if refus:
        print()

    if not fiches:
        print("Aucune fiche exploitable : rien a ecrire.")
        return 1

    problemes = valider_catalogue(fiches)
    if problemes:
        print("Le catalogue produit ne passe pas la validation d'ensemble :")
        for probleme in problemes:
            print(f"  {probleme}")
        return 1

    if not args.sortie:
        print("Catalogue valide. Relancez avec --sortie FICHIER pour l'ecrire.")
        return 0

    destination = Path(args.sortie)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(fiches, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Catalogue ecrit dans {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv[1:]))
