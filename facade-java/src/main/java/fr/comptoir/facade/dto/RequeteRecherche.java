package fr.comptoir.facade.dto;

import jakarta.validation.constraints.NotBlank;

/**
 * Ce que le client de la facade envoie - le meme contrat que
 * interface/serveur.py cote Python (texte, rediger), pour que les deux
 * points d'entree restent interchangeables.
 */
public record RequeteRecherche(

        @NotBlank(message = "le texte de la demande ne peut pas etre vide")
        String texte,

        boolean rediger
) {
}
