package fr.comptoir.facade.web;

import fr.comptoir.facade.dto.RequeteRecherche;
import fr.comptoir.facade.service.ComptoirClient;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * Meme contrat que interface/serveur.py cote Python (POST /api/chercher,
 * GET /api/exemples), sous /api/comptoir ici pour ne pas se confondre avec
 * le service qu'elle relaie. Aucune logique metier : la validation
 * (@Valid) et la traduction des pannes (voir GestionnaireErreurs) sont
 * tout ce que cette couche ajoute.
 */
@RestController
@RequestMapping("/api/comptoir")
public class ComptoirController {

    private final ComptoirClient client;

    public ComptoirController(ComptoirClient client) {
        this.client = client;
    }

    @PostMapping("/chercher")
    public Map<String, Object> chercher(@Valid @RequestBody RequeteRecherche requete) {
        return client.chercher(requete);
    }

    @GetMapping("/exemples")
    public List<Map<String, Object>> exemples() {
        return client.exemples();
    }
}
