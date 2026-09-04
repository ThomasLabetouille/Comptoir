"""Le catalogue en SQLite, et la partie du filtrage qui a du sens en SQL.

Ce module ne remplace pas comptoir/filtres.py : il lui sert de deuxieme
implementation, verifiee CONTRE la premiere plutot qu'a sa place (voir
tests/test_base_sql.py). Les criteres qui exigent un calcul - la periode
(intersection de plages de dates) et le prix (remise enfant, choix de la
duree la moins chere) - restent dans comptoir/filtres.py et sont reutilises
tels quels apres la requete SQL : ce n'est pas de la paresse, c'est que ces
regles-la n'ont pas leur place dans une clause WHERE sans devenir illisibles.

La requete SQL couvre exactement les criteres "d'appartenance a un ensemble"
de comptoir.filtres.CRITERES, moins periode et budget :
destination, depart, duree (existence), formule, capacite, enfants, club_enfants.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path

from .demande import Demande

RACINE = Path(__file__).resolve().parent.parent
CHEMIN_PAR_DEFAUT = RACINE / "data" / "comptoir.db"

SCHEMA = """
CREATE TABLE fiches (
    id                    TEXT PRIMARY KEY,
    nom                   TEXT NOT NULL,
    gamme                 TEXT NOT NULL,
    pays                  TEXT NOT NULL,
    region                TEXT NOT NULL,
    formule               TEXT NOT NULL,
    capacite_max_chambre  INTEGER NOT NULL,
    enfants_acceptes      INTEGER NOT NULL CHECK (enfants_acceptes IN (0, 1)),
    club_age_min          INTEGER,
    club_age_max          INTEGER,
    note_clients          REAL,
    distance_plage_m      INTEGER
);

-- pays, region ET chaque alias d'une fiche, a plat : une seule table a
-- interroger pour "cette fiche correspond-elle a ce que le client a dit".
CREATE TABLE lieux (
    fiche_id  TEXT NOT NULL REFERENCES fiches(id),
    valeur    TEXT NOT NULL
);

CREATE TABLE aeroports_depart (
    fiche_id  TEXT NOT NULL REFERENCES fiches(id),
    code      TEXT NOT NULL
);

CREATE TABLE durees_prix (
    fiche_id  TEXT NOT NULL REFERENCES fiches(id),
    nuits     INTEGER NOT NULL,
    prix_pp   INTEGER NOT NULL,
    PRIMARY KEY (fiche_id, nuits)
);

CREATE TABLE periodes_ouverture (
    fiche_id  TEXT NOT NULL REFERENCES fiches(id),
    debut     TEXT NOT NULL,
    fin       TEXT NOT NULL
);

CREATE INDEX idx_lieux_fiche      ON lieux (fiche_id);
CREATE INDEX idx_lieux_valeur     ON lieux (valeur);
CREATE INDEX idx_aeroports_fiche  ON aeroports_depart (fiche_id);
CREATE INDEX idx_aeroports_code   ON aeroports_depart (code);
CREATE INDEX idx_durees_fiche     ON durees_prix (fiche_id);
CREATE INDEX idx_durees_nuits     ON durees_prix (nuits);
CREATE INDEX idx_periodes_fiche   ON periodes_ouverture (fiche_id);
CREATE INDEX idx_fiches_pays      ON fiches (pays);
CREATE INDEX idx_fiches_region    ON fiches (region);
"""


def _peupler(conn: sqlite3.Connection, fiches: list[dict]) -> None:
    conn.executescript(SCHEMA)
    for fiche in fiches:
        club = fiche.get("club_enfants")
        conn.execute(
            """INSERT INTO fiches
               (id, nom, gamme, pays, region, formule, capacite_max_chambre,
                enfants_acceptes, club_age_min, club_age_max, note_clients,
                distance_plage_m)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fiche["id"], fiche["nom"], fiche["gamme"], fiche["pays"], fiche["region"],
                fiche["formule"], fiche["capacite_max_chambre"],
                int(fiche["enfants_acceptes"]),
                club["age_min"] if club else None,
                club["age_max"] if club else None,
                fiche.get("note_clients"), fiche.get("distance_plage_m"),
            ),
        )

        lieux = {fiche["pays"], fiche["region"], *fiche.get("alias", [])}
        conn.executemany(
            "INSERT INTO lieux (fiche_id, valeur) VALUES (?, ?)",
            [(fiche["id"], valeur) for valeur in lieux],
        )

        conn.executemany(
            "INSERT INTO aeroports_depart (fiche_id, code) VALUES (?, ?)",
            [(fiche["id"], code) for code in fiche["aeroports_depart"]],
        )

        conn.executemany(
            "INSERT INTO durees_prix (fiche_id, nuits, prix_pp) VALUES (?, ?, ?)",
            [
                (fiche["id"], nuits, fiche["prix_pp_par_duree"][str(nuits)])
                for nuits in fiche["durees_nuits"]
            ],
        )

        conn.executemany(
            "INSERT INTO periodes_ouverture (fiche_id, debut, fin) VALUES (?, ?, ?)",
            [(fiche["id"], p["debut"], p["fin"]) for p in fiche["periodes_ouverture"]],
        )
    conn.commit()


def construire(fiches: list[dict], chemin: Path | str | None = None) -> None:
    """(Re)cree la base a partir des fiches deja validees (voir schema.py).

    Construite entierement dans un fichier temporaire local, puis copiee
    d'un bloc vers sa destination finale : jamais de connexion SQLite en
    ecriture ouverte directement sur `chemin`. Ce n'est pas de la prudence
    excessive - sur un chemin monte (le pont Cowork utilise pour developper
    ce projet, potentiellement un lecteur reseau plus tard), ouvrir une base
    SQLite en ECRITURE echoue avec une erreur d'E/S disque, alors qu'une
    simple copie d'un fichier deja construit passe sans probleme. La lecture
    seule, elle, n'a jamais pose de souci - `connecter()` ci-dessous reste
    une connexion normale.
    """
    chemin = Path(chemin) if chemin else CHEMIN_PAR_DEFAUT
    chemin.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as dossier_temp:
        provisoire = Path(dossier_temp) / "construction.db"
        conn = sqlite3.connect(provisoire)
        try:
            _peupler(conn, fiches)
        finally:
            conn.close()

        try:
            chemin.write_bytes(provisoire.read_bytes())
        except PermissionError:
            # Repli si l'ecriture directe echoue aussi (mount tres restrictif).
            shutil.copyfile(provisoire, chemin)


def connecter(chemin: Path | str | None = None) -> sqlite3.Connection:
    chemin = Path(chemin) if chemin else CHEMIN_PAR_DEFAUT
    if not chemin.exists():
        raise FileNotFoundError(
            f"{chemin} n'existe pas - lancer d'abord outils/construire_base_sql.py"
        )
    return sqlite3.connect(chemin)


def candidats(conn: sqlite3.Connection, demande: Demande) -> set[str]:
    """Fiches qui passent les criteres structurels, en une requete SQL.

    Ne juge PAS la periode ni le budget : voir le docstring du module.
    """
    clauses: list[str] = []
    params: list = []

    if demande.destinations:
        sous_clauses = []
        for cible in demande.destinations:
            sous_clauses.append("(l.valeur LIKE '%' || ? || '%' OR ? LIKE '%' || l.valeur || '%')")
            params.extend([cible, cible])
        clauses.append(
            "EXISTS (SELECT 1 FROM lieux l WHERE l.fiche_id = f.id AND (" +
            " OR ".join(sous_clauses) + "))"
        )

    if demande.depart:
        clauses.append(
            "EXISTS (SELECT 1 FROM aeroports_depart a WHERE a.fiche_id = f.id AND a.code = ?)"
        )
        params.append(demande.depart)

    if demande.duree_nuits is not None:
        clauses.append(
            "EXISTS (SELECT 1 FROM durees_prix d WHERE d.fiche_id = f.id AND d.nuits = ?)"
        )
        params.append(demande.duree_nuits)

    if demande.formules:
        marques = ", ".join("?" for _ in demande.formules)
        clauses.append(f"f.formule IN ({marques})")
        params.extend(demande.formules)

    clauses.append("f.capacite_max_chambre >= ?")
    params.append(demande.voyageurs)

    if demande.enfants_ages:
        clauses.append("f.enfants_acceptes = 1")

    if demande.club_enfants_requis:
        clauses.append("f.club_age_min IS NOT NULL")
        if demande.enfants_ages:
            sous_clauses = ["(f.club_age_min <= ? AND f.club_age_max >= ?)" for _ in demande.enfants_ages]
            clauses.append("(" + " OR ".join(sous_clauses) + ")")
            for age in demande.enfants_ages:
                params.extend([age, age])

    requete = "SELECT f.id FROM fiches f"
    if clauses:
        requete += " WHERE " + " AND ".join(clauses)

    lignes = conn.execute(requete, params).fetchall()
    return {ligne[0] for ligne in lignes}
