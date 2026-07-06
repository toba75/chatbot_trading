# T-011 - Vérifier les anti-patterns interdits V1

## Milestone
- Nom: M-013 - Durcissement et acceptation V1.
- Source: section 23 `Anti-patterns interdits et questions ouvertes`, tests M-013 et définition d'achèvement V1.
- Objectif métier: empêcher l'acceptation V1 si le système contient un anti-pattern explicitement interdit par la spécification.

## Contexte DDD
- Domaine: durcissement opérationnel et acceptation V1.
- Bounded context: gouvernance V1 et architecture transverse.
- Objectif métier: transformer les interdictions normatives en contrôles automatisés ou revues documentées.
- Langage ubiquitaire: anti-pattern interdit, revue documentée, contrôle automatisé, violation bloquante, exception refusée, question ouverte contrôlée.
- Invariants critiques: chaque anti-pattern V1 possède un contrôle; les violations sont bloquantes; les questions ouvertes ne sont pas résolues implicitement dans le code; une revue manuelle possède preuve, date et périmètre.
- Garde-fous: pas d'exception implicite; pas de microservice par contexte imposé; pas de Qdrant comme source de vérité; pas de vLLM exposé; pas de checkpoint quantifié sans benchmark; pas de contexte 256K par défaut.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-010.
- Présence des milestones amont dans master: M-012 présent dans `master`.
- Décisions manquantes: ADR requise pour trancher une question ouverte structurante au lieu de la laisser en note de revue.
- Risques: valider seulement les anti-patterns faciles à scanner; oublier les questions ouvertes; accepter une revue sans preuve; dupliquer des contrôles déjà couverts sans les relier.

## Tâches
### T-011 - Vérifier les anti-patterns interdits V1
- But métier: garantir que la V1 ne passe pas l'acceptation avec une décision explicitement rejetée.
- Portée DDD: anti-patterns de domaine, architecture, sécurité, LLM, conversation, stratégie, backtest, persistance, exposition réseau, logs et décisions ouvertes.
- Scénario BDD:
  - Given la spécification V1 liste des anti-patterns interdits et des questions ouvertes contrôlées.
  - When la validation M-013 des anti-patterns s'exécute.
  - Then chaque interdiction possède un contrôle automatisé ou une revue documentée, et toute violation bloque l'acceptation V1.
- Tests d'acceptation à écrire: `tests/m013/validate_v1_antipatterns_acceptance.ps1`, qui échoue si un anti-pattern interdit n'a pas de contrôle, si une violation est présente, si une question ouverte est résolue sans ADR, si un checkpoint quantifié est promu sans benchmark ou si vLLM est exposé à tout le LAN.
- Tests unitaires à écrire: tests de `scripts/validate_m013_antipatterns.ps1` pour anti-pattern absent, contrôle absent, revue sans date, question ouverte sans statut, violation réseau, fallback LLM, Qdrant source de vérité, historique conversationnel factuel, résultat négatif supprimé et prompt complet persistant.
- Implémentation attendue: créer `scripts/validate_m013_antipatterns.ps1`, publier `docs/governance/m013_antipattern_review.md`, relier les contrôles existants et nouveaux, compléter les revues documentées nécessaires et enrôler la validation dans `scripts/lint.ps1`.
- Invariants et garde-fous: aucune interdiction sans contrôle; aucune violation non bloquante; aucune question ouverte tranchée implicitement; aucune revue sans preuve; aucun contrôle dupliqué sans lien de traçabilité.
- Dépendances: T-010; section 23 de la spécification; ADR index; validateurs d'architecture, réseau, traceabilité et ADR.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_antipatterns_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_antipatterns_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_antipatterns.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_network_boundary.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m013): couvrir antipatterns v1`
- Commit GREEN: `chore(m013): verifier antipatterns v1`
