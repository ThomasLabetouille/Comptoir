"""Interface web minimale : une page, deux points d'entree.

Reste volontairement hors de comptoir/ : le coeur du projet (filtres,
extraction, redaction) ne depend que de la bibliotheque standard, et cette
regle vaut la peine d'etre gardee intacte. FastAPI et uvicorn ne sont
necessaires qu'ici, pour exposer ce coeur dans un navigateur plutot qu'en
ligne de commande - `requirements-interface.txt` les liste a part de
`requirements.txt` pour que la distinction reste visible dans le depot.

Lancer :
    pip install -r requirements.txt -r requirements-interface.txt
    python3 -m uvicorn interface.serveur:app --reload
Puis ouvrir http://127.0.0.1:8000 - Ollama doit tourner en local pour que
la recherche fonctionne (l'extraction texte -> demande en a besoin).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from comptoir.catalogue import charger  # noqa: E402
from comptoir.classement import classer  # noqa: E402
from comptoir.extraction import ErreurExtraction, extraire  # noqa: E402
from comptoir.filtres import filtrer  # noqa: E402
from comptoir.redaction import ErreurRedaction, rediger  # noqa: E402

app = FastAPI(title="Comptoir")
CATALOGUE = charger()
REQUETES_TEST = RACINE / "tests" / "requetes.jsonl"


class RequeteRecherche(BaseModel):
    texte: str
    rediger: bool = False


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
        {"id": r["id"], "texte": r["texte"]}
        for r in (json.loads(ligne) for ligne in lignes if ligne.strip())
    ]


@app.post("/api/chercher")
def chercher(requete: RequeteRecherche) -> JSONResponse:
    try:
        demande = extraire(requete.texte)
    except ErreurExtraction as erreur:
        return JSONResponse({"erreur": str(erreur)})

    resultat = filtrer(CATALOGUE, demande)

    reponse: dict = {
        "erreur": None,
        "demande": {
            "voyageurs": demande.voyageurs,
            "destinations": demande.destinations,
            "duree_nuits": demande.duree_nuits,
            "budget_total_max": demande.budget_total_max,
            "formules": demande.formules,
            "depart": demande.depart,
            "non_precise": demande.non_precise,
        },
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
    --encre: #1c2733;
    --encre-att: #5a6b7a;
    --fond: #f7f8f9;
    --surface: #ffffff;
    --trait: #dde2e7;
    --accent: #175e8c;
    --accent-fond: #e7f0f6;
    --alerte: #9c3b2e;
    --alerte-fond: #f7ece9;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    background: var(--fond);
    color: var(--encre);
    line-height: 1.5;
  }
  .page { max-width: 760px; margin: 0 auto; padding: 40px 20px 80px; }
  header { margin-bottom: 28px; }
  h1 { font-size: 1.6rem; margin: 0 0 6px; }
  .sous-titre { color: var(--encre-att); font-size: 0.95rem; margin: 0; }
  .panneau {
    background: var(--surface);
    border: 1px solid var(--trait);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
  }
  label { display: block; font-size: 0.85rem; color: var(--encre-att); margin-bottom: 6px; }
  textarea {
    width: 100%;
    min-height: 84px;
    font-family: inherit;
    font-size: 0.98rem;
    padding: 10px 12px;
    border: 1px solid var(--trait);
    border-radius: 6px;
    resize: vertical;
  }
  select {
    width: 100%;
    padding: 8px 10px;
    border: 1px solid var(--trait);
    border-radius: 6px;
    font-family: inherit;
    font-size: 0.9rem;
    margin-bottom: 14px;
    background: var(--surface);
  }
  .ligne-options {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 14px;
    gap: 12px;
    flex-wrap: wrap;
  }
  .case-rediger { display: flex; align-items: center; gap: 8px; font-size: 0.9rem; color: var(--encre-att); }
  button {
    background: var(--accent);
    color: #fff;
    border: none;
    padding: 10px 20px;
    border-radius: 6px;
    font-size: 0.95rem;
    cursor: pointer;
  }
  button:disabled { opacity: 0.6; cursor: default; }
  .resume {
    font-size: 0.88rem;
    color: var(--encre-att);
    background: var(--accent-fond);
    border-radius: 6px;
    padding: 10px 12px;
    margin-bottom: 16px;
  }
  .non-precise { color: var(--alerte); }
  .proposition {
    border: 1px solid var(--trait);
    border-radius: 6px;
    padding: 14px 16px;
    margin-bottom: 10px;
  }
  .proposition h3 { margin: 0 0 4px; font-size: 1.02rem; }
  .proposition .prix { color: var(--accent); font-weight: 600; }
  .proposition .plus { color: #2c6a50; font-size: 0.88rem; margin-top: 6px; }
  .proposition .moins { color: var(--alerte); font-size: 0.88rem; }
  .proposition .id { color: var(--encre-att); font-size: 0.76rem; font-family: ui-monospace, monospace; margin-top: 6px; }
  .diagnostic {
    background: var(--alerte-fond);
    color: var(--alerte);
    border-radius: 6px;
    padding: 12px 14px;
    font-size: 0.92rem;
  }
  .redaction {
    background: var(--accent-fond);
    border-radius: 6px;
    padding: 14px 16px;
    margin-top: 16px;
    white-space: pre-line;
    font-size: 0.95rem;
  }
  .redaction .note { display: block; margin-top: 10px; font-size: 0.78rem; color: var(--encre-att); }
  .erreur { color: var(--alerte); font-size: 0.9rem; margin-top: 10px; }
  .etat { font-size: 0.85rem; color: var(--encre-att); margin-top: 10px; }
  footer { margin-top: 40px; font-size: 0.78rem; color: var(--encre-att); }
</style>
</head>
<body>
<div class="page">
  <header>
    <h1>Comptoir</h1>
    <p class="sous-titre">La demande d'un client, telle qu'elle a ete dite, et les sejours qui correspondent vraiment.</p>
  </header>

  <div class="panneau">
    <label for="exemples">Charger un exemple du jeu de test</label>
    <select id="exemples"><option value="">-- choisir --</option></select>

    <label for="texte">Ce que dit le client</label>
    <textarea id="texte" placeholder="on est quatre, deux enfants de 8 et 14 ans, Crete ou Sicile, deuxieme quinzaine de juillet, tout compris, 3500 euros, depart Toulouse"></textarea>

    <div class="ligne-options">
      <label class="case-rediger"><input type="checkbox" id="rediger"> rediger une reponse en langage naturel (verifiee), plus lent</label>
      <button id="bouton" onclick="chercher()">Chercher</button>
    </div>
    <div class="etat" id="etat"></div>
  </div>

  <div id="resultats"></div>

  <footer>Catalogue de demonstration, entierement fictif. Extraction et redaction via un modele local (Ollama) - aucune donnee client ne quitte cette machine.</footer>
</div>

<script>
async function chargerExemples() {
  const rep = await fetch('/api/exemples');
  const exemples = await rep.json();
  const select = document.getElementById('exemples');
  for (const ex of exemples) {
    const option = document.createElement('option');
    option.value = ex.texte;
    option.textContent = `[${ex.id}] ${ex.texte.slice(0, 70)}${ex.texte.length > 70 ? '...' : ''}`;
    select.appendChild(option);
  }
  select.addEventListener('change', () => {
    if (select.value) document.getElementById('texte').value = select.value;
  });
}

function echapper(texte) {
  const div = document.createElement('div');
  div.textContent = texte;
  return div.innerHTML;
}

async function chercher() {
  const texte = document.getElementById('texte').value.trim();
  const rediger = document.getElementById('rediger').checked;
  const bouton = document.getElementById('bouton');
  const etat = document.getElementById('etat');
  const resultats = document.getElementById('resultats');

  if (!texte) { etat.textContent = 'Ecris ou choisis une demande d\\'abord.'; return; }

  bouton.disabled = true;
  etat.textContent = rediger ? 'Extraction puis redaction en cours (le modele local peut prendre quelques secondes)...' : 'Extraction en cours...';
  resultats.innerHTML = '';

  try {
    const rep = await fetch('/api/chercher', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({texte, rediger}),
    });
    const donnees = await rep.json();
    etat.textContent = '';

    if (donnees.erreur) {
      resultats.innerHTML = `<div class="erreur">${echapper(donnees.erreur)}</div>`;
      return;
    }

    let html = '';
    const d = donnees.demande;
    const morceaux = [`${d.voyageurs} voyageur(s)`];
    if (d.destinations.length) morceaux.push(d.destinations.join(' / '));
    if (d.duree_nuits) morceaux.push(`${d.duree_nuits} nuits`);
    if (d.formules.length) morceaux.push(d.formules.join(' ou ').replace(/_/g, ' '));
    if (d.depart) morceaux.push(`depart ${d.depart}`);
    if (d.budget_total_max) morceaux.push(`max ${d.budget_total_max} EUR`);
    html += `<div class="resume">${echapper(morceaux.join(' | '))}`;
    if (d.non_precise.length) {
      html += `<br><span class="non-precise">Non precise ou ecarte : ${echapper(d.non_precise.join(', '))}</span>`;
    }
    html += '</div>';

    if (donnees.propositions.length === 0) {
      html += `<div class="diagnostic">${echapper(donnees.diagnostic)}</div>`;
    } else {
      for (const p of donnees.propositions) {
        html += `<div class="proposition">
          <h3>${echapper(p.nom)} - ${echapper(p.region)}, ${echapper(p.pays)}</h3>
          <div>${p.nuits} nuits, ${echapper(p.formule)}, <span class="prix">${p.prix_total} EUR au total</span></div>
          <div class="plus">+ ${echapper(p.point_fort)}</div>
          <div class="moins">- ${echapper(p.point_faible)}</div>
          <div class="id">${echapper(p.id)}</div>
        </div>`;
      }
      if (donnees.reste > 0) {
        html += `<div class="etat">(${donnees.reste} autre(s) sejour(s) correspondent aussi)</div>`;
      }
    }

    if (donnees.redaction) {
      html += `<div class="redaction">${echapper(donnees.redaction.texte)}`;
      if (donnees.redaction.affirmations_rejetees > 0) {
        html += `<span class="note">${donnees.redaction.affirmations_rejetees} affirmation(s) du modele rejetee(s) a la verification</span>`;
      }
      html += '</div>';
    } else if (donnees.redaction_erreur) {
      html += `<div class="erreur">Redaction impossible : ${echapper(donnees.redaction_erreur)}</div>`;
    }

    resultats.innerHTML = html;
  } catch (err) {
    etat.textContent = '';
    resultats.innerHTML = `<div class="erreur">Erreur de communication avec le serveur : ${echapper(String(err))}</div>`;
  } finally {
    bouton.disabled = false;
  }
}

chargerExemples();
</script>
</body>
</html>"""
