"""Interface web minimale : une page, deux points d'entree.

Reste volontairement hors de comptoir/ : le coeur du projet (filtres,
extraction, redaction) ne depend que de la bibliotheque standard, et cette
regle vaut la peine d'etre gardee intacte. FastAPI et uvicorn ne sont
necessaires qu'ici, pour exposer ce coeur dans un navigateur plutot qu'en
ligne de commande - `requirements-interface.txt` les liste a part de
`requirements.txt` pour que la distinction reste visible dans le depot.

La page garde la derniere demande comprise et la renvoie avec la suivante :
c'est ce qui permet a « meme chose mais pas plus de 3000 euros » d'avoir un
sens. La reprise des criteres est faite cote Python par `fusionner()`, pas
par le navigateur ni par le modele.

Lancer :
    pip install -r requirements.txt -r requirements-interface.txt
    python3 -m uvicorn interface.serveur:app --reload
Puis ouvrir http://127.0.0.1:8000 - Ollama doit tourner en local pour que
la recherche fonctionne (l'extraction texte -> demande en a besoin).
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from comptoir.catalogue import charger  # noqa: E402
from comptoir.classement import classer  # noqa: E402
from comptoir.demande import Demande  # noqa: E402
from comptoir.extraction import ErreurExtraction, extraire  # noqa: E402
from comptoir.filtres import filtrer  # noqa: E402
from comptoir.redaction import ErreurRedaction, rediger  # noqa: E402

app = FastAPI(title="Comptoir")
CATALOGUE = charger()
REQUETES_TEST = RACINE / "tests" / "requetes.jsonl"


class RequeteRecherche(BaseModel):
    texte: str
    rediger: bool = False
    precedente: dict | None = None


def _demande_precedente(donnees: dict | None) -> Demande | None:
    """La demande renvoyee par la page au tour precedent. Elle vient du
    navigateur : on ne lui fait pas confiance. Si elle n'est pas exactement
    de la forme attendue, on lit la nouvelle phrase seule plutot que de
    faire echouer la recherche."""
    if not isinstance(donnees, dict):
        return None
    try:
        return Demande.depuis_dict(donnees)
    except (TypeError, ValueError):
        return None


@app.get("/", response_class=HTMLResponse)
def page_accueil() -> str:
    return PAGE_HTML


@app.get("/api/exemples")
def exemples() -> list[dict]:
    """Les phrases du jeu de test, pour peupler le menu deroulant de la page -
    evite d'avoir a taper une demande a la main pour essayer l'outil."""
    if not REQUETES_TEST.exists():
        return []
    lignes = REQUETES_TEST.read_text(encoding="utf-8").splitlines()
    return [
        {"id": r["id"], "texte": r["texte"], "suite_de": r.get("suite_de")}
        for r in (json.loads(ligne) for ligne in lignes if ligne.strip())
    ]


@app.post("/api/chercher")
def chercher(requete: RequeteRecherche) -> JSONResponse:
    precedente = _demande_precedente(requete.precedente)

    try:
        demande = extraire(requete.texte, precedente=precedente)
    except ErreurExtraction as erreur:
        return JSONResponse({"erreur": str(erreur)})

    resultat = filtrer(CATALOGUE, demande)

    reponse: dict = {
        "erreur": None,
        "a_herite": precedente is not None,
        "demande": {
            "voyageurs": demande.voyageurs,
            "adultes": demande.adultes,
            "enfants_ages": demande.enfants_ages,
            "destinations": demande.destinations,
            "duree_nuits": demande.duree_nuits,
            "budget_total_max": demande.budget_total_max,
            "formules": demande.formules,
            "depart": demande.depart,
            "club_enfants_requis": demande.club_enfants_requis,
            "non_precise": demande.non_precise,
        },
        # Renvoyee telle quelle a la page, qui la joindra a la demande
        # suivante si le client enchaine par « meme chose mais... ».
        "demande_complete": asdict(demande),
        "diagnostic": resultat.diagnostic(),
        "propositions": [
            {
                "id": p.fiche["id"],
                "nom": p.fiche["nom"],
                "region": p.fiche["region"],
                "pays": p.fiche["pays"],
                "formule": p.fiche["formule"].replace("_", " "),
                "prix_total": p.prix_total,
                "nuits": p.nuits,
                "point_fort": p.fiche["points_forts"][0],
                "point_faible": p.fiche["points_faibles"][0],
            }
            for p in classer(resultat.propositions, demande)[:3]
        ],
        "reste": max(0, len(resultat.propositions) - 3),
        "redaction": None,
        "redaction_erreur": None,
    }

    if requete.rediger and resultat:
        try:
            texte_redige, redaction = rediger(demande, resultat)
            reponse["redaction"] = {
                "texte": texte_redige,
                "affirmations_rejetees": len(redaction.rejetees) if redaction else 0,
            }
        except ErreurRedaction as erreur:
            reponse["redaction_erreur"] = str(erreur)

    return JSONResponse(reponse)


PAGE_HTML = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Comptoir</title>
<style>
  :root {
    --encre: #17212e;
    --papier: #eef2f5;
    --surface: #ffffff;
    --trait: #d3dbe2;
    --attenue: #55636e;
    --accent: #1d5d73;
    --accent-pale: #e2edf1;
    --retenu: #2f6b4f;
    --refus: #9a4b2f;
    --refus-pale: #f7ece7;
    --serif: Georgia, "Times New Roman", serif;
    --sans: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif;
  }

  * { box-sizing: border-box; }

  body {
    margin: 0;
    background: var(--papier);
    color: var(--encre);
    font-family: var(--sans);
    font-size: 16px;
    line-height: 1.6;
  }

  .page {
    max-width: 54rem;
    margin: 0 auto;
    padding: 2.5rem 1.25rem 4rem;
    display: flex;
    flex-direction: column;
    gap: 1.75rem;
  }

  header { display: flex; flex-direction: column; gap: .3rem; }

  h1 {
    font-family: var(--serif);
    font-size: 2.1rem;
    font-weight: 600;
    letter-spacing: -.01em;
    margin: 0;
  }

  .sous-titre { color: var(--attenue); font-size: 1rem; margin: 0; }

  /* ---------- le formulaire ---------- */

  form {
    background: var(--surface);
    border: 1px solid var(--trait);
    border-radius: 4px;
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: .9rem;
  }

  label { font-size: .9rem; font-weight: 600; }

  textarea {
    width: 100%;
    min-height: 5.5rem;
    resize: vertical;
    padding: .7rem .8rem;
    border: 1px solid var(--trait);
    border-radius: 3px;
    font-family: inherit;
    font-size: 1rem;
    line-height: 1.5;
    color: inherit;
    background: var(--surface);
  }

  textarea:focus, select:focus, button:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }

  .rangee {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: .8rem 1.1rem;
  }

  select {
    flex: 1 1 18rem;
    padding: .5rem .6rem;
    border: 1px solid var(--trait);
    border-radius: 3px;
    font-family: inherit;
    font-size: .92rem;
    background: var(--surface);
    color: inherit;
  }

  .bascule { display: flex; align-items: center; gap: .45rem; font-size: .92rem; font-weight: 400; }

  button {
    font-family: inherit;
    font-size: .95rem;
    font-weight: 600;
    padding: .6rem 1.3rem;
    border: 1px solid var(--accent);
    border-radius: 3px;
    background: var(--accent);
    color: #fff;
    cursor: pointer;
  }

  button:hover { background: #17505f; }
  button[disabled] { opacity: .55; cursor: default; }

  button.discret {
    background: transparent;
    color: var(--accent);
    border-color: var(--trait);
    font-weight: 500;
    padding: .35rem .8rem;
    font-size: .85rem;
  }

  button.discret:hover { background: var(--accent-pale); }

  /* ---------- le fil de la demande ---------- */

  .contexte {
    background: var(--accent-pale);
    border: 1px solid #cbdde4;
    border-radius: 4px;
    padding: .8rem 1rem;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: .6rem 1rem;
    font-size: .92rem;
  }

  .contexte .criteres { display: flex; flex-wrap: wrap; gap: .3rem .75rem; }
  .contexte .rappel-suite { flex-basis: 100%; font-size: .82rem; color: var(--attenue); }
  .contexte .critere { white-space: nowrap; }
  .contexte .critere b { font-weight: 600; }
  .marque-suite {
    font-size: .78rem;
    text-transform: uppercase;
    letter-spacing: .07em;
    color: var(--accent);
    font-weight: 600;
  }

  /* ---------- etats ---------- */

  .attente, .panne {
    background: var(--surface);
    border: 1px solid var(--trait);
    border-left: 3px solid var(--accent);
    border-radius: 3px;
    padding: .9rem 1.1rem;
    font-size: .95rem;
    color: var(--attenue);
  }

  .panne { border-left-color: var(--refus); color: var(--encre); }

  /* ---------- resultats ---------- */

  .resultats { display: flex; flex-direction: column; gap: .9rem; }

  .titre-bloc {
    font-family: var(--serif);
    font-size: 1.15rem;
    font-weight: 600;
    margin: 0;
  }

  .sejour {
    background: var(--surface);
    border: 1px solid var(--trait);
    border-radius: 4px;
    padding: 1rem 1.15rem;
    display: grid;
    grid-template-columns: 1fr auto;
    gap: .35rem 1.2rem;
    align-items: baseline;
  }

  .sejour .nom { font-family: var(--serif); font-size: 1.15rem; font-weight: 600; }
  .sejour .prix {
    font-size: 1.15rem;
    font-weight: 600;
    color: var(--retenu);
    font-variant-numeric: tabular-nums;
    text-align: right;
    white-space: nowrap;
  }
  .sejour .lieu { color: var(--attenue); font-size: .92rem; }
  .sejour .par-personne { color: var(--attenue); font-size: .82rem; text-align: right; white-space: nowrap; }
  .sejour .details { grid-column: 1 / -1; display: flex; flex-direction: column; gap: .2rem; margin-top: .45rem; font-size: .92rem; }
  .sejour .fort::before { content: "+ "; color: var(--retenu); font-weight: 700; }
  .sejour .faible::before { content: "\\2212\\00a0"; color: var(--refus); font-weight: 700; }
  .sejour .faible { color: var(--attenue); }

  .refus {
    background: var(--refus-pale);
    border: 1px solid #e8d5cb;
    border-left: 3px solid var(--refus);
    border-radius: 4px;
    padding: 1rem 1.15rem;
    display: flex;
    flex-direction: column;
    gap: .35rem;
  }

  .refus .titre { font-family: var(--serif); font-size: 1.1rem; font-weight: 600; }
  .refus .detail { font-size: .95rem; }

  .redaction {
    background: var(--surface);
    border: 1px solid var(--trait);
    border-radius: 4px;
    padding: 1rem 1.15rem;
    display: flex;
    flex-direction: column;
    gap: .5rem;
  }

  .redaction .corps { white-space: pre-wrap; font-size: .97rem; }
  .redaction .note { font-size: .82rem; color: var(--attenue); border-top: 1px solid var(--trait); padding-top: .5rem; }

  .reste, .manquant { font-size: .88rem; color: var(--attenue); }

  [hidden] { display: none !important; }

  @media (max-width: 32rem) {
    .sejour { grid-template-columns: 1fr; }
    .sejour .prix, .sejour .par-personne { text-align: left; }
  }
</style>
</head>
<body>
<div class="page">

  <header>
    <h1>Comptoir</h1>
    <p class="sous-titre">Dites la demande du client comme il la formule. Rien ne sera propose qui n'existe pas au catalogue.</p>
  </header>

  <div class="contexte" id="contexte" hidden>
    <div class="criteres" id="criteres"></div>
    <div class="rappel-suite" id="rappel-suite" hidden>Pour enchainer sur cette demande (« meme chose mais... »), cochez « Suite de la demande precedente ».</div>
    <button type="button" class="discret" id="reinitialiser">Nouvelle recherche</button>
  </div>

  <form id="formulaire">
    <label for="texte">La demande du client</label>
    <textarea id="texte" placeholder="On part a deux, une semaine en Crete en tout compris, en juillet, au depart de Toulouse, et on ne veut pas depasser 2000 euros a deux."></textarea>

    <div class="rangee">
      <select id="exemples"><option value="">Ou choisir un exemple...</option></select>
      <label class="bascule" id="bascule-suite" hidden><input type="checkbox" id="suite"> Suite de la demande precedente</label>
      <label class="bascule"><input type="checkbox" id="rediger"> Rediger la reponse au client</label>
      <button type="submit" id="envoyer">Chercher</button>
    </div>
  </form>

  <div class="attente" id="attente" hidden></div>
  <div class="panne" id="panne" hidden></div>
  <div class="resultats" id="resultats"></div>

</div>

<script>
const $ = (id) => document.getElementById(id);
let demandePrecedente = null;

const EURO = new Intl.NumberFormat("fr-FR");

async function chargerExemples() {
  try {
    const reponse = await fetch("/api/exemples");
    const exemples = await reponse.json();
    for (const exemple of exemples) {
      const option = document.createElement("option");
      option.value = exemple.texte;
      const suite = exemple.suite_de ? " (suite)" : "";
      option.dataset.suite = exemple.suite_de ? "1" : "";
      option.textContent = exemple.id + suite + " - " + exemple.texte.slice(0, 70) + (exemple.texte.length > 70 ? "..." : "");
      $("exemples").appendChild(option);
    }
  } catch (erreur) {
    /* le menu d'exemples est un confort : son absence n'empeche pas de taper une demande */
  }
}

$("exemples").addEventListener("change", (evenement) => {
  const choisie = evenement.target.selectedOptions[0];
  if (evenement.target.value) {
    $("texte").value = evenement.target.value;
    // un exemple marque comme demande de suite n'a de sens qu'apres une autre :
    // on coche pour l'utilisateur plutot que de le laisser deviner
    $("suite").checked = Boolean(choisie && choisie.dataset.suite && demandePrecedente);
    evenement.target.value = "";
    $("texte").focus();
  }
});

$("reinitialiser").addEventListener("click", () => {
  demandePrecedente = null;
  $("suite").checked = false;
  $("bascule-suite").hidden = true;
  $("contexte").hidden = true;
  $("resultats").innerHTML = "";
  $("panne").hidden = true;
  $("texte").value = "";
  $("texte").focus();
});

function afficherContexte(demande, aHerite) {
  const morceaux = [];
  const voyageurs = demande.voyageurs + (demande.voyageurs > 1 ? " voyageurs" : " voyageur");
  const enfants = demande.enfants_ages.length ? " (dont " + demande.enfants_ages.length + " enfant" + (demande.enfants_ages.length > 1 ? "s" : "") + ")" : "";
  morceaux.push(voyageurs + enfants);
  if (demande.destinations.length) morceaux.push(demande.destinations.join(", "));
  if (demande.duree_nuits) morceaux.push(demande.duree_nuits + " nuits");
  if (demande.formules.length) morceaux.push(demande.formules.join(", ").replace(/_/g, " "));
  if (demande.budget_total_max) morceaux.push("max " + EURO.format(demande.budget_total_max) + " EUR");
  if (demande.depart) morceaux.push("depart " + demande.depart);
  if (demande.club_enfants_requis) morceaux.push("club enfants");

  const criteres = $("criteres");
  criteres.innerHTML = "";
  if (aHerite) {
    const marque = document.createElement("span");
    marque.className = "marque-suite";
    marque.textContent = "Suite de la demande precedente";
    criteres.appendChild(marque);
  }
  for (const morceau of morceaux) {
    const bloc = document.createElement("span");
    bloc.className = "critere";
    bloc.textContent = morceau;
    criteres.appendChild(bloc);
  }
  $("rappel-suite").hidden = aHerite;
  $("contexte").hidden = false;
}

function carteSejour(sejour, voyageurs) {
  const carte = document.createElement("article");
  carte.className = "sejour";

  const nom = document.createElement("div");
  nom.className = "nom";
  nom.textContent = sejour.nom;

  const prix = document.createElement("div");
  prix.className = "prix";
  prix.textContent = EURO.format(sejour.prix_total) + " EUR";

  const lieu = document.createElement("div");
  lieu.className = "lieu";
  lieu.textContent = sejour.region + ", " + sejour.pays + " - " + sejour.nuits + " nuits, " + sejour.formule;

  const parPersonne = document.createElement("div");
  parPersonne.className = "par-personne";
  parPersonne.textContent = voyageurs > 1 ? "soit " + EURO.format(Math.round(sejour.prix_total / voyageurs)) + " EUR par personne" : "au total";

  const details = document.createElement("div");
  details.className = "details";
  const fort = document.createElement("div");
  fort.className = "fort";
  fort.textContent = sejour.point_fort;
  const faible = document.createElement("div");
  faible.className = "faible";
  faible.textContent = sejour.point_faible;
  details.append(fort, faible);

  carte.append(nom, prix, lieu, parPersonne, details);
  return carte;
}

function afficherResultats(donnees) {
  const zone = $("resultats");
  zone.innerHTML = "";

  if (donnees.propositions.length === 0) {
    const bloc = document.createElement("div");
    bloc.className = "refus";
    const titre = document.createElement("div");
    titre.className = "titre";
    titre.textContent = "Rien ne correspond a cette demande";
    const detail = document.createElement("div");
    detail.className = "detail";
    detail.textContent = donnees.diagnostic;
    bloc.append(titre, detail);
    zone.appendChild(bloc);
    return;
  }

  const titre = document.createElement("h2");
  titre.className = "titre-bloc";
  titre.textContent = donnees.propositions.length > 1 ? "Ce que je peux proposer" : "Une seule offre correspond";
  zone.appendChild(titre);

  for (const sejour of donnees.propositions) {
    zone.appendChild(carteSejour(sejour, donnees.demande.voyageurs));
  }

  if (donnees.reste > 0) {
    const reste = document.createElement("div");
    reste.className = "reste";
    reste.textContent = donnees.reste + " autre(s) sejour(s) correspondent aussi, classes apres ceux-ci.";
    zone.appendChild(reste);
  }

  if (donnees.demande.non_precise.length) {
    const manquant = document.createElement("div");
    manquant.className = "manquant";
    manquant.textContent = "A demander au client : " + donnees.demande.non_precise.join(", ") + ".";
    zone.appendChild(manquant);
  }

  if (donnees.redaction) {
    const bloc = document.createElement("div");
    bloc.className = "redaction";
    const titreR = document.createElement("h2");
    titreR.className = "titre-bloc";
    titreR.textContent = "La reponse au client";
    const corps = document.createElement("div");
    corps.className = "corps";
    corps.textContent = donnees.redaction.texte;
    bloc.append(titreR, corps);

    const note = document.createElement("div");
    note.className = "note";
    note.textContent = donnees.redaction.affirmations_rejetees > 0
      ? donnees.redaction.affirmations_rejetees + " affirmation(s) ecartee(s) a la verification : elles ne correspondaient a aucune donnee des fiches, le client ne les voit pas."
      : "Toutes les affirmations ont ete verifiees contre les fiches.";
    bloc.appendChild(note);
    zone.appendChild(bloc);
  } else if (donnees.redaction_erreur) {
    const bloc = document.createElement("div");
    bloc.className = "panne";
    bloc.textContent = "La redaction n'a pas abouti : " + donnees.redaction_erreur + " (les sejours ci-dessus, eux, sont bien reels).";
    zone.appendChild(bloc);
  }
}

$("formulaire").addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  const texte = $("texte").value.trim();
  if (!texte) return;

  const rediger = $("rediger").checked;
  $("envoyer").disabled = true;
  $("panne").hidden = true;
  $("resultats").innerHTML = "";
  $("attente").hidden = false;
  $("attente").textContent = rediger
    ? "Je lis la demande, puis je redige la reponse. Deux appels au modele local : comptez une quinzaine de secondes."
    : "Je lis la demande et je cherche dans le catalogue...";

  try {
    const reponse = await fetch("/api/chercher", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      // sans la case cochee, chaque demande est lue seule : deux recherches
      // sans rapport ne doivent pas cumuler leurs criteres
      body: JSON.stringify({texte: texte, rediger: rediger, precedente: $("suite").checked ? demandePrecedente : null}),
    });
    const donnees = await reponse.json();

    if (donnees.erreur) {
      $("panne").hidden = false;
      $("panne").textContent = donnees.erreur;
      return;
    }

    demandePrecedente = donnees.demande_complete;
    $("bascule-suite").hidden = false;
    $("suite").checked = false;
    afficherContexte(donnees.demande, donnees.a_herite);
    afficherResultats(donnees);
  } catch (erreur) {
    $("panne").hidden = false;
    $("panne").textContent = "Le serveur n'a pas repondu : " + erreur;
  } finally {
    $("attente").hidden = true;
    $("envoyer").disabled = false;
  }
});

chargerExemples();
</script>
</body>
</html>"""
