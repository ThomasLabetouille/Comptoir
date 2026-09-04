# -*- coding: utf-8 -*-
"""Interroger le moteur en ligne de commande.

Rejouer une demande du jeu de test :
    python3 outils/chercher.py q02
    python3 outils/chercher.py --toutes

Essayer sa propre demande, en la composant champ par champ :
    python3 outils/chercher.py --essai --destination Crete --nuits 7 --budget 2000

Ou en langage libre, via le modele local (Ollama doit tourner) :
    python3 outils/chercher.py --texte "on est quatre, deux enfants de 8 et 14 ans, \
Crete ou Sicile, deuxieme quinzaine de juillet, tout compris, 3500 euros, depart Toulouse"

Ajouter --rediger a n'importe laquelle des commandes ci-dessus pour que le modele
redige une reponse en langage naturel, verifiee affirmation par affirmation contre
les fiches retenues (Ollama doit tourner) :
    python3 outils/chercher.py q02 --rediger
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from comptoir.catalogue import charger  # noqa: E402
from comptoir.demande import Demande  # noqa: E402
from comptoir.extraction import (  # noqa: E402
    ErreurExtraction,
    OLLAMA_HOTE_PAR_DEFAUT,
    OLLAMA_MODELE_PAR_DEFAUT,
    extraire,
)
from comptoir.filtres import filtrer  # noqa: E402
from comptoir.redaction import ErreurRedaction, rediger  # noqa: E402
from comptoir.schema import FORMULES  # noqa: E402

REQUETES = RACINE / "tests" / "requetes.jsonl"


def charger_requetes() -> dict[str, dict]:
    lignes = REQUETES.read_text(encoding="utf-8").splitlines()
    return {r["id"]: r for r in (json.loads(l) for l in lignes if l.strip())}


def afficher_non_precise(demande: Demande) -> None:
    if demande.non_precise:
        print("  Non precise ou ecarte : " + ", ".join(demande.non_precise))
        print()


def resume_demande(demande: Demande) -> str:
    morceaux = [f"{demande.voyageurs} voyageur(s)"]
    if demande.enfants_ages:
        morceaux.append("enfants " + ", ".join(f"{a} ans" for a in demande.enfants_ages))
    if demande.destinations:
        morceaux.append(" / ".join(demande.destinations))
    if demande.duree_nuits:
        morceaux.append(f"{demande.duree_nuits} nuits")
    if demande.date_debut or demande.date_fin:
        morceaux.append(f"{demande.date_debut or '...'} -> {demande.date_fin or '...'}")
    if demande.formules:
        morceaux.append(" ou ".join(f.replace("_", " ") for f in demande.formules))
    if demande.depart:
        morceaux.append(f"depart {demande.depart}")
    if demande.club_enfants_requis:
        morceaux.append("club enfants exige")
    if demande.budget_total_max:
        morceaux.append(f"max {demande.budget_total_max} EUR")
    return " | ".join(morceaux)


def afficher(demande: Demande, catalogue: list[dict], texte: str | None = None,
             etiquette: str = "", rediger_option: dict | None = None) -> None:
    resultat = filtrer(catalogue, demande)

    print("=" * 78)
    if texte:
        print(f"{etiquette} Le client dit :")
        print(f"  « {texte} »")
        print()
    print("  " + resume_demande(demande))
    print()
    afficher_non_precise(demande)

    if not resultat:
        print("  " + resultat.diagnostic())
        print()
        return

    for rang, proposition in enumerate(resultat.propositions[:3], 1):
        fiche = proposition.fiche
        prix_pp = fiche["prix_pp_par_duree"][str(proposition.nuits)]
        print(f"  {rang}. {fiche['nom']} - {fiche['region']}, {fiche['pays']}")
        print(
            f"     {proposition.nuits} nuits, {fiche['formule'].replace('_', ' ')}, "
            f"{proposition.prix_total} EUR au total ({prix_pp} EUR/personne)"
        )
        print(f"     + {fiche['points_forts'][0]}")
        print(f"     - {fiche['points_faibles'][0]}")
        print(f"     [fiche: {fiche['id']}]")
        print()

    reste = len(resultat.propositions) - 3
    if reste > 0:
        print(f"  ({reste} autre(s) sejour(s) correspondent aussi)")
        print()

    if rediger_option is not None:
        try:
            texte_redige, redaction = rediger(
                demande, resultat,
                hote=rediger_option["hote"], modele=rediger_option["modele"],
            )
        except ErreurRedaction as erreur:
            print(f"  Redaction impossible : {erreur}")
            print()
            return
        print("  --- Reponse redigee (verifiee contre les fiches ci-dessus) ---")
        for ligne in texte_redige.splitlines():
            print(f"  {ligne}")
        if redaction is not None and redaction.rejetees:
            print(f"  ({len(redaction.rejetees)} affirmation(s) du modele rejetee(s) a la verification)")
        print()


def construire_analyseur() -> argparse.ArgumentParser:
    a = argparse.ArgumentParser(
        prog="chercher.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    a.add_argument("requete", nargs="?", help="identifiant d'une requete du jeu de test (q01, q02...)")
    a.add_argument("--toutes", action="store_true", help="rejouer toutes les requetes du jeu de test")
    a.add_argument("--essai", action="store_true", help="composer sa propre demande avec les options ci-dessous")
    a.add_argument("--texte", metavar="PHRASE",
                   help="demande en langage libre, extraite via le modele local (Ollama)")
    a.add_argument("--rediger", action="store_true",
                   help="rediger une reponse en langage naturel via le modele local, "
                        "avec verification des citations (Ollama doit tourner)")
    a.add_argument("--hote", default=OLLAMA_HOTE_PAR_DEFAUT, help=f"defaut: {OLLAMA_HOTE_PAR_DEFAUT}")
    a.add_argument("--modele", default=OLLAMA_MODELE_PAR_DEFAUT, help=f"defaut: {OLLAMA_MODELE_PAR_DEFAUT}")
    a.add_argument("--adultes", type=int, default=2)
    a.add_argument("--enfants", type=int, nargs="*", default=[], metavar="AGE",
                   help="ages des enfants, ex: --enfants 8 14")
    a.add_argument("--destination", nargs="*", default=[], metavar="LIEU",
                   help="pays, region ou alias, ex: --destination Crete Sicile")
    a.add_argument("--du", dest="date_debut", metavar="AAAA-MM-JJ")
    a.add_argument("--au", dest="date_fin", metavar="AAAA-MM-JJ")
    a.add_argument("--nuits", type=int)
    a.add_argument("--budget", type=int, metavar="EUR", help="budget total, tous voyageurs")
    a.add_argument("--budget-pp", type=int, metavar="EUR", help="budget par personne")
    a.add_argument("--formule", nargs="*", default=[], choices=sorted(FORMULES))
    a.add_argument("--depart", metavar="IATA", help="ex: TLS, ORY, NTE")
    a.add_argument("--club-enfants", action="store_true", help="exiger un club enfants adapte aux ages donnes")
    a.add_argument("--ambiance", nargs="*", default=[], metavar="MOT")
    return a


def principal(argv: list[str]) -> int:
    analyseur = construire_analyseur()
    args = analyseur.parse_args(argv)
    catalogue = charger()
    requetes = charger_requetes()

    rediger_option = {"hote": args.hote, "modele": args.modele} if args.rediger else None

    if args.texte:
        try:
            demande = extraire(args.texte, hote=args.hote, modele=args.modele)
        except ErreurExtraction as erreur:
            print(f"Extraction impossible : {erreur}")
            return 1
        afficher(demande, catalogue, texte=args.texte, etiquette="[extrait]", rediger_option=rediger_option)
        return 0

    if args.essai:
        demande = Demande(
            adultes=args.adultes,
            enfants_ages=args.enfants,
            destinations=args.destination,
            date_debut=args.date_debut,
            date_fin=args.date_fin,
            duree_nuits=args.nuits,
            budget_total_max=args.budget,
            budget_pp_max=args.budget_pp,
            formules=args.formule,
            depart=args.depart,
            club_enfants_requis=args.club_enfants,
            ambiance=args.ambiance,
        )
        afficher(demande, catalogue, rediger_option=rediger_option)
        return 0

    if args.toutes:
        for requete in requetes.values():
            afficher(
                Demande.depuis_dict(requete["demande"]),
                catalogue,
                texte=requete["texte"],
                etiquette=f"[{requete['id']}]",
                rediger_option=rediger_option,
            )
        return 0

    if args.requete:
        if args.requete not in requetes:
            print(f"Requete inconnue : {args.requete}")
            print("Disponibles :", ", ".join(requetes))
            return 1
        requete = requetes[args.requete]
        afficher(
            Demande.depuis_dict(requete["demande"]),
            catalogue,
            texte=requete["texte"],
            etiquette=f"[{requete['id']}]",
            rediger_option=rediger_option,
        )
        return 0

    analyseur.print_help()
    print()
    print("Requetes disponibles :", ", ".join(requetes))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv[1:]))
