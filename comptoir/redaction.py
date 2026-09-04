"""Demande + Resultat -> reponse redigee, avec verification apres coup.

Le meme principe qu'ailleurs dans le projet s'applique ici : le modele
redige, il ne decide rien de verifiable. Concretement :

- le modele ne voit jamais tout le catalogue, seulement les fiches deja
  retenues par `comptoir.filtres.filtrer()` ;
- le modele ne rend pas du texte libre mais un JSON structure ou chaque
  affirmation est explicitement rattachee a un champ d'une fiche ;
- `verifier()` re-cherche chaque affirmation dans la fiche citee. Ce qui ne
  s'y retrouve pas - fiche jamais presentee au modele, champ inexistant,
  chiffre qui ne correspond pas au prix reel - est retire de la reponse et
  journalise dans `Redaction.rejetees`, jamais montre au client ;
- quand `Resultat` est vide, le modele n'est meme pas appele : on renvoie
  `Resultat.diagnostic()` tel quel. Un modele livre a lui-meme prefere
  presque toujours inventer plutot que decevoir ; la seule facon fiable
  d'empecher ca est de ne jamais lui en laisser l'occasion.

Comme `comptoir/extraction.py`, l'appel au modele passe par `urllib` (aucune
dependance ajoutee) et ne peut pas etre teste par un appel reseau reel depuis
une session de developpement a distance : `tests/test_redaction.py` teste
`verifier()` et `assembler()` avec des sorties de modele simulees, y compris
deliberement malhonnetes (fiche inventee, chiffre errone, champ qui n'existe
pas dans la fiche citee).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from . import _json_modele
from .classement import classer
from .demande import Demande
from .filtres import Proposition, Resultat

OLLAMA_HOTE_PAR_DEFAUT = "http://localhost:11434"
OLLAMA_MODELE_PAR_DEFAUT = "gemma4:12b"

# Liste blanche des champs qu'une affirmation peut citer. Un champ absent
# d'ici est refuse meme s'il existe par ailleurs dans le dict fiche - "id"
# par exemple n'est pas une affirmation utile a un client.
CHAMPS_CITABLES = {
    "nom",
    "gamme",
    "pays",
    "region",
    "formule",
    "ambiance",
    "equipements",
    "points_forts",
    "points_faibles",
    "club_enfants",
    "note_clients",
    "aeroports_depart",
}
# Ne viennent pas du dict fiche mais du calcul deja fait par filtrer() pour
# cette demande precise (prix_total depend de la composition familiale).
CHAMPS_CALCULES = {"prix_total", "nuits"}


class ErreurRedaction(Exception):
    """Le modele n'a pas ete joignable, ou n'a rien produit d'exploitable."""


@dataclass
class Affirmation:
    champ: str
    texte: str


@dataclass
class PropositionRedigee:
    fiche_id: str
    affirmations: list[Affirmation] = field(default_factory=list)


@dataclass
class Redaction:
    intro: str
    propositions: list[PropositionRedigee] = field(default_factory=list)
    # Chaque rejet journalise pourquoi une affirmation du modele n'a pas
    # survecu a la verification. Utile pour deboguer un prompt, jamais
    # affiche au client.
    rejetees: list[str] = field(default_factory=list)

    def taux_de_verification(self, nombre_produites: int) -> float | None:
        """Part des affirmations produites par le modele qui ont survecu.
        None si le modele n'a rien produit du tout (rien a mesurer)."""
        if nombre_produites == 0:
            return None
        nombre_retenues = sum(len(p.affirmations) for p in self.propositions)
        return nombre_retenues / nombre_produites


def construire_prompt(demande: Demande, propositions: list[Proposition]) -> str:
    fiches_presentees = []
    for prop in propositions:
        fiche = prop.fiche
        fiches_presentees.append(
            {
                "id": fiche["id"],
                "nom": fiche["nom"],
                "gamme": fiche["gamme"],
                "pays": fiche["pays"],
                "region": fiche["region"],
                "formule": fiche["formule"],
                "ambiance": fiche["ambiance"],
                "equipements": fiche["equipements"],
                "points_forts": fiche["points_forts"],
                "points_faibles": fiche["points_faibles"],
                "club_enfants": fiche.get("club_enfants"),
                "note_clients": fiche.get("note_clients"),
                "aeroports_depart": fiche["aeroports_depart"],
                "prix_total": prop.prix_total,
                "nuits": prop.nuits,
            }
        )

    champs_autorises = sorted(CHAMPS_CITABLES | CHAMPS_CALCULES)
    return f"""Tu rediges une reponse courte pour un agent de voyages, a partir \
UNIQUEMENT des fiches ci-dessous. N'utilise aucune autre information, meme si \
tu la connais par ailleurs sur ces destinations.

Reponds UNIQUEMENT avec un objet JSON de cette forme, sans texte autour, sans \
balises markdown :
{{
  "intro": "une phrase d'accroche courte, SANS chiffre ni fait precis",
  "propositions": [
    {{
      "id": "<id exact d'une des fiches ci-dessous>",
      "affirmations": [
        {{"champ": "<nom du champ source>", "texte": "<phrase qui restitue ce champ>"}}
      ]
    }}
  ]
}}

Champs autorises pour "champ" : {champs_autorises}.
Pour prix_total et nuits, le texte doit contenir le chiffre exact fourni dans la fiche.
N'invente et ne complete rien depuis une connaissance generale du tourisme : une
affirmation qui ne vient pas d'un champ ci-dessous ne doit pas exister. Cite au
moins prix_total et nuits pour chaque proposition, et au moins un point_faible
s'il existe : un agent a besoin de savoir quoi annoncer avant que le client le
decouvre sur place.

Demande du client : {demande.voyageurs} voyageur(s), {demande.destinations or 'destination non precisee'}.

Fiches disponibles :
{json.dumps(fiches_presentees, ensure_ascii=False, indent=2)}

JSON :"""


def appeler_ollama(
    demande: Demande,
    propositions: list[Proposition],
    *,
    hote: str = OLLAMA_HOTE_PAR_DEFAUT,
    modele: str = OLLAMA_MODELE_PAR_DEFAUT,
    delai_max_s: float = 60.0,
) -> str:
    """Renvoie le texte brut produit par le modele. N'interprete rien."""
    charge_utile = json.dumps(
        {
            "model": modele,
            "prompt": construire_prompt(demande, propositions),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
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
        raise ErreurRedaction(
            f"Ollama injoignable sur {hote} - est-il lance ? ({erreur})"
        ) from erreur
    except TimeoutError as erreur:
        raise ErreurRedaction(f"Ollama n'a pas repondu en {delai_max_s:.0f}s") from erreur

    if "response" not in corps:
        raise ErreurRedaction(f"reponse Ollama inattendue, pas de champ 'response': {corps}")
    return corps["response"]


def extraire_json(brut: str) -> dict:
    """Isole et decode l'objet JSON dans une reponse de modele, tolerante
    aux balises markdown et a la prose autour."""
    return _json_modele.extraire_json(brut, ErreurRedaction)


def verifier(brut: dict, propositions: list[Proposition]) -> Redaction:
    """Construit une Redaction a partir du JSON brut du modele, en ne
    conservant que les affirmations verifiables dans les fiches deja
    retenues. Ne leve jamais : ce qui est invalide est journalise dans
    `rejetees`, jamais transmis au client."""
    fiches_par_id = {prop.fiche.get("id"): prop.fiche for prop in propositions}
    calculs_par_id = {prop.fiche.get("id"): {"prix_total": prop.prix_total, "nuits": prop.nuits} for prop in propositions}

    intro = str(brut.get("intro") or "").strip()
    rejetees: list[str] = []
    retenues: list[PropositionRedigee] = []

    for bloc in brut.get("propositions") or []:
        if not isinstance(bloc, dict):
            rejetees.append(f"bloc de proposition mal forme: {bloc!r}")
            continue

        fiche_id = bloc.get("id")
        if fiche_id not in fiches_par_id:
            rejetees.append(f"fiche '{fiche_id}' citee mais jamais presentee au modele")
            continue
        fiche = fiches_par_id[fiche_id]
        calculs = calculs_par_id[fiche_id]

        affirmations_valides: list[Affirmation] = []
        for aff in bloc.get("affirmations") or []:
            if not isinstance(aff, dict):
                rejetees.append(f"{fiche_id}: affirmation mal formee {aff!r}")
                continue

            champ = str(aff.get("champ") or "")
            texte = str(aff.get("texte") or "").strip()
            if not texte:
                rejetees.append(f"{fiche_id}: affirmation sans texte (champ '{champ}')")
                continue

            if champ in CHAMPS_CALCULES:
                valeur_reelle = calculs[champ]
                if str(valeur_reelle) not in texte:
                    rejetees.append(
                        f"{fiche_id}.{champ}: '{texte}' ne mentionne pas la valeur reelle ({valeur_reelle})"
                    )
                    continue
            elif champ in CHAMPS_CITABLES:
                if not fiche.get(champ):
                    rejetees.append(f"{fiche_id}.{champ}: champ absent ou vide dans la fiche")
                    continue
            else:
                rejetees.append(f"{fiche_id}: champ '{champ}' non citable")
                continue

            affirmations_valides.append(Affirmation(champ=champ, texte=texte))

        if affirmations_valides:
            retenues.append(PropositionRedigee(fiche_id=fiche_id, affirmations=affirmations_valides))
        else:
            rejetees.append(f"{fiche_id}: aucune affirmation verifiable, proposition ecartee")

    return Redaction(intro=intro, propositions=retenues, rejetees=rejetees)


def _compter_affirmations_produites(brut: dict) -> int:
    total = 0
    for bloc in brut.get("propositions") or []:
        if isinstance(bloc, dict):
            total += len(bloc.get("affirmations") or [])
    return total


def assembler(redaction: Redaction) -> str:
    """La Redaction verifiee -> le texte a afficher a l'agent."""
    if not redaction.propositions:
        return redaction.intro or "Aucune des propositions du modele n'a pu etre confirmee."

    lignes = [redaction.intro] if redaction.intro else []
    for prop in redaction.propositions:
        phrase = " ".join(aff.texte for aff in prop.affirmations)
        lignes.append(f"- {phrase}")
    return "\n".join(lignes)


def rediger(
    demande: Demande,
    resultat: Resultat,
    *,
    hote: str = OLLAMA_HOTE_PAR_DEFAUT,
    modele: str = OLLAMA_MODELE_PAR_DEFAUT,
    delai_max_s: float = 60.0,
) -> tuple[str, Redaction | None]:
    """Le pipeline complet. Renvoie le texte a afficher et la Redaction
    detaillee - None quand il n'y avait rien a rediger : `Resultat` est vide,
    et le modele n'est alors jamais appele."""
    if not resultat:
        return resultat.diagnostic(), None

    propositions = classer(resultat.propositions, demande)[:3]
    brut_texte = appeler_ollama(demande, propositions, hote=hote, modele=modele, delai_max_s=delai_max_s)
    donnees = extraire_json(brut_texte)
    redaction = verifier(donnees, propositions)
    return assembler(redaction), redaction
