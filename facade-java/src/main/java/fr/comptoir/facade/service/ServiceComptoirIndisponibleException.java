package fr.comptoir.facade.service;

/**
 * Le service Python n'a pas repondu, ou a repondu une erreur. Une exception
 * dediee plutot que de laisser fuiter l'exception Spring d'origine : le
 * controleur (voir web/GestionnaireErreurs) n'a besoin de connaitre que
 * celle-ci pour savoir quel statut HTTP renvoyer au client de la facade.
 */
public class ServiceComptoirIndisponibleException extends RuntimeException {

    public ServiceComptoirIndisponibleException(String message, Throwable cause) {
        super(message, cause);
    }
}
