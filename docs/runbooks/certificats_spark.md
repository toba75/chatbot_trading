# Runbook certificats Spark M-013

## Statut

- Identifiant: `M013-Runbook-SparkCertificates-1.0`
- Tâche: `docs/tasks/milestone_013/0010_publier_runbooks_documentation_utilisateur.md`
- Preuve source: `docs/governance/m013_security_audit.md`
- ADR applicables: ADR-007, ADR-008, ADR-009, ADR-010, ADR-014, ADR-016.
- ADR: ADR-014 et ADR-046; le Spark actuel fonctionne avec `services.llm_gateway.tls_mode=disabled` dans `config/environments/<profil>.yaml`, et ce runbook décrit le contrôle à appliquer si une terminaison HTTPS avec CA explicite est ajoutée.

## Scénario BDD

- Given Spark reste accessible uniquement par `llm-gateway -> spark-inference`.
- When un certificat TLS est validé, renouvelé ou refusé pour un futur mode `services.llm_gateway.tls_mode=ca_bundle`.
- Then l'état public nomme la validation de certificat, la rotation certificat et l'erreur explicite sans publier de clé privée.

## Validation de certificat

- Précondition: une terminaison HTTPS Spark a été décidée explicitement, la rotation certificat est préparée hors dépôt et aucune clé privée ou passphrase n'est écrite dans Git.
- Point de configuration: le chemin `security.secrets.tls_ca_certificate_path` désigne un certificat public local, et le secret hors Git associé reste monté en lecture seule quand un mode futur l'exige.
- Commande vérifiée:

```console
uv run --locked gate
```

- Résultat attendu: `llm-gateway -> spark-inference` reste le seul chemin autorisé; en mode actuel `disabled`, aucun CA n'est exigé; en mode futur `ca_bundle`, tout accès direct Spark depuis navigateur reste interdit.
- Erreur explicite: `LLM_TLS_CERTIFICATE_INVALID` bloque l'appel LLM sans réponse factuelle et sans fallback silencieux.
- Preuve à conserver: sortie du validateur, `docs/governance/m013_security_audit.md` et statut public associé.

## Rotation certificat

- Précondition: le nouveau certificat est installé localement sur le plan Spark avant exposition au gateway et `services.llm_gateway.tls_mode=ca_bundle` est déclaré explicitement dans `config/environments/<profil>.yaml`.
- Commande vérifiée:

```console
uv run --locked gate
```

- Résultat attendu: le gateway conserve la frontière `spark-inference`, le mode TLS déclaré dans `config/environments/<profil>.yaml`, le chemin `security.secrets.tls_ca_certificate_path` et l'authentification explicite; aucun service interne n'est publié.
- Erreur explicite: `LLM_AUTHENTICATION_FAILED` ou `LLM_TLS_CERTIFICATE_INVALID` reste visible tant que la rotation n'est pas validée.
- Preuve à conserver: sortie du validateur réseau, horodatage local de rotation et absence de secret dans les logs.

## Garde-fous

- Aucun certificat privé, token bearer, passphrase ou clé API dans la documentation.
- Aucun endpoint public Spark.
- Aucune réponse factuelle n'est produite si TLS ou authentification échoue dans un mode qui les active explicitement.
