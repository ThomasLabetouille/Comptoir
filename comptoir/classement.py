"""Classement des propositions retenues, sur ce que le client a dit vouloir
en plus des criteres durs : ambiance, avis clients, proximite de la plage.

`filtrer()` garde son tri par prix inchange - c'est le contrat que
`tests/test_base_sql.py` verifie contre le portage SQL, et dont depend
indirectement le calcul du prix minimum atteignable (diagnostic de
blocage). Ce module est une etape separee, appliquee seulement pour
l'affichage : reordonner ce que `filtrer()` a deja valide, jamais decider
ce qui est valide.

Volontairement pas de RAG ni d'embeddings ici (voir README) : le catalogue
est une poignee de champs structures par fiche, pas un corpus de texte a
chercher par similarite semantique. Une recherche vectorielle serait une
solution a un probleme que ce projet n'a pas. Le score ci-dessous n'est que
des comparaisons, comme le reste du projet - explicable, et testable sans
modele.
"""

from __future__ import annotations

from .demande import Demande
from .filtres import Proposition
from .schema import sans_accent

# Somme a 1.0 : changer ces poids revient a changer ce que "le mieux classe"
# veut dire, pas juste ajuster un detail.
POIDS_AMBIANCE = 0.5
POIDS_NOTE = 0.3
POIDS_PLAGE = 0.2

DISTANCE_PLAGE_MAX_M = 2000  # au-dela, le score de proximite est nul


def score_ambiance(fiche: dict, demande: Demande) -> float:
    """Part des ambiances demandees que cette fiche couvre. 0 si le client
    n'a rien precise - l'ambiance ne doit pas departager des sejours sur un
    critere que personne n'a exprime."""
    if not demande.ambiance:
        return 0.0
    voulues = {sans_accent(a) for a in demande.ambiance}
    disponibles = {sans_accent(a) for a in fiche.get("ambiance", [])}
    return len(voulues & disponibles) / len(voulues)


def score_note(fiche: dict) -> float:
    """Note clients sur 10, ramenee entre 0 et 1. Une fiche sans note n'est
    pas traitee comme une mauvaise note : elle reste neutre (0.5)."""
    note = fiche.get("note_clients")
    if note is None:
        return 0.5
    return max(0.0, min(1.0, note / 10))


def score_plage(fiche: dict) -> float:
    """Proximite de la plage : 1.0 au bord de l'eau, 0.0 au-dela de
    DISTANCE_PLAGE_MAX_M. Neutre (0.5) si la fiche ne precise pas la
    distance - absence d'information, pas mauvais point."""
    distance = fiche.get("distance_plage_m")
    if distance is None:
        return 0.5
    return max(0.0, 1.0 - min(distance, DISTANCE_PLAGE_MAX_M) / DISTANCE_PLAGE_MAX_M)


def score(proposition: Proposition, demande: Demande) -> float:
    fiche = proposition.fiche
    return (
        POIDS_AMBIANCE * score_ambiance(fiche, demande)
        + POIDS_NOTE * score_note(fiche)
        + POIDS_PLAGE * score_plage(fiche)
    )


def classer(propositions: list[Proposition], demande: Demande) -> list[Proposition]:
    """Reordonne par score decroissant. Le tri de Python est stable : deux
    scores egaux gardent l'ordre de depart, qui est deja le prix croissant
    (`filtrer()` trie par prix) - l'egalite se resout donc naturellement par
    le moins cher d'abord, sans cle supplementaire a ecrire."""
    return sorted(propositions, key=lambda p: -score(p, demande))
