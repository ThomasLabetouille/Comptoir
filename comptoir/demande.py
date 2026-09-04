"""Ce qu'un client demande, sous forme structuree.

C'est la sortie de l'etape d'extraction (semaine 2) et l'entree du moteur.
Tant que l'extraction n'existe pas, on remplit cet objet a la main : le moteur
peut donc etre teste et mesure avant qu'un modele de langage entre en jeu.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Demande:
    """Une demande client. Tout est optionnel sauf le nombre d'adultes.

    Les champs 'ambiance' et 'non_precise' ne filtrent jamais : le premier sert
    au classement, le second recense ce que le client n'a pas dit pour que
    l'assistant puisse poser la question au lieu de deviner.
    """

    adultes: int = 2
    enfants_ages: list[int] = field(default_factory=list)
    destinations: list[str] = field(default_factory=list)
    date_debut: str | None = None
    date_fin: str | None = None
    duree_nuits: int | None = None
    budget_total_max: int | None = None
    budget_pp_max: int | None = None
    formules: list[str] = field(default_factory=list)
    depart: str | None = None
    club_enfants_requis: bool = False
    ambiance: list[str] = field(default_factory=list)
    non_precise: list[str] = field(default_factory=list)

    @property
    def voyageurs(self) -> int:
        return self.adultes + len(self.enfants_ages)

    @classmethod
    def depuis_dict(cls, donnees: dict) -> "Demande":
        connus = {champ for champ in cls.__dataclass_fields__}
        inconnus = set(donnees) - connus
        if inconnus:
            raise ValueError(f"champs de demande inconnus: {sorted(inconnus)}")
        return cls(**donnees)
