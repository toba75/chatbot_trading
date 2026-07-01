# T-002 - Publier la spécification de conversation produit

## Milestone
- Nom: M-008 - Conversation produit.
- Source: plan M-008 et spécification v4.1, section CV, conversation orchestrée, API, sécurité, observabilité, tests et critères V1.
- Objectif métier: publier le contrat exécutable du bounded context CV avant d'implémenter la continuité conversationnelle.

## Contexte DDD
- Domaine: conversation produit fondée sur preuves.
- Bounded context: CV.
- Objectif métier: définir comment CV conserve la continuité du dialogue, résout les références, route les modes, revalide les assertions historiques réutilisées et présente les résultats vérifiés sans posséder de vérité documentaire.
- Langage ubiquitaire: `Conversation`, `ConversationTurn`, `ConversationContextSnapshot`, question résolue, `ConversationModeRoutingPolicy`, `ReferenceResolutionPolicy`, `VerifiedResultReusePolicy`, `ConversationRetentionPolicy`, tour append-only.
- Invariants critiques: l'historique conversationnel n'est jamais une preuve autonome; une question de suivi est résolue avant RA, SD ou EX; le mode sélectionné et sa justification sont enregistrés; l'archivage ne supprime pas les connaissances déclenchées.
- Garde-fous: aucune copie aveugle de l'historique dans un prompt; aucun fallback de mode; aucune décision documentaire prise par CV; aucune exposition de stockage RA, KA, EG ou SP dans le contrat public.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 doit rétablir les gates avant la spécification exécutable.
- Présence des milestones amont dans master: M-007 requis et présent.
- Décisions manquantes: aucune si M-008 applique la spécification v4.1 et les ADR existantes; ADR requise si la compatibilité `/v1/chat/completions`, la rétention conversationnelle ou la politique de réutilisation de réponses vérifiées change de sens.
- Risques: spécification centrée sur le client HTTP; confusion entre mémoire conversationnelle et preuve documentaire; mode de traitement implicite; ajout implicite de citations dans le contrat publié `VerifiedResearchOutcome`.

## Tâches
### T-002 - Publier la spécification de conversation produit
- But métier: rendre M-008 implémentable par comportements CV vérifiables.
- Portée DDD: mission CV, agrégats `Conversation` et `ConversationTurn`, objet-valeur `ConversationContextSnapshot`, politiques, commandes, événements, ports, endpoints, erreurs publiques, métriques, exclusions M-009 à M-011, contrat d'intégration RA côté CV et ADR applicables.
- Scénario BDD:
  - Given la mission M-008 est de permettre une conversation suivie sans preuve historique implicite.
  - When la spécification de conversation produit est publiée.
  - Then chaque comportement CV nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
- Tests d'acceptation à écrire: `tests/m008/validate_m008_specification_acceptance.ps1`, qui échoue tant que `docs/specs/m008_conversation_produit.md` et son validateur n'existent pas.
- Tests unitaires à écrire: tests de `scripts/validate_m008_specification.ps1` pour mission absente, agrégat absent, objet-valeur absent, mode absent, endpoint absent, erreur publique absente, ADR absente, confusion historique-preuve, fallback de mode, revalidation RA absente pour assertion historique sans `VerifiedAnswerVersion` et confusion entre `VerifiedResearchOutcome` et le DTO public RA contenant texte et citations.
- Implémentation attendue: créer `docs/specs/m008_conversation_produit.md`, créer `scripts/validate_m008_specification.ps1`, enrôler la validation dans `scripts/test.ps1` et `scripts/lint.ps1`, puis relier les exigences M-008 à `docs/traceability/matrix.md`.
- Invariants et garde-fous: aucune décision structurante implicite; aucune valeur par défaut de mode non déclarée; aucun prompt ni résumé interne publié comme source de vérité; aucune mutation d'agrégat RA depuis CV; aucune extension silencieuse du contrat `VerifiedResearchOutcome`.
- Dépendances: T-001; ADR-010; DDD-ADR-001; DDD-ADR-002; DDD-ADR-003; DDD-ADR-007; DDD-ADR-008; `docs/tasks/README.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_m008_specification_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m008_specification.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m008): couvrir la specification conversation produit`
- Commit GREEN: `docs(m008): publier la specification conversation produit`
