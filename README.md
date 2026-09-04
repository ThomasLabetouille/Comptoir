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

Sous Windows l'interpreteur s'appelle `python` ou `py`, jamais `python3` :
`python3` y est un raccourci vide qui renvoie vers le Microsoft Store.
Sous Linux et macOS, remplacer `python` par `python3`.

```powershell
python outils\construire_catalogue.py   # (re)genere data/catalogue.json
python -m pytest tests -q               # 109 tests
python outils\chercher.py q02           # rejoue une demande client
python outils\chercher.py --toutes      # les 20 demandes du jeu de test
```

Composer sa propre demande (une seule ligne, quel que soit le shell) :

```powershell
python outils\chercher.py --essai --destination Crete --nuits 7 --budget 2000
python outils\chercher.py --essai --adultes 2 --enfants 8 14 --destination Crete Sicile --du 2027-07-15 --au 2027-07-31 --nuits 7 --formule tout_compris --depart TLS --budget 3500
```

`python outils\chercher.py --help` liste toutes les options.

Le noyau ne depend que de la bibliotheque standard (Python 3.10 ou plus recent).
`pytest` sert uniquement aux tests : `pip install pytest`.

Un cas ou rien ne correspond :

```
> python outils\chercher.py q03
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
comptoir/filtres.py       les criteres durs et le diagnostic de blocage
comptoir/catalogue.py     chargement du catalogue JSON
comptoir/base_donnees.py  le meme filtrage, en SQL, verifie contre filtres.py
comptoir/extraction.py    texte libre -> Demande, via Ollama en local
comptoir/redaction.py     demande + resultat -> reponse redigee, verifiee affirmation par affirmation
data/catalogue.json       30 fiches fictives (voir SOURCES.md)
data/comptoir.db          genere - jamais commit, voir outils/construire_base_sql.py
outils/                   generation du catalogue et de la base, recherche en ligne de commande
tests/requetes.jsonl      20 demandes ecrites comme un client parle, avec l'attendu
```

`tests/requetes.jsonl` porte a la fois le texte libre et la demande structuree
correspondante. La demande structuree sert de reference au moteur aujourd'hui ; le texte
libre servira de jeu d'evaluation quand l'extraction automatique sera en place.

## Ce qui est mesure

Trois chiffres, dont un seul tourne aujourd'hui.

Contraintes dures violees : 0, verifie a chaque commit. Une proposition au-dessus du
budget, hors des dates demandees ou trop petite pour le groupe fait echouer la CI. J'ai
re-implemente les controles a la main dans `tests/test_contraintes_dures.py` plutot que
d'appeler les fonctions du moteur : un test qui verifie le code avec le code teste se
contente de confirmer que la fonction est d'accord avec elle-meme.

Abstention : 10 cas insolubles sur 10. Le moteur ne propose rien quand rien ne correspond,
et nomme le critere a assouplir. C'est teste sur les demandes structurees pour l'instant -
la vraie question se posera avec un modele dans la boucle, qui preferera presque toujours
inventer plutot que decevoir.

Tracabilite : verifiee affirmation par affirmation dans `comptoir/redaction.py`, mais
pas encore mesuree en continu sur un jeu de reponses reelles - `tests/test_redaction.py`
teste le verificateur avec des sorties de modele simulees (16 tests, sans reseau), pas
encore avec Ollama effectivement lance sur les 20 requetes du jeu de test.

## Le meme moteur, en SQL

`comptoir/base_donnees.py` reimplemente en SQLite les criteres qui se ramenent a une
appartenance a un ensemble - destination, aeroport de depart, duree, formule, capacite,
enfants, club enfants - dans une seule requete parametree avec des `EXISTS` sur des tables
normalisees (fiches, aeroports_depart, durees_prix, periodes_ouverture, et une table `lieux`
qui met a plat pays/region/alias pour n'avoir qu'un seul endroit ou chercher "Ocean Indien").

La periode et le prix restent en Python : une intersection de plages de dates et une remise
enfant n'ont pas leur place dans une clause `WHERE` sans devenir illisibles, et les fonctions
qui les calculent sont deja testees. `tests/test_base_sql.py` recompose le resultat complet
(SQL pour l'ensemble, Python pour le calcul) et verifie qu'il est identique, fiche par fiche
et prix par prix, a `comptoir.filtres.filtrer()` sur les 20 memes requetes. Le portage n'est
pas suppose correct parce qu'il ressemble a l'original ; il est verifie contre lui.

```bash
python outils\construire_base_sql.py   # (re)genere data/comptoir.db depuis catalogue.json
```

Construire une base SQLite sur le dossier de developpement (le pont utilise pour ecrire ce
projet, potentiellement un lecteur reseau plus tard) echoue si on ouvre une connexion en
ecriture directement dessus - erreur d'E/S disque, alors que la lecture ne pose aucun probleme.
`construire()` contourne ca sans y penser a chaque appel : elle batit la base dans un fichier
temporaire local puis copie le resultat fini en une fois. `data/comptoir.db` n'est jamais
commit (voir `.gitignore`) - seul `data/catalogue.json` est la source versionnee, la base se
regenere en une commande.

## Du langage libre a la demande

```powershell
python outils\chercher.py --texte "on est quatre, deux enfants de 8 et 14 ans, Crete ou Sicile, deuxieme quinzaine de juillet, tout compris, 3500 euros, depart Toulouse"
```

Exige Ollama lance en local (`ollama serve`, modele `gemma4:12b` deja utilise dans
`IA_Locale/assistant_local`) - aucune dependance ajoutee, l'appel passe par `urllib`
plutot que par le paquet `ollama`. Sans reseau ou sans Ollama lance, l'echec est propre :

```
Extraction impossible : Ollama injoignable sur http://localhost:11434 - est-il lance ?
```

Le meme principe qu'ailleurs dans le projet s'applique a la sortie du modele elle-meme,
pas seulement a ses reponses : un JSON produit par un modele n'est fiable ni sur la forme
(peut arriver entoure de balises markdown, de prose, tronque) ni sur le fond (une formule
qui n'existe pas dans le catalogue, un age d'enfant hors limites, une date mal formee).
`comptoir/extraction.py` ne fait confiance a rien de tout ca : ce qui est invalide est
ecarte, jamais devine, et signale dans `Demande.non_precise` - le meme champ qui recense
ce que le client n'a simplement pas dit. `tests/test_extraction.py` teste ce nettoyage
avec des reponses de modele deliberement imparfaites (24 tests, sans reseau).

Un module interne, `comptoir/_json_modele.py`, isole le decodage JSON tolerant aux balises
markdown et au texte tronque : `comptoir/redaction.py` (section suivante) en a besoin pour
la meme raison, sur une sortie de modele differente.

`--essai` reste disponible pour composer une demande sans modele, en particulier pour
deboguer le moteur independamment de l'extraction.

## La redaction, verifiee affirmation par affirmation

```powershell
python outils\chercher.py q01 --rediger
```

Une fois le moteur passe, `comptoir/redaction.py` demande au modele de rediger une reponse
pour l'agent - mais pas en texte libre. Le modele ne voit que les fiches deja retenues par
`filtrer()`, et doit rendre un JSON ou chaque phrase est explicitement rattachee a un champ
d'une fiche precise (`{"champ": "points_faibles", "texte": "..."}`).

`verifier()` re-cherche ensuite chaque affirmation dans la fiche qu'elle cite : une fiche
jamais presentee au modele, un champ qui n'existe pas, un prix qui ne correspond pas au
montant reellement calcule pour cette demande - tout ca est retire de la reponse et
journalise dans `Redaction.rejetees`, jamais montre au client. `tests/test_redaction.py`
verifie ce filet avec des sorties de modele deliberement malhonnetes (16 tests, sans reseau).

Quand `filtrer()` ne retient rien, le modele n'est pas appele du tout : la reponse est
directement `Resultat.diagnostic()`. Un modele livre a lui-meme prefere presque toujours
inventer plutot que decevoir ; la seule facon fiable d'empecher ca est de ne jamais lui en
laisser l'occasion.

## Le catalogue

Les fiches sont fictives (voir `SOURCES.md`) mais respectent les contraintes qui rendent la
recherche difficile : durees fixes avec un prix par personne pour chacune, periodes d'ouverture
saisonnieres, capacites maximales par chambre, clubs enfants avec des tranches d'age variables.

J'ai rendu `points_faibles` obligatoire : une fiche sans point faible fait echouer
la validation. Un agent a besoin de savoir quoi annoncer avant que le client le decouvre
sur place, et un catalogue qui ne dit que du bien n'est pas utilisable au comptoir.

## Hypotheses simplificatrices

- Un enfant de moins de 12 ans paie 70 % du prix adulte. Un vrai catalogue porte cette regle
  par fiche et par periode.
- Le prix est celui du sejour, vol inclus, sans option ni assurance.
- Aucune disponibilite en temps reel : une fiche ouverte a la periode demandee est consideree
  comme reservable.

## Etat d'avancement

Le catalogue, la validation, le filtrage dur (en Python et, verifie identique, en SQL), le
diagnostic de blocage, l'extraction texte -> demande et la redaction verifiee fonctionnent.
Ce qui manque :

- le classement des resultats sur les criteres souples (ambiance, note, distance a la plage),
  aujourd'hui limite au tri par prix ;
- une mesure en continu de la tracabilite sur les 20 requetes du jeu de test, avec Ollama
  effectivement lance - aujourd'hui `verifier()` est teste, mais pas encore le pipeline
  complet en conditions reelles ;
- une interface autre que la ligne de commande ;
- une facade Java/Spring Boot devant le service, pour presenter un point d'integration dans
  le langage le plus demande sur les offres techniques du groupe.

`comptoir/extraction.py` et `comptoir/redaction.py` ont chacun un chemin non teste par la
suite automatique : l'appel reseau reel a Ollama (`appeler_ollama()` dans les deux modules).
Le reste de chaque module l'est (parsing, nettoyage ou verification, 40 tests entre les
deux) ; seul l'aller-retour HTTP vers un modele reellement lance ne peut se verifier que sur
la machine ou Ollama tourne.
