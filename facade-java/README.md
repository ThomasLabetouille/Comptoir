# Facade Java (Spring Boot)

Un service Spring Boot devant `interface/serveur.py` (le service Python) - pas une
deuxieme implementation du moteur de recherche. `ComptoirClient` appelle l'API Python
par HTTP ; la facade ajoute la validation des requetes et traduit les pannes du service
Python en reponses HTTP propres (400 pour une demande mal formee, 502 pour un service
Python injoignable). Le meme principe que `comptoir/base_donnees.py` cote SQL : une
couche verifiee ou branchee sur l'original, jamais une copie de sa logique maintenue en
parallele.

Pourquoi ce module existe : le developpement du groupe (hors siege Toulouse) est
majoritairement en Java/Spring/Hibernate/Maven. Le reste de Comptoir est en Python -
delibere, voir le README principal - mais rien n'empechait de montrer une integration
Java propre par-dessus, sans dupliquer ce qui marche deja.

## Lancer

Le service Python doit tourner (port 8000 par defaut) :

```bash
cd ..
pip install -r requirements.txt -r requirements-interface.txt
python3 -m uvicorn interface.serveur:app --port 8000
```

Puis, dans ce dossier, avec un JDK 17+ et Maven installes :

```bash
mvn spring-boot:run
```

La facade ecoute sur le port 8081 et relaie vers le port 8000 :

```bash
curl -X POST http://127.0.0.1:8081/api/comptoir/chercher \
  -H "Content-Type: application/json" \
  -d '{"texte": "on est deux, une semaine en Crete, tout compris, 2000 euros", "rediger": false}'
```

## Tests

```bash
mvn test
```

`ComptoirControllerTest` teste la couche web avec `ComptoirClient` simule
(`@MockBean`) - rien n'appelle le service Python reellement, le meme esprit que
`tests/test_interface.py` cote Python : verifier ce qui peut l'etre sans dependance
externe, sans pretendre tester ce qui en a besoin.

## Une limite a connaitre

Ce module a ete ecrit depuis un environnement de developpement a distance qui n'a pas
acces a Maven Central (seuls PyPI, npm et GitHub le sont depuis ce pont) - il n'a donc
jamais pu etre compile ni ses tests executes avant d'arriver dans ce depot,
contrairement au reste du projet (135 tests Python, tous verifies reellement). La
structure a ete verifiee (accolades et parentheses equilibrees, imports coherents avec
les dependances declarees dans `pom.xml`), mais `mvn clean verify` n'a jamais tourne
pour de vrai. Premiere chose a faire avant de s'en servir en demo.
