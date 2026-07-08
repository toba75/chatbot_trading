# Runbook certificats Spark M-013

## Statut

- Identifiant: `M013-Runbook-SparkCertificates-1.0`
- Tâche: `docs/tasks/milestone_013/0010_publier_runbooks_documentation_utilisateur.md`
- Preuve source: `docs/governance/m013_security_audit.md`
- ADR applicables: ADR-007, ADR-008, ADR-009, ADR-010.
- ADR: non requise; ce runbook applique la frontière réseau et TLS existante sans changer la topologie.

## Scénario BDD

- Given Spark reste accessible uniquement par `llm-gateway -> spark-inference`.
- When un certificat TLS est validé, renouvelé ou refusé.
- Then l'état public nomme la validation de certificat, la rotation certificat et l'erreur explicite sans publier de clé privée.

## Validation de certificat

- Précondition: la rotation certificat est préparée hors dépôt; aucune clé privée ou passphrase n'est écrite dans Git.
- Commande vérifiée:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_security.ps1
```

- Résultat attendu: `llm-gateway -> spark-inference` reste le seul chemin autorisé, TLS est requis et tout accès direct Spark depuis navigateur reste interdit.
- Erreur explicite: `LLM_TLS_CERTIFICATE_INVALID` bloque l'appel LLM sans réponse factuelle et sans fallback silencieux.
- Preuve à conserver: sortie du validateur, `docs/governance/m013_security_audit.md` et statut public associé.

## Rotation certificat

- Précondition: le nouveau certificat est installé localement sur le plan Spark avant exposition au gateway.
- Commande vérifiée:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_network_boundary.ps1
```

- Résultat attendu: le gateway conserve TLS, authentification et frontière `spark-inference`; aucun service interne n'est publié.
- Erreur explicite: `LLM_AUTHENTICATION_FAILED` ou `LLM_TLS_CERTIFICATE_INVALID` reste visible tant que la rotation n'est pas validée.
- Preuve à conserver: sortie du validateur réseau, horodatage local de rotation et absence de secret dans les logs.

## Garde-fous

- Aucun certificat privé, token bearer, passphrase ou clé API dans la documentation.
- Aucun endpoint public Spark.
- Aucune réponse factuelle n'est produite si TLS ou authentification échoue.
