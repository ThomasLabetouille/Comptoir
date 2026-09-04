"""Mesure en conditions reelles : extraction + redaction sur les 20 requetes
du jeu de test, avec Ollama effectivement lance.

tests/test_extraction.py et tests/test_redaction.py testent le nettoyage et
la verification avec des reponses de modele simulees, deliberement
imparfaites - c'est ce qui permet a la suite de tourner sans reseau, y
compris dans la CI. Mais ca ne dit rien de ce qui se passe quand un vrai
modele traite les 20 requetes ecrites "comme un client parle" plutot que
leur demande structuree de reference. Ce script fait tourner le pipeline
complet - texte libre -> Demande -> Resultat -> reponse redigee - sur le
modele local, et rapporte trois chiffres :

- extraction reussie : combien de requetes ont produit une Demande sans
  erreur reseau ni JSON illisible ;
- abstention : sur les requetes deliberement insolubles, combien le moteur
  a effectivement refuse de proposer quoi que ce soit ;
- tracabilite : sur les requetes qui ont produit une reponse redigee, la
  part des affirmations du modele qui ont survecu a la verification.

Lancer (Ollama doit tourner sur cette machine) :
    python3 outils/mesurer.py
    python3 outils/mesurer.py --sortie data/mesures_tracabilite.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from comptoir.catalogue import charger  # noqa: E402
from comptoir.extraction import (  # noqa: E402
    ErreurExtraction,
    OLLAMA_HOTE_PAR_DEFAUT,
    OLLAMA_MODELE_PAR_DEFAUT,
    extraire,
)
from comptoir.filtres import filtrer  # noqa: E402
from comptoir.redaction import ErreurRedaction, rediger  # noqa: E402

REQUETES = RACINE / "tests" / "requetes.jsonl"


def charger_requetes() -> list[dict]:
    lignes = REQUETES.read_text(encoding="utf-8").splitlines()
    return [json.loads(ligne) for ligne in lignes if ligne.strip()]


def mesurer_une_requete(requete: dict, catalogue: list[dict], *, hote: str, modele: str) -> dict:
    """Fait tourner le pipeline complet sur une requete et rapporte ce qui
    s'est passe. Ne leve jamais : une requete qui echoue est journalisee,
    pas fatale pour les 19 autres."""
    ligne: dict = {"id": requete["id"], "texte": requete["texte"]}

    debut = time.monotonic()
    try:
        demande = extraire(requete["texte"], hote=hote, modele=modele)
    except ErreurExtraction as erreur:
        ligne["erreur_extraction"] = str(erreur)
        return ligne
    ligne["duree_extraction_s"] = round(time.monotonic() - debut, 2)
    ligne["non_precise"] = demande.non_precise

    resultat = filtrer(catalogue, demande)
    ligne["nombre_propositions"] = len(resultat.propositions)
    ligne["insoluble_attendu"] = bool(requete["attendu"].get("insoluble"))
    ligne["insoluble_obtenu"] = not bool(resultat)

    if not resultat:
        return ligne

    debut_redaction = time.monotonic()
    try:
        _texte, redaction = rediger(demande, resultat, hote=hote, modele=modele)
    except ErreurRedaction as erreur:
        ligne["erreur_redaction"] = str(erreur)
        return ligne
    ligne["duree_redaction_s"] = round(time.monotonic() - debut_redaction, 2)

    if redaction is not None:
        ligne["affirmations_produites"] = redaction.nombre_produites
        ligne["affirmations_rejetees"] = len(redaction.rejetees)
        ligne["taux_de_verification"] = redaction.taux_de_verification()

    return ligne


def resumer(lignes: list[dict]) -> dict:
    total = len(lignes)
    extraction_ok = [l for l in lignes if "erreur_extraction" not in l]

    attendues_insolubles = [l for l in extraction_ok if l.get("insoluble_attendu")]
    abstention_correcte = [l for l in attendues_insolubles if l.get("insoluble_obtenu")]

    taux = [l["taux_de_verification"] for l in extraction_ok if l.get("taux_de_verification") is not None]

    return {
        "total_requetes": total,
        "extraction_reussie": f"{len(extraction_ok)}/{total}",
        "abstention_correcte": f"{len(abstention_correcte)}/{len(attendues_insolubles)}" if attendues_insolubles else "n/a",
        "tracabilite_moyenne": round(sum(taux) / len(taux), 3) if taux else None,
        "tracabilite_sur_n_reponses": len(taux),
    }


def afficher(lignes: list[dict], resume: dict) -> None:
    for ligne in lignes:
        print(f"[{ligne['id']}] {ligne['texte'][:70]}")
        if "erreur_extraction" in ligne:
            print(f"  extraction en echec : {ligne['erreur_extraction']}")
        elif "erreur_redaction" in ligne:
            print(f"  {ligne['nombre_propositions']} proposition(s) ; redaction en echec : {ligne['erreur_redaction']}")
        elif ligne["nombre_propositions"] == 0:
            marque = "OK" if ligne["insoluble_attendu"] else "INATTENDU"
            print(f"  aucune proposition ({marque} - insoluble attendu: {ligne['insoluble_attendu']})")
        else:
            taux = ligne.get("taux_de_verification")
            taux_txt = f"{taux:.0%}" if taux is not None else "n/a"
            print(
                f"  {ligne['nombre_propositions']} proposition(s), "
                f"{ligne.get('affirmations_produites', 0)} affirmation(s) produites, "
                f"{ligne.get('affirmations_rejetees', 0)} rejetee(s), tracabilite {taux_txt}"
            )
        print()

    print("=" * 78)
    for cle, valeur in resume.items():
        print(f"  {cle}: {valeur}")


def construire_analyseur() -> argparse.ArgumentParser:
    a = argparse.ArgumentParser(prog="mesurer.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--hote", default=OLLAMA_HOTE_PAR_DEFAUT)
    a.add_argument("--modele", default=OLLAMA_MODELE_PAR_DEFAUT)
    a.add_argument("--sortie", metavar="FICHIER.json", help="ecrit aussi le detail complet dans ce fichier JSON")
    return a


def principal(argv: list[str]) -> int:
    args = construire_analyseur().parse_args(argv)
    catalogue = charger()
    requetes = charger_requetes()

    lignes = [
        mesurer_une_requete(requete, catalogue, hote=args.hote, modele=args.modele)
        for requete in requetes
    ]
    resume = resumer(lignes)
    afficher(lignes, resume)

    if args.sortie:
        chemin = Path(args.sortie)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(
            json.dumps({"resume": resume, "detail": lignes}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nDetail complet ecrit dans {chemin}")

    return 0


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv[1:]))
