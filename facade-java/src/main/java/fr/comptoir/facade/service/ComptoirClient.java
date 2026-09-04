package fr.comptoir.facade.service;

import fr.comptoir.facade.dto.RequeteRecherche;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.util.List;
import java.util.Map;

/**
 * Appelle le service Python (comptoir/, expose par interface/serveur.py) -
 * ne reimplemente jamais sa logique de recherche. Le moteur, l'extraction
 * et la redaction restent une seule source de verite, en Python ; cette
 * classe est une porte d'entree, pas une deuxieme implementation a
 * maintenir en parallele - le meme principe que comptoir/base_donnees.py
 * cote SQL, qui est verifie CONTRE le moteur Python plutot que de le
 * doubler sans lien avec lui.
 */
@Service
public class ComptoirClient {

    private final RestClient restClient;
    private final String urlDeBase;

    public ComptoirClient(@Value("${comptoir.python.base-url:http://127.0.0.1:8000}") String urlDeBase) {
        this.urlDeBase = urlDeBase;
        this.restClient = RestClient.builder().baseUrl(urlDeBase).build();
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> chercher(RequeteRecherche requete) {
        try {
            return restClient.post()
                    .uri("/api/chercher")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(Map.of("texte", requete.texte(), "rediger", requete.rediger()))
                    .retrieve()
                    .body(Map.class);
        } catch (RestClientException erreur) {
            throw new ServiceComptoirIndisponibleException(
                    "Le service Comptoir (" + urlDeBase + ") est injoignable ou a repondu une erreur : "
                            + erreur.getMessage(),
                    erreur
            );
        }
    }

    public List<Map<String, Object>> exemples() {
        try {
            return restClient.get()
                    .uri("/api/exemples")
                    .retrieve()
                    .body(new ParameterizedTypeReference<List<Map<String, Object>>>() {
                    });
        } catch (RestClientException erreur) {
            throw new ServiceComptoirIndisponibleException(
                    "Le service Comptoir (" + urlDeBase + ") est injoignable ou a repondu une erreur : "
                            + erreur.getMessage(),
                    erreur
            );
        }
    }
}
