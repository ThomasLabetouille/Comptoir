# Origine des donnees

Le catalogue de `data/catalogue.json` est **entierement fictif**. Les etablissements,
les prix, les notes et les periodes d'ouverture sont inventes. Toute ressemblance avec
un hotel existant serait fortuite : je n'ai repris aucune fiche, aucun descriptif et
aucun tarif d'un catalogue reel.

Ce qui est reproduit fidelement, c'est la **structure** d'un catalogue de voyagiste :

- des gammes distinctes (club, club premium, circuit accompagne, autotour, city break,
  croisiere) qui n'obeissent pas aux memes contraintes ;
- des periodes d'ouverture par etablissement, souvent saisonnieres ;
- des durees fixes avec un prix par personne different pour chacune, et non un prix par nuit ;
- des aeroports de depart limites par produit ;
- des capacites maximales par chambre, qui eliminent silencieusement les familles nombreuses ;
- des clubs enfants avec des tranches d'age qui ne se recouvrent pas d'un hotel a l'autre.

Ces contraintes sont ce qui rend la recherche difficile. Elles suffisent a faire tourner et a
mesurer le moteur ; brancher un vrai catalogue reviendrait a remplacer le contenu de
`data/catalogue.json`, pas a changer le code.

Les fiches sont ecrites dans `outils/construire_catalogue.py` et le JSON en est genere.
Modifier le JSON a la main ne sert a rien : `tests/test_catalogue.py` verifie que les deux
sont identiques.
