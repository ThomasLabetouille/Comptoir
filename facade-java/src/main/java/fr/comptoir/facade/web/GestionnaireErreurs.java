package fr.comptoir.facade.web;

import fr.comptoir.facade.service.ServiceComptoirIndisponibleException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Deux facons de rater une requete, deux reponses propres plutot qu'une
 * trace Java brute renvoyee au client : une demande mal formee (400) et un
 * service Python injoignable ou en erreur (502 - Bad Gateway, le code fait
 * pour "je n'ai pas pu joindre le service en amont").
 */
@RestControllerAdvice
public class GestionnaireErreurs {

    @ExceptionHandler(ServiceComptoirIndisponibleException.class)
    public ResponseEntity<Map<String, Object>> serviceIndisponible(ServiceComptoirIndisponibleException erreur) {
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(corpsErreur(erreur.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> requeteInvalide(MethodArgumentNotValidException erreur) {
        String message = erreur.getBindingResult().getFieldErrors().stream()
                .findFirst()
                .map(f -> f.getField() + " : " + f.getDefaultMessage())
                .orElse("requete invalide");
        return ResponseEntity.badRequest().body(corpsErreur(message));
    }

    private static Map<String, Object> corpsErreur(String message) {
        Map<String, Object> corps = new LinkedHashMap<>();
        corps.put("erreur", message);
        return corps;
    }
}
