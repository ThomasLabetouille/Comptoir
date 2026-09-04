# Comptoir

Un agent de voyages au telephone entend :

> « On est quatre, deux enfants de 8 et 14 ans, on hesite entre la Crete et la Sicile,
> deuxieme quinzaine de juillet, tout compris, 3500 euros maximum, et si possible au
> depart de Toulouse. »

Il doit traduire cette phrase en une suite de filtres, et tout recommencer des que le client
bouge un critere. Comptoir prend la phrase telle qu'elle a ete dite et rend les sejours qui
correspondent vraiment, avec leur prix reel pour cette composition familiale — et quand rien
ne correspond, il dit lequel des criteres il faudrait assouplir.

## Le principe

Le modele de langage comprend la demande et redige la reponse. Il ne decide rien.

Prix, dates, capacite des chambres, formule de restauration, aeroport de depart : tout ce qui
est verifiable est tranche dans `comptoir/filtres.py`, en Python, avec des comparaisons. Aucun
modele n'est appele pour savoir si 3293 euros tient dans un budget de 3000.

Dans le tourisme, une hallucination n'est pas une curiosite : c'est un client qui arrive dans
un hotel qui n'a pas le club enfants qu'on lui a promis. La separation ci-dessus est la seule
chose qui empeche ca de facon fiable.

## Lancer

```bash
python3 outils/construire_catalogue.py   # (re)genere data/catalogue.json
python3 -m pytest tests -q               # 45 tests
python3 outils/chercher.py q02           # rejoue une demande client
python3 outils/chercher.py --toutes
```

Le noyau ne depend que de la bibliotheque standard. `pytest` sert uniquement aux tests.

Un cas ou rien ne correspond :

```
$ python3 outils/chercher.py q03
[q03] Le client dit :
  « Meme chose mais on ne peut pas mettre plus de 3000 euros. »

  4 voyageur(s) | Crete, Sicile | 7 nuits | max 3000 EUR

  Aucun sejour ne correspond. En relachant un seul critere - le budget (le moins cher
  qui correspond est a 3293 EUR au total) : 2 option(s) s'ouvriraient ; la destination :
  4 option(s) s'ouvriraient.
```

Les pistes sont classees dans l'ordre ou un agent negocie reellement : le budget d'abord,
les dates ensuite, la destination en dernier. Trier par nombre d'options aurait donne
l'inverse, et un conseil inutilisable.

## Organisation

```
comptoir/schema.py     definition d'une fiche + validation d'un catalogue
comptoir/demande.py    ce qu'un client veut, sous forme structuree
comptoir/filtres.py    les criteres durs et le diagnostic de blocage
comptoir/catalogue.py  chargement
data/catalogue.json    30 fiches fictives (voir SOURCES.md)
outils/                generation du catalogue, recherche en ligne de commande
tests/requetes.jsonl   20 demandes ecrites comme un client parle, avec l'attendu
```

`tests/requetes.jsonl` porte a la fois le texte libre et la demande structuree
correspondante. La demande structuree sert de reference au moteur aujourd'hui ; le texte
libre servira de jeu d'evaluation quand l'extraction automatique sera en place.

## Ce qui est mesure

Trois chiffres, dont un seul tourne aujourd'hui.

**Contraintes dures violees — 0, verifie a chaque commit.** Une proposition au-dessus du
budget, hors des dates demandees ou trop petite pour le groupe fait echouer la CI.
`tests/test_contraintes_dures.py` re-implemente les controles a la main plutot que d'appeler
les fonctions du moteur : un test qui verifie le code avec le code teste se contente de
confirmer que la fonction est d'accord avec elle-meme.

**Abstention — 10 cas insolubles sur 10.** Le moteur ne propose rien quand rien ne correspond,
et nomme le critere a assouplir. C'est teste sur les demandes structurees. La vraie question
se posera avec un modele dans la boucle : livre a lui-meme, il preferera presque toujours
inventer plutot que decevoir.

**Tracabilite — pas encore.** Chaque affirmation de la reponse redigee devra pointer vers un
champ existant de la fiche citee, et un verificateur retirera celles qui ne s'y retrouvent pas.
Rien de tout ca n'existe tant que l'etape de redaction n'est pas ecrite.

## Le catalogue

Les fiches sont fictives (voir `SOURCES.md`) mais respectent les contraintes qui rendent la
recherche difficile : durees fixes avec un prix par personne pour chacune, periodes d'ouverture
saisonnieres, capacites maximales par chambre, clubs enfants avec des tranches d'age variables.

`points_faibles` est obligatoire — une fiche sans point faible fait echouer la validation.
Un agent a besoin de savoir quoi annoncer avant que le client le decouvre sur place, et un
catalogue qui ne dit que du bien n'est pas utilisable au comptoir.

## Hypotheses simplificatrices

- Un enfant de moins de 12 ans paie 70 % du prix adulte. Un vrai catalogue porte cette regle
  par fiche et par periode.
- Le prix est celui du sejour, vol inclus, sans option ni assurance.
- Aucune disponibilite en temps reel : une fiche ouverte a la periode demandee est consideree
  comme reservable.

## Etat d'avancement

Le catalogue, la validation, le filtrage dur et le diagnostic de blocage fonctionnent.
Ce qui manque :

- l'extraction du texte libre vers une demande structuree ;
- le classement des resultats sur les criteres souples (ambiance, note, distance a la plage),
  aujourd'hui limite au tri par prix ;
- la redaction des propositions avec citation obligatoire, et le verificateur qui va avec ;
- une interface autre que la ligne de commande.
