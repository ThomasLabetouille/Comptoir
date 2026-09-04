package fr.comptoir.facade.web;

import com.fasterxml.jackson.databind.ObjectMapper;
import fr.comptoir.facade.dto.RequeteRecherche;
import fr.comptoir.facade.service.ComptoirClient;
import fr.comptoir.facade.service.ServiceComptoirIndisponibleException;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Teste uniquement la couche web : ComptoirClient est simule (@MockBean),
 * donc rien ici n'appelle reellement le service Python. Le meme esprit que
 * tests/test_interface.py cote Python - verifier ce qui peut l'etre sans
 * dependance externe, sans pretendre tester ce qui en a besoin.
 */
@WebMvcTest(ComptoirController.class)
class ComptoirControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private ComptoirClient comptoirClient;

    @Test
    void relaie_une_recherche_valide_vers_le_service_python() throws Exception {
        when(comptoirClient.chercher(any()))
                .thenReturn(Map.of("erreur", "", "propositions", List.of()));

        mockMvc.perform(post("/api/comptoir/chercher")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new RequeteRecherche("on est deux, Crete", false))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.propositions").isArray());
    }

    @Test
    void refuse_une_demande_avec_un_texte_vide_avant_meme_dappeler_le_service() throws Exception {
        mockMvc.perform(post("/api/comptoir/chercher")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new RequeteRecherche("", false))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.erreur").exists());
    }

    @Test
    void traduit_une_panne_du_service_python_en_502_plutot_que_de_planter() throws Exception {
        when(comptoirClient.chercher(any()))
                .thenThrow(new ServiceComptoirIndisponibleException("Le service Comptoir a repondu 500", null));

        mockMvc.perform(post("/api/comptoir/chercher")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new RequeteRecherche("Crete", false))))
                .andExpect(status().isBadGateway())
                .andExpect(jsonPath("$.erreur").exists());
    }

    @Test
    void relaie_les_exemples_du_service_python() throws Exception {
        when(comptoirClient.exemples())
                .thenReturn(List.of(Map.of("id", "q01", "texte", "Bonjour, on part a deux...")));

        mockMvc.perform(get("/api/comptoir/exemples"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].id").value("q01"));
    }
}
