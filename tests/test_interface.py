# -*- coding: utf-8 -*-
"""Interface web : ce qui peut etre teste sans Ollama.

/api/chercher appelle extraire() puis rediger(), qui ont chacun besoin d'un
modele reellement lance - ce fichier ne teste donc que ce qui ne depend
d'aucun reseau : que le serveur demarre, que la page se rend, et que
/api/exemples restitue bien le contenu de tests/requetes.jsonl.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

try:
    from fastapi.testclient import TestClient
except ImportError:
    import pytest
    pytest.skip(
        "fastapi/httpx non installes (dependances de l'interface, voir "
        "requirements-interface.txt) - pas d'echec de la suite principale pour autant",
        allow_module_level=True,
    )

from interface.serveur import app  # noqa: E402

client = TestClient(app)


def test_page_accueil_se_rend():
    rep = client.get("/")
    assert rep.status_code == 200
    assert "Comptoir" in rep.text
    assert "<textarea" in rep.text


def test_exemples_reprend_le_jeu_de_test():
    rep = client.get("/api/exemples")
    assert rep.status_code == 200
    exemples = rep.json()
    assert len(exemples) == 20
    assert all("id" in e and "texte" in e for e in exemples)
    assert exemples[0]["id"] == "q01"


def test_chercher_sans_ollama_renvoie_une_erreur_propre_pas_un_500():
    rep = client.post("/api/chercher", json={"texte": "peu importe", "rediger": False})
    assert rep.status_code == 200
    donnees = rep.json()
    assert donnees["erreur"] is not None
    assert "Ollama" in donnees["erreur"]
