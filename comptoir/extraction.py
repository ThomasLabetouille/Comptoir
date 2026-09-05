"""Texte libre -> Demande structuree, via un modele de langage local.

Le principe du projet s'applique ici aussi : le modele comprend, il ne
decide rien. Concretement :

- le modele produit un JSON, mais ce JSON n'est fiable ni sur la forme
  (peut etre entoure de balises markdown, de prose, tronque) ni sur le fond
  (peut proposer une formule qui n'existe pas, un age hors limites, une
  date mal formee) - `extraire_json()` et `nettoyer()` ne lui font confiance
  sur rien de verifiable ;
- tout ce que le modele n'a pas su remplir, ou que `nettoyer()` a du
  ecarter, atterrit dans `Demande.non_precise` plutot que d'etre devine ou
  silencieusement perdu.

Aucune dependance ajoutee : l'appel a Ollama passe par `urllib` (bibliotheque
standard), pas par le paquet `ollama`. Rien d'autre a installer que ce que
`requirements.txt` liste deja.

Ce module ne peut pas etre teste par appel reseau reel depuis une session de
developpement a distance (Ollama tourne sur la machine de l'utilisateur, pas
sur la machine qui execute ces tests). `tests/test_extraction.py` teste donc
`extraire_json()` et `nettoyer()` avec des reponses de modele simulees, y
compris deliberement imparfaites. `appeler_ollama()` n'est couverte que par
un usage reel, a lancer sur la machine ou Ollama tourne.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date

from . import _json_modele
from .demande import Demande
from .schema import FORMULES, IATA_VALIDE

OLLAMA_HOTE_PAR_DEFAUT = "http://localhost:11434"
# Le modele deja configure et telecharge dans IA_Locale/assistant_local/config.json -
# pas de raison d'en installer un deuxieme pour ce projet.
OLLAMA_MODELE_PAR_DEFAUT = "gemma4:12b"

AGE_ENFANT_MIN = 0
AGE_ENFANT_MAX = 17


class ErreurExtraction(Exception):
    """Le modele n'a pas ete joignable, ou n'a rien produit d'exploitable."""


def construire_prompt(texte_client: str, date_reference: date | None = None) -> str:
    date_reference = date_reference or date.today()
    return f"""Tu extrais une demande de voyage depuis ce qu'un client dit a l'oral \
a un agent. Reponds UNIQUEMENT avec un objet JSON, sans texte autour, sans balises \
markdown. Nous sommes le {date_reference.isoformat()}.

Champs possibles (tous optionnels sauf indication contraire) :
- adultes (entier, defaut 2)
- enfants_ages (liste d'entiers, un age par enfant)
- destinations (liste de chaines : pays, region, ou nom de lieu tel que dit)
- date_debut, date_fin (AAAA-MM-JJ ; deduis l'annee depuis la date d'aujourd'hui
  si le client dit juste un mois - la prochaine occurrence de ce mois)
- duree_nuits (entier)
- budget_total_max (entier, en euros, pour l'ensemble des voyageurs)
- budget_pp_max (entier, en euros, par personne)
- formules (liste parmi exactement : {sorted(FORMULES)})
- depart (code aeroport IATA en majuscules, 3 lettres, ex: TLS, ORY, NTE)
- club_enfants_requis (booleen)
- ambiance (liste de mots libres decrivant l'atmosphere recherchee)
- non_precise (liste de chaines : ce que le client n'a PAS precise et qui
  serait utile de lui demander - ne devine jamais une valeur a la place)

Regle absolue : n'invente jamais une destination, une date, un budget ou une
formule que le client n'a pas donnes. Un champ absent doit rester absent du
JSON, pas rempli au hasard.

Phrase du client :
\"\"\"{texte_client}\"\"\"

JSON :"""


def appeler_ollama(
    texte_client: str,
    *,
    hote: str = OLLAMA_HOTE_PAR_DEFAUT,
    modele: str = OLLAMA_MODELE_PAR_DEFAUT,
    delai_max_s: float = 120.0,
    date_reference: date | None = None,
) -> str:
    """Renvoie le texte brut produit par le modele. N'interprete rien."""
    charge_utile = json.dumps(
        {
            "model": modele,
            "prompt": construire_prompt(texte_client, date_reference),
            "stream": False,
            "format": "json",
            "think": False,
            "options": {
                "temperature": 0.2,
                "num_ctx": 8192,
                "num_predict": 2048,
                "repeat_penalty": 1.3,
            },
        }
    ).encode("utf-8")

    requete = urllib.request.Request(
        f"{hote.rstrip('/')}/api/generate",
        data=charge_utile,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requete, timeout=delai_max_s) as reponse:
            corps = json.loads(reponse.read().decode("utf-8"))
    except urllib.error.URLError as erreur:
        raise ErreurExtraction(
            f"Ollama injoignable sur {hote} - est-il lance ? ({erreur})"
        ) from erreur
    except TimeoutError as erreur:
        raise ErreurExtraction(f"Ollama n'a pas repondu en {delai_max_s:.0f}s") from erreur

    if "response" not in corps:
        raise ErreurExtraction(f"reponse Ollama inattendue, pas de champ 'response': {corps}")
    return corps["response"]


def extraire_json(brut: str) -> dict:
    """Isole et decode l'objet JSON dans une reponse de modele, tolerante
    aux balises markdown et a la prose autour."""
    return _json_modele.extraire_json(brut, ErreurExtraction)


def _entier_positif(valeur, avertissements: list[str], nom: str) -> int | None:
    if valeur is None:
        return None
    try:
        n = int(valeur)
    except (TypeError, ValueError):
        avertissements.append(nom)
        return None
    if n <= 0:
        avertissements.append(nom)
        return None
    return n


def _date_iso(valeur, avertissements: list[str]) -> str | None:
    if valeur is None:
        return None
    try:
        date.fromisoformat(str(valeur))
    except ValueError:
        avertissements.append("dates")
        return None
    return str(valeur)


def _booleen(valeur) -> bool:
    """Ne jamais faire confiance a bool('false') (== True en Python)."""
    if isinstance(valeur, bool):
        return valeur
    if isinstance(valeur, str):
        return valeur.strip().lower() in {"true", "vrai", "oui", "yes"}
    return bool(valeur)


def nettoyer(donnees: dict) -> Demande:
    """Un dict issu du modele -> une Demande valide. Rien de verifiable n'est
    accepte tel quel ; tout ce qui est ecarte est signale dans non_precise."""
    avertissements: list[str] = [str(x) for x in (donnees.get("non_precise") or [])]

    # Un champ absent prend le defaut sans avertissement ; un champ present
    # mais invalide (ex: "beaucoup", 0, -1) est ecarte ET signale - ce n'est
    # pas la meme situation, meme si le resultat final (2 adultes) est identique.
    if donnees.get("adultes") is None:
        adultes = 2
    else:
        adultes = _entier_positif(donnees["adultes"], avertissements, "nombre d'adultes") or 2

    enfants_ages: list[int] = []
    for age in donnees.get("enfants_ages") or []:
        try:
            age_i = int(age)
        except (TypeError, ValueError):
            avertissements.append("age d'un enfant")
            continue
        if AGE_ENFANT_MIN <= age_i <= AGE_ENFANT_MAX:
            enfants_ages.append(age_i)
        else:
            avertissements.append("age d'un enfant")

    destinations = [str(d).strip() for d in (donnees.get("destinations") or []) if str(d).strip()]

    date_debut = _date_iso(donnees.get("date_debut"), avertissements)
    date_fin = _date_iso(donnees.get("date_fin"), avertissements)

    duree_nuits = _entier_positif(donnees.get("duree_nuits"), avertissements, "duree du sejour")
    budget_total_max = _entier_positif(donnees.get("budget_total_max"), avertissements, "budget")
    budget_pp_max = _entier_positif(donnees.get("budget_pp_max"), avertissements, "budget")

    formules: list[str] = []
    for f in donnees.get("formules") or []:
        f_norm = str(f).strip().lower().replace(" ", "_").replace("-", "_")
        if f_norm in FORMULES:
            formules.append(f_norm)
        else:
            avertissements.append(f"formule '{f}' non reconnue")

    depart = donnees.get("depart")
    if depart is not None:
        depart = str(depart).strip().upper()
        if not IATA_VALIDE.match(depart):
            avertissements.append(f"aeroport de depart '{depart}' invalide")
            depart = None

    ambiance = [str(a).strip() for a in (donnees.get("ambiance") or []) if str(a).strip()]

    return Demande(
        adultes=adultes,
        enfants_ages=enfants_ages,
        destinations=destinations,
        date_debut=date_debut,
        date_fin=date_fin,
        duree_nuits=duree_nuits,
        budget_total_max=budget_total_max,
        budget_pp_max=budget_pp_max,
        formules=formules,
        depart=depart,
        club_enfants_requis=_booleen(donnees.get("club_enfants_requis", False)),
        ambiance=ambiance,
        non_precise=avertissements,
    )


def extraire(
    texte_client: str,
    *,
    hote: str = OLLAMA_HOTE_PAR_DEFAUT,
    modele: str = OLLAMA_MODELE_PAR_DEFAUT,
    delai_max_s: float = 120.0,
) -> Demande:
    """Le pipeline complet : appel au modele local, puis nettoyage strict."""
    brut = appeler_ollama(texte_client, hote=hote, modele=modele, delai_max_s=delai_max_s)
    donnees = extraire_json(brut)
    return nettoyer(donnees)
