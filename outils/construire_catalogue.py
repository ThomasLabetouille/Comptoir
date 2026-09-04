# -*- coding: utf-8 -*-
"""Genere data/catalogue.json a partir d'une saisie compacte.

Le catalogue est entierement FICTIF : etablissements inventes, prix inventes.
Il reproduit la STRUCTURE d'un catalogue de voyagiste (gammes, formules,
periodes d'ouverture, capacites, clubs enfants), pas son contenu.
Voir SOURCES.md.

Ajouter une fiche = ajouter une ligne dans FICHES, puis relancer ce script.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from comptoir.schema import valider_catalogue  # noqa: E402


def f(ident, nom, gamme, pays, region, aero, durees, prix, formule, cap, ouv,
      amb, equip, forts, faibles, club=None, note=None, plage=None, enfants=True, alias=None):
    fiche = {
        "id": ident,
        "nom": nom,
        "gamme": gamme,
        "pays": pays,
        "region": region,
        "aeroports_depart": aero.split(),
        "durees_nuits": list(durees),
        "prix_pp_par_duree": {str(n): p for n, p in zip(durees, prix)},
        "formule": formule,
        "capacite_max_chambre": cap,
        "enfants_acceptes": enfants,
        "periodes_ouverture": [{"debut": d, "fin": ff} for d, ff in ouv],
        "ambiance": amb.split(),
        "equipements": equip.split(", "),
        "points_forts": forts,
        "points_faibles": faibles,
    }
    if alias:
        fiche["alias"] = alias
    if club:
        fiche["club_enfants"] = {"age_min": club[0], "age_max": club[1]}
    if note is not None:
        fiche["note_clients"] = note
    if plage is not None:
        fiche["distance_plage_m"] = plage
    return fiche


ETE = [("2027-04-15", "2027-10-25")]
ANNEE = [("2026-10-01", "2027-12-31")]
HIVER = [("2026-11-01", "2027-04-30")]

FICHES = [
 f("kalliste-crete", "Club Kalliste", "club", "Grece", "Crete", "TLS ORY LYS", [7,10,14], [890,1150,1420], "tout_compris", 4, ETE,
   "famille plage animation", "piscine, club enfants, sports nautiques, wifi gratuit",
   ["Plage de sable a 150 m", "Animation et encadrement en francais"],
   ["Chambres cote route sensiblement bruyantes", "Restaurant unique : file d'attente au diner en haute saison"], club=(4,12), note=7.8, plage=150),

 f("anemos-rhodes", "Club Anemos Premium", "club_premium", "Grece", "Rhodes", "TLS ORY", [7,10], [1290,1620], "tout_compris", 4, [("2027-04-20","2027-10-20")],
   "famille plage calme", "trois piscines, spa, club enfants, wifi gratuit",
   ["Acces direct a la plage", "Spa inclus dans la formule"],
   ["Peu d'animation en soiree", "Supplement demande pour les restaurants a theme"], club=(3,12), note=8.4, plage=80),

 f("trinacria-sicile", "Club Trinacria", "club", "Italie", "Sicile", "TLS MRS ORY", [7,10,14], [940,1210,1490], "tout_compris", 4, [("2027-05-01","2027-10-10")],
   "famille plage animation", "piscine, club enfants, terrain multisport, navette plage",
   ["Excursions vers Taormine au depart de l'hotel", "Cuisine locale reputee"],
   ["Plage a 300 m, navette toutes les heures seulement", "Climatisation coupee la nuit hors juillet-aout"], club=(4,11), note=7.5, plage=300),

 f("nuraghe-sardaigne", "Club Nuraghe Evasion", "club_evasion", "Italie", "Sardaigne", "ORY TLS", [7,10], [1080,1370], "demi_pension", 3, [("2027-05-15","2027-09-30")],
   "calme nature plage", "piscine, location velos, restaurant panoramique",
   ["Site isole, tres calme", "Criques accessibles a pied"],
   ["Voiture indispensable pour sortir", "Aucune animation, ne convient pas aux ados"], note=8.1, plage=600),

 f("sa-marina-majorque", "Club Sa Marina", "club", "Espagne", "Majorque", "TLS ORY NTE", [7], [780], "tout_compris", 4, [("2027-04-25","2027-10-15")],
   "famille animation plage", "piscine, toboggans, club enfants, mini-golf",
   ["Rapport qualite-prix", "Toboggans tres appreciees des enfants"],
   ["Etablissement dense, bruyant en journee", "Chambres datees dans l'aile ouest"], club=(4,12), note=7.2, plage=250, alias=["Baleares"]),

 f("sevilla-centro", "Sevilla Centro", "city", "Espagne", "Andalousie", "TLS ORY", [3,4,5], [390,470,540], "petit_dejeuner", 2, ANNEE,
   "culture romantique", "patio, rooftop, wifi gratuit",
   ["A pied de la cathedrale et de l'Alcazar", "Rooftop avec vue"],
   ["Chambres petites", "Rue animee jusque tard le week-end"], note=8.0),

 f("yasmine-djerba", "Club Yasmine", "club", "Tunisie", "Djerba", "TLS ORY LYS MRS", [7,10,14], [610,780,940], "tout_compris", 4, [("2026-10-01","2027-11-30")],
   "famille plage animation", "piscine chauffee, club enfants, hammam, animation",
   ["Le meilleur prix du catalogue en tout compris", "Hammam inclus"],
   ["Buffet repetitif au-dela d'une semaine", "Sollicitations commerciales a la sortie de l'hotel"], club=(3,12), note=7.4, plage=100),

 f("sidi-bou-hammamet", "Club Sidi Bou Premium", "club_premium", "Tunisie", "Hammamet", "TLS ORY", [7,10], [890,1120], "tout_compris", 4, [("2026-10-15","2027-11-15")],
   "calme plage luxe", "spa, deux piscines, restaurants a theme, wifi gratuit",
   ["Thalasso incluse deux seances", "Service tres bien note"],
   ["Ambiance calme, peu adaptee aux adolescents", "Plage partagee avec un hotel voisin"], note=8.3, plage=50),

 f("argana-agadir", "Club Argana", "club", "Maroc", "Agadir", "TLS ORY LYS BOD", [7,10,14], [720,920,1130], "tout_compris", 4, ANNEE,
   "famille plage sportif", "piscine, club enfants, tennis, surf, wifi gratuit",
   ["Ouvert toute l'annee, doux en hiver", "Ecole de surf sur place"],
   ["Plage a 400 m par une avenue passante", "Vent fort l'apres-midi une bonne partie de l'annee"], club=(4,12), note=7.6, plage=400),

 f("villes-imperiales", "Circuit Villes Imperiales", "circuit", "Maroc", "Villes imperiales", "TLS ORY", [8], [1090], "pension_complete", 2, [("2026-10-01","2027-12-15")],
   "culture itinerant", "autocar climatise, guide francophone, hotels 4 etoiles",
   ["Quatre villes en huit jours", "Guide francophone sur tout le parcours"],
   ["Rythme soutenu, longues etapes en autocar", "Peu de temps libre"], note=8.2),

 f("lykia-antalya", "Club Lykia", "club", "Turquie", "Antalya", "ORY TLS", [7,10,14], [690,880,1080], "tout_compris", 5, [("2027-04-20","2027-10-30")],
   "famille animation plage", "parc aquatique, club enfants, spa, animation",
   ["Parc aquatique inclus", "Chambres familiales jusqu'a cinq personnes"],
   ["Tres grand complexe, deplacements internes longs", "Plage de galets"], club=(4,12), note=7.7, plage=200),

 f("praia-dourada", "Club Praia Dourada", "club", "Portugal", "Algarve", "TLS ORY NTE", [7,10], [960,1220], "demi_pension", 4, [("2027-04-01","2027-10-31")],
   "calme plage nature", "piscine, sentiers cotiers, restaurant de poisson",
   ["Falaises et criques a pied", "Cuisine de poisson remarquee"],
   ["Pas de formule tout compris", "Acces a la plage par un escalier raide"], note=8.0, plage=350),

 f("funchal-madere", "Funchal Evasion", "club_evasion", "Portugal", "Madere", "ORY TLS", [7], [1140], "demi_pension", 2, ANNEE,
   "nature calme culture", "piscine chauffee, navette centre-ville, jardin",
   ["Randonnees toute l'annee", "Climat doux en hiver"],
   ["Pas de plage de sable sur l'ile", "Denivele important autour de l'hotel"], note=8.5),

 f("corralejo-fuerteventura", "Club Corralejo", "club", "Espagne", "Fuerteventura", "TLS ORY MRS", [7,10,14], [830,1060,1290], "tout_compris", 4, ANNEE,
   "famille plage sportif", "piscines chauffees, club enfants, planche a voile, wifi",
   ["Dunes et plage a deux pas", "Ouvert et agreable meme en janvier"],
   ["Vent presque permanent", "Paysage tres mineral, peu de verdure"], club=(4,12), note=7.3, plage=120, alias=["Canaries", "Iles Canaries"]),

 f("teide-tenerife", "Club Teide Premium", "club_premium", "Espagne", "Tenerife", "ORY TLS", [7,10], [1190,1490], "tout_compris", 4, ANNEE,
   "famille calme luxe", "spa, quatre restaurants, club enfants, piscines chauffees",
   ["Prestations haut de gamme toute l'annee", "Tres bien note par les familles"],
   ["Plage de sable noir", "Zone touristique tres construite"], club=(3,12), note=8.6, plage=60, alias=["Canaries", "Iles Canaries"]),

 f("santa-maria-sal", "Club Santa Maria", "club", "Cap-Vert", "Ile de Sal", "ORY TLS", [7,9,14], [1090,1290,1690], "tout_compris", 4, ANNEE,
   "plage sportif animation", "piscine, club enfants, kitesurf, plongee",
   ["Plage de huit kilometres", "Spot de kitesurf reconnu"],
   ["Ile aride, peu d'excursions culturelles", "Coupures d'eau ponctuelles"], club=(4,12), note=7.9, plage=30),

 f("saly-senegal", "Club Saly", "club", "Senegal", "Petite Cote", "ORY TLS", [7,9], [1150,1340], "tout_compris", 3, [("2026-11-01","2027-05-15")],
   "plage nature calme", "piscine, excursions brousse, peche au gros",
   ["Excursions nature et village de pecheurs", "Personnel tres accueillant"],
   ["Ferme de juin a octobre", "Plage soumise a l'erosion, etroite a maree haute"], note=7.1, plage=20),

 f("flic-en-flac-maurice", "Club Flic en Flac Premium", "club_premium", "Maurice", "Cote Ouest", "ORY", [9,12], [2190,2590], "demi_pension", 4, ANNEE,
   "luxe romantique plage", "spa, golf, plongee, trois restaurants",
   ["Lagon protege, baignade toute l'annee", "Spa et golf inclus deux jours"],
   ["Vols longs avec escale au depart de province", "Boissons non incluses, addition rapide"], note=8.8, plage=40, alias=["Ocean Indien"]),

 f("atoll-maldives", "Atoll Evasion", "club_evasion", "Maldives", "Atoll de Male Sud", "ORY", [9,12], [2890,3390], "pension_complete", 2, ANNEE,
   "romantique luxe plage", "villas sur pilotis, plongee, spa",
   ["Villas sur pilotis avec acces direct au lagon", "Site de plongee exceptionnel"],
   ["Reserve aux adultes, enfants non acceptes", "Aucune sortie possible hors de l'ile"], note=9.1, plage=10, enfants=False, alias=["Ocean Indien"]),

 f("kendwa-zanzibar", "Club Kendwa", "club", "Tanzanie", "Zanzibar", "ORY", [9,12], [1790,2090], "tout_compris", 4, [("2026-11-01","2027-10-15")],
   "plage nature romantique", "piscine, plongee, excursion Stone Town",
   ["Plage sans maree marquee, rare sur l'ile", "Stone Town accessible en excursion"],
   ["Longue route depuis l'aeroport", "Moustiques presents, traitement recommande"], note=8.0, plage=25, alias=["Ocean Indien"]),

 f("bavaro-punta-cana", "Club Bavaro", "club", "Republique dominicaine", "Punta Cana", "ORY TLS", [9,12,16], [1490,1790,2190], "tout_compris", 4, ANNEE,
   "famille animation plage", "parc aquatique, club enfants, spectacles, six restaurants",
   ["Tout compris tres complet, boissons incluses", "Programme d'animation dense"],
   ["Complexe immense et tres frequente", "Sargasses possibles de mai a aout"], club=(4,12), note=7.8, plage=90, alias=["Caraibes"]),

 f("varadero-cuba", "Club Varadero", "club", "Cuba", "Varadero", "ORY", [9,12], [1590,1890], "tout_compris", 4, HIVER,
   "plage culture animation", "piscine, club enfants, excursion La Havane",
   ["Une des plus belles plages des Caraibes", "Excursion a La Havane au programme"],
   ["Approvisionnement irregulier au buffet", "Connexion internet lente et payante"], club=(5,12), note=7.4, plage=60, alias=["Caraibes"]),

 f("akumal-mexique", "Club Akumal", "club", "Mexique", "Riviera Maya", "ORY", [9,12], [1690,1990], "tout_compris", 4, ANNEE,
   "famille culture plage", "piscine, club enfants, snorkeling, excursions mayas",
   ["Sites mayas a moins d'une heure", "Snorkeling avec tortues depuis la plage"],
   ["Sargasses frequentes au printemps", "Supplement pour les restaurants a la carte"], club=(4,12), note=8.1, plage=80),

 f("baie-along", "Circuit Baie d'Along", "circuit", "Vietnam", "Nord et Centre", "ORY", [13], [2290], "pension_complete", 2, [("2026-10-01","2027-04-30")],
   "culture itinerant nature", "guide francophone, nuit en jonque, vols interieurs",
   ["Nuit a bord d'une jonque dans la baie", "Guide francophone du debut a la fin"],
   ["Treize jours avec de nombreux transferts", "Deconseille aux enfants de moins de huit ans"], note=8.7),

 f("kata-phuket", "Club Kata Beach", "club", "Thailande", "Phuket", "ORY", [9,12], [1490,1790], "demi_pension", 3, [("2026-11-01","2027-04-15")],
   "plage animation culture", "piscine, spa, cours de cuisine, navette",
   ["Spa et massages a prix local", "Cours de cuisine thaie inclus"],
   ["Quartier bruyant le soir", "Ferme pendant la mousson, de mai a octobre"], note=7.9, plage=150),

 f("ceylan", "Circuit Ceylan", "circuit", "Sri Lanka", "Sri Lanka", "ORY", [11], [1990], "pension_complete", 2, [("2026-11-01","2027-04-15")],
   "culture nature itinerant", "guide francophone, safari, train panoramique",
   ["Safari a Yala et plantations de the", "Trajet en train panoramique inclus"],
   ["Routes lentes, journees de transfert longues", "Chaleur humide difficile en fin de circuit"], note=8.4),

 f("autotour-bali", "Autotour Bali", "autotour", "Indonesie", "Bali", "ORY", [12], [1890], "petit_dejeuner", 3, ANNEE,
   "nature culture itinerant", "voiture avec chauffeur, hotels de charme, road-book",
   ["Chauffeur prive inclus, rythme libre", "Hotels de charme selectionnes"],
   ["Repas non inclus hors petit-dejeuner", "Circulation difficile dans le sud de l'ile"], note=8.2),

 f("autotour-islande", "Autotour Islande", "autotour", "Islande", "Sud", "ORY CDG", [8,10], [1690,1990], "petit_dejeuner", 4, [("2027-05-15","2027-09-15")],
   "nature itinerant sportif", "voiture de location, guesthouses, road-book",
   ["Cascades, glaciers et sources chaudes", "Jour sans fin en juin et juillet"],
   ["Budget repas tres eleve sur place", "Meteo changeante, conduite exigeante"], note=8.6),

 f("roma-trastevere", "Roma Trastevere", "city", "Italie", "Rome", "TLS ORY", [3,4], [430,510], "petit_dejeuner", 2, ANNEE,
   "culture romantique", "terrasse, wifi gratuit, petit-dejeuner italien",
   ["Quartier vivant, a pied du Trastevere", "Excellent petit-dejeuner"],
   ["Ascenseur absent, trois etages", "Bruit de la rue jusque tard"], note=8.3),

 f("croisiere-cyclades", "Croisiere Cyclades", "croisiere", "Grece", "Cyclades", "ORY", [8], [1590], "pension_complete", 2, [("2027-05-01","2027-09-30")],
   "itinerant culture romantique", "cabine exterieure, escales quotidiennes, guide",
   ["Cinq iles en huit jours", "Escales longues, temps a terre reel"],
   ["Cabines exigues", "Mer parfois formee en juillet avec le meltem"], note=8.0),
]


def principal() -> int:
    problemes = valider_catalogue(FICHES)
    if problemes:
        print(f"{len(problemes)} probleme(s), catalogue NON ecrit :")
        for probleme in problemes:
            print(f"  - {probleme}")
        return 1

    destination = RACINE / "data" / "catalogue.json"
    destination.write_text(
        json.dumps(FICHES, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"{len(FICHES)} fiches ecrites dans {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
