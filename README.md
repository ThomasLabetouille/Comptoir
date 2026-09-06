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
python -m pytest tests -q               # 167 tests
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
comptoir/classement.py    reordonne les propositions retenues sur l'ambiance, la note, la plage
comptoir/redaction.py     demande + resultat -> reponse redigee, verifiee affirmation par affirmation
data/catalogue.json       30 fiches fictives (voir SOURCES.md)
data/comptoir.db          genere - jamais commit, voir outils/construire_base_sql.py
outils/                   generation du catalogue et de la base, recherche en ligne de commande, mesure
tests/requetes.jsonl      20 demandes ecrites comme un client parle, avec l'attendu
```

`tests/requetes.jsonl` porte a la fois le texte libre et la demande structuree
correspondante. La demande structuree sert de reference au moteur aujourd'hui ; le texte
libre servira de jeu d'evaluation quand l'extraction automatique sera en place.

## Ce qui est mesure

Trois chiffres, mesures pour de vrai sur les 20 requetes du jeu de test.

Contraintes dures violees : 0, verifie a chaque commit. Une proposition au-dessus du
budget, hors des dates demandees ou trop petite pour le groupe fait echouer la CI. J'ai
re-implemente les controles a la main dans `tests/test_contraintes_dures.py` plutot que
d'appeler les fonctions du moteur : un test qui verifie le code avec le code teste se
contente de confirmer que la fonction est d'accord avec elle-meme.

Abstention : 10 cas insolubles sur 10. Le moteur ne propose rien quand rien ne correspond,
et nomme le critere a assouplir. C'est teste sur les demandes structurees pour l'instant -
la vraie question se posera avec un modele dans la boucle, qui preferera presque toujours
inventer plutot que decevoir.

Tracabilite : verifiee affirmation par affirmation dans `comptoir/redaction.py`, mesurable
en conditions reelles avec `outils/mesurer.py` (Ollama doit tourner) :

```bash
python3 outils/mesurer.py
python3 outils/mesurer.py --sortie data/mesures_tracabilite.json
```

Fait tourner le pipeline complet - texte libre -> Demande -> Resultat -> reponse redigee -
sur les 20 requetes du jeu de test, avec le vrai modele plutot que leur demande structuree
de reference, et rapporte l'extraction reussie, l'abstention correcte sur les requetes
insolubles et la tracabilite moyenne (`Redaction.taux_de_verification()`). Une requete qui
echoue est journalisee, jamais fatale pour les 19 autres - voir `tests/test_mesurer.py`
pour la mecanique testee sans reseau (extraire() et rediger() simules, 8 tests).

Chaque requete peut prendre plusieurs dizaines de secondes (deux appels au modele local,
extraction puis redaction) : le script affiche une ligne des qu'une requete est traitee
plutot que d'attendre les 20 pour tout afficher d'un coup - sans ca, l'ecran reste vide
plusieurs minutes et donne l'impression que rien ne se passe.

Resultat mesure pour de vrai (Ollama lance, jeu de 20 requetes, detail dans
`data/mesures_tracabilite.json`) : extraction reussie 20/20, abstention correcte 8/8,
traçabilite moyenne 0.86 sur les 10 reponses effectivement redigees.

Un detail de ce passage vaut d'etre note. Sur 63 affirmations produites par le modele, 12
ont ete ecartees - et aucune pour avoir contredit une fiche : toutes etaient des
affirmations annoncees puis laissees sans texte. Le verificateur n'a donc rien eu a
rattraper cette fois-la. C'est un passage sur vingt requetes, pas une garantie, mais les
motifs de rejet sont maintenant enregistres, ce qui permet de distinguer un modele qui
invente d'un modele qui bafouille - et le taux de 0.86 est tire vers le bas par le second
plutot que par le premier.

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

### « Meme chose mais pas plus de 3000 euros »

Un client ne repete pas ce qu'il vient de dire. Lue seule, la phrase ci-dessus ne parle
que d'un budget : ni destination, ni dates, ni nombre de voyageurs. C'est exactement ce
que la mesure en conditions reelles a montre - deux des huit cas insolubles n'etaient pas
detectes parce que la demande de suite arrivait amputee de tout son contexte.

`extraire()` accepte donc une demande precedente. Le modele, lui, ne voit toujours que la
derniere phrase et n'a rien a decider de ce qui reste valable : c'est
`comptoir/demande.py:fusionner()` qui reprend, champ par champ, ce que la nouvelle phrase
ne mentionne pas. Savoir quels champs elle mentionne demande une precaution - dans une
`Demande`, « le client n'a pas parle du nombre d'adultes » et « le client a dit deux
adultes » donnent tous les deux 2. `champs_fournis()` regarde donc la reponse du modele
pour ces deux champs-la, et la Demande nettoyee pour tous les autres, de sorte qu'une
valeur proposee puis ecartee comme invalide ne compte pas comme fournie.

Sans demande precedente, rien ne change : la phrase est lue seule, comme avant.
`tests/test_suite_demande.py` couvre la fusion et les cas limites (14 tests, sans reseau).

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

## Le classement, separe du filtrage

```powershell
python outils\chercher.py --essai --nuits 7 --budget 5000 --ambiance animation
python outils\chercher.py --essai --nuits 7 --budget 5000 --ambiance calme
```

Meme budget, meme duree - deux ensembles de sejours completement differents en tete,
selon l'ambiance demandee. `filtrer()` garde son tri par prix inchange : c'est le
contrat que `tests/test_base_sql.py` verifie contre le portage SQL, et il ne devait
pas bouger pour ajouter du classement. `comptoir/classement.py` est donc une etape
separee, appliquee seulement a l'affichage - elle reordonne ce que `filtrer()` a
deja valide, elle ne decide jamais ce qui est valide.

Le score combine l'ambiance demandee (recouvrement avec `fiche["ambiance"]`), la
note clients et la proximite de la plage, ponderees 50/30/20. Pas de RAG ni
d'embeddings : le catalogue est une poignee de champs structures par fiche, pas
un corpus de texte a chercher par similarite semantique - une recherche
vectorielle serait une solution a un probleme que ce projet n'a pas. Une fiche
sans note ou sans distance renseignee reste neutre (0.5), plutot que d'etre
penalisee pour une information absente. `tests/test_classement.py` teste chaque
composante du score et le classement final (15 tests, sans reseau).

`comptoir/redaction.py` s'appuie dessus : le modele redige desormais sur les
propositions les mieux classees pour cette demande, pas seulement les moins
cheres.

## Facade Java

`facade-java/` est un service Spring Boot qui appelle `interface/serveur.py` par HTTP -
pas une deuxieme implementation du moteur, une porte d'entree devant lui, avec
validation des requetes et pannes traduites en reponses HTTP propres. Ecrit depuis un
environnement qui n'a pas acces a Maven Central, donc d'abord verifie a la main plutot
qu'avec `mvn` ; `mvn clean verify` confirme depuis que ca compile et que les 4 tests
passent (JDK 17, Maven 3.9.16). Voir `facade-java/README.md`.

## Interface web

```bash
pip install -r requirements.txt -r requirements-interface.txt
python3 -m uvicorn interface.serveur:app --reload
```

Puis ouvrir `http://127.0.0.1:8000`. Une page, un champ de texte, une case a cocher
pour demander la reponse redigee. Les sejours retenus s'affichent avec leur prix reel
pour la composition du groupe, leur point fort et leur point faible ; quand rien ne
correspond, c'est le diagnostic qui prend la place des propositions, pas une page vide.

La page garde la derniere demande comprise, et une case a cocher permet d'enchainer
« meme chose mais notre fils a 2 ans » sans tout retaper. La case est decochee apres
chaque recherche : deux demandes sans rapport ne doivent pas cumuler leurs criteres - ce
defaut-la s'est vu des la premiere utilisation reelle, la reprise etant au depart
automatique. Elle se coche d'elle-meme quand l'exemple choisi est marque comme une demande
de suite. La reprise des criteres reste faite cote Python par `fusionner()` ; le navigateur
ne fait que transporter la demande precedente.

`interface/serveur.py` reste hors de `comptoir/` :
le coeur du projet ne depend que de la bibliotheque standard, et exposer ce coeur
dans un navigateur ne devait pas casser cette regle. FastAPI et uvicorn vivent donc
dans `requirements-interface.txt`, separe de `requirements.txt`.

`tests/test_interface.py` verifie que le serveur demarre et que la page se rend,
sans reseau ; l'extraction et la redaction, elles, ont toujours besoin d'Ollama
lance en local - la meme contrainte qu'en ligne de commande.

## Le catalogue

Les fiches sont fictives (voir `SOURCES.md`) mais respectent les contraintes qui rendent la
recherche difficile : durees fixes avec un prix par personne pour chacune, periodes d'ouverture
saisonnieres, capacites maximales par chambre, clubs enfants avec des tranches d'age variables.

J'ai rendu `points_faibles` obligatoire : une fiche sans point faible fait echouer
la validation. Un agent a besoin de savoir quoi annoncer avant que le client le decouvre
sur place, et un catalogue qui ne dit que du bien n'est pas utilisable au comptoir.

### Brancher un autre catalogue

Le moteur ne connait pas le catalogue d'un voyagiste en particulier : il connait la forme
decrite par `comptoir/schema.py`. Y brancher un vrai catalogue, c'est traduire l'export du
voyagiste dans cette forme - le moteur, lui, ne bouge pas.

`outils/convertir_catalogue.py` fait cette traduction depuis un CSV, avec un export
d'exemple pour l'essayer :

```powershell
python outils\convertir_catalogue.py data\exemple_import.csv
python outils\convertir_catalogue.py data\exemple_import.csv --sortie data\catalogue.json
```

```
4 ligne(s) lue(s) dans data/exemple_import.csv
3 fiche(s) convertie(s), 1 refusee(s)

  refuse - ligne 5 : 3 duree(s) pour 2 prix : chaque duree vendue doit avoir son prix

Catalogue valide. Relancez avec --sortie FICHIER pour l'ecrire.
```

Trois choix de conception, tous pour la meme raison - un export reel est toujours
imparfait, et un catalogue a moitie faux est pire qu'un catalogue absent :

- toute l'adaptation a un nouveau fournisseur tient dans le dictionnaire `CORRESPONDANCE`
  en tete du fichier, qui met en face de chaque champ attendu le nom de la colonne qui le
  remplit. C'est un tableau a deux colonnes, qui se remplit avec les gens du metier plutot
  que devant un ecran ;
- une ligne qui ne se traduit pas est refusee avec son numero et la raison, et n'interrompt
  pas les autres. Chaque fiche produite passe en plus `valider_fiche()` avant d'etre
  retenue, donc une conversion approximative se voit tout de suite ;
- sans `--sortie`, rien n'est ecrit. Le script dit ce qu'il produirait, ce qui permet de
  regarder les refus avant de toucher au catalogue existant.

`tests/test_convertisseur.py` couvre la traduction et les refus (16 tests, sans reseau).

## Hypotheses simplificatrices

- Un enfant de moins de 12 ans paie 70 % du prix adulte. Un vrai catalogue porte cette regle
  par fiche et par periode.
- Le prix est celui du sejour, vol inclus, sans option ni assurance.
- Aucune disponibilite en temps reel : une fiche ouverte a la periode demandee est consideree
  comme reservable.

## Etat d'avancement

Le catalogue, la validation, le filtrage dur (en Python et, verifie identique, en SQL), le
diagnostic de blocage, l'extraction texte -> demande, le classement sur criteres souples, la
redaction verifiee, la mesure en conditions reelles et une interface web minimale
fonctionnent, et la facade Java compile et passe ses tests (`mvn clean verify`, JDK 17,
Maven 3.9.16 - voir `facade-java/README.md`).

La mesure en conditions reelles (`outils/mesurer.py`) a demande deux passages avant de
donner un chiffre exploitable. Le premier a bute sur des reponses tronquees et des delais
depasses : le modele produisait des reponses plus longues que la fenetre de contexte par
defaut ne laissait de place, et rajoutait parfois un raisonnement explicite avant le JSON
attendu. J'ai elargi `num_ctx` et `num_predict`, porte le delai a 120s - et le deuxieme
passage a revele un second probleme, different : le modele partait par moments en boucle de
repetition sur les listes de propositions, produisant du JSON syntaxiquement valide mais
rempli de texte duplique en boucle. Ajoute `repeat_penalty` pour decourager la repetition et
`think: false` pour couper le raisonnement libre qui faisait aussi trainer l'extraction.
Chiffres dans `data/mesures_tracabilite.json` et resumes plus haut.

Cette mesure a mis deux choses au jour, corrigees puis re-mesurees depuis :

- les deux cas insolubles non detectes etaient des demandes de suite lues hors contexte.
  `extraire(precedente=...)` et `fusionner()` traitent ce cas, et `tests/requetes.jsonl`
  marque les trois demandes concernees par un champ `suite_de` que `outils/mesurer.py`
  suit pour rechainer. L'abstention est passee de 6/8 a 8/8 ;
- `outils/mesurer.py` n'enregistrait que le nombre d'affirmations rejetees, ce qui ne
  permet pas de distinguer un modele qui invente d'un verificateur trop strict. Les motifs
  et la demande extraite sont maintenant dans la sortie JSON - c'est ce qui a permis de
  voir que les rejets etaient des affirmations vides, pas des affirmations fausses.

Un troisieme defaut n'est apparu qu'a l'usage reel de l'interface, pas a la mesure : la
page renvoyait la derniere demande comprise a chaque recherche, si bien que deux demandes
sans rapport cumulaient leurs criteres et ne trouvaient plus rien des le deuxieme essai.
La reprise passe maintenant par une case a cocher, decochee par defaut.

Ce qui reste, et qui est mesure : deux demandes tres vagues du jeu de test - « quelque
chose de calme au bord de la mer », « un circuit culturel » - recoivent un refus alors que
le catalogue a des offres. Le moteur se trompe donc en refusant plutot qu'en inventant,
mais il se trompe.

`comptoir/extraction.py` et `comptoir/redaction.py` ont chacun un chemin non teste par la
suite automatique : l'appel reseau reel a Ollama (`appeler_ollama()` dans les deux modules).
Le reste de chaque module l'est (parsing, nettoyage ou verification, 40 tests entre les
deux) ; seul l'aller-retour HTTP vers un modele reellement lance ne peut se verifier que sur
la machine ou Ollama tourne.
