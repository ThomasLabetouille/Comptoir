"""Aide interne partagee par extraction.py et redaction.py : isoler et
decoder l'objet JSON dans une reponse de modele.

Les deux pipelines font exactement la meme chose sur des sorties de modele
differentes - tolerer les balises markdown, la prose autour, le JSON tronque
- donc ce module porte le code commun. Prefixe d'underscore : ce n'est pas
une piece de l'API publique du projet, seulement un detail d'implementation
partage.
"""

from __future__ import annotations

import json
import re


def extraire_json(brut: str, erreur_cls: type[Exception]) -> dict:
    """Isole et decode l'objet JSON dans une reponse de modele, tolerante
    aux balises markdown et a la prose autour. Leve `erreur_cls` (fournie
    par l'appelant, pour que l'erreur porte le nom du bon pipeline) si rien
    d'exploitable n'est trouve."""
    texte = brut.strip()

    if texte.startswith("```"):
        texte = re.sub(r"^```[a-zA-Z]*\n?", "", texte)
        texte = re.sub(r"\n?```\s*$", "", texte)
        texte = texte.strip()

    try:
        donnees = json.loads(texte)
    except json.JSONDecodeError:
        donnees = None

    if donnees is None:
        debut = texte.find("{")
        if debut == -1:
            raise erreur_cls(f"aucun JSON dans la reponse du modele :\n{brut[:500]}")

        profondeur = 0
        fin = None
        for indice in range(debut, len(texte)):
            if texte[indice] == "{":
                profondeur += 1
            elif texte[indice] == "}":
                profondeur -= 1
                if profondeur == 0:
                    fin = indice
                    break
        if fin is None:
            raise erreur_cls(f"JSON tronque dans la reponse du modele :\n{brut[:500]}")

        candidat = texte[debut : fin + 1]
        try:
            donnees = json.loads(candidat)
        except json.JSONDecodeError as erreur:
            raise erreur_cls(f"JSON invalide ({erreur}) :\n{candidat[:500]}") from erreur

    if not isinstance(donnees, dict):
        raise erreur_cls(f"le JSON extrait n'est pas un objet : {donnees!r}")
    return donnees
