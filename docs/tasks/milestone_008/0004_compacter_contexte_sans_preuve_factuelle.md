# T-004 - Compacter le contexte sans preuve factuelle

## Milestone
- Nom: M-008 - Conversation produit.
- Source: spécification M-008, objet-valeur `ConversationContextSnapshot` et politique `ConversationContextCompactionPolicy`.
- Objectif métier: conserver le contexte utile d'une conversation sans transformer l'historique en source documentaire.

## Contexte DDD
- Domaine: conversation produit fondée sur preuves.
- Bounded context: CV.
- Objectif métier: distinguer préférences, concepts, documents sélectionnés, ambiguïtés et résultats vérifiés dans un snapshot compact.
- Langage ubiquitaire: `ConversationContextSnapshot`, contexte utile, mandat actif, préférences utilisateur, documents sélectionnés, ambiguïtés, résultats vérifiés, mémoire conversationnelle, mémoire documentaire.
- Invariants critiques: le snapshot ne recopie pas tous les tours; les préférences utilisateur sont distinctes des faits documentaires; une assertion historique n'est factuelle que si elle référence une `VerifiedAnswerVersion` ou si elle est revalidée.
- Garde-fous: aucun résumé de conversation utilisé comme preuve; aucun texte complet de réponse ou de document dans les métriques; aucune donnée sensible envoyée à un fournisseur distant non autorisé.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-003 terminé.
- Présence des milestones amont dans master: M-007 présent.
- Décisions manquantes: ADR requise si une politique durable de rétention, chiffrement ou purge du snapshot est décidée hors de la spécification.
- Risques: compacter en prompt opaque; perdre les références vers résultats vérifiés; confondre préférence de présentation et contrainte documentaire.

## Tâches
### T-004 - Compacter le contexte sans preuve factuelle
- But métier: rendre la continuité conversationnelle utile sans affaiblir la chaîne de preuve.
- Portée DDD: objet-valeur `ConversationContextSnapshot`, politique de compaction, store de contexte, référence vers résultats vérifiés et distinction explicite entre préférences et faits.
- Scénario BDD:
  - Given une conversation contient une préférence utilisateur et une réponse précédente vérifiée.
  - When le contexte conversationnel est compacté.
  - Then le snapshot conserve la préférence et la référence vérifiée sans recopier l'historique comme preuve factuelle.
- Tests d'acceptation à écrire: `tests/m008/validate_conversation_context_snapshot_acceptance.ps1`, qui échoue tant que le snapshot ne distingue pas préférence, ambiguïté et résultat vérifié.
- Tests unitaires à écrire: tests de marquage d'une assertion historique sans `VerifiedAnswerVersion` comme non factuelle et à revalider par T-007, conservation des documents explicitement sélectionnés, conservation du mandat actif, exclusion de tours bruts, absence de payload sensible et sérialisation stable du snapshot.
- Implémentation attendue: créer `app/conversation/domain/context_snapshot.py`, `app/conversation/application/compact_context.py` et `app/conversation/adapters/in_memory_context_store.py`.
- Invariants et garde-fous: aucune preuve créée par résumé; aucune copie aveugle de l'historique; aucune suppression des ambiguïtés non résolues; aucune dépendance à RA interne; aucune assertion historique sans version vérifiée ne devient utilisable sans revalidation RA.
- Dépendances: T-003; contrat `VerifiedResearchOutcome`; `SourceLocator`; `docs/specs/m007_reponse_documentaire_verifiee.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_conversation_context_snapshot_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_conversation_context_snapshot_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m008): couvrir snapshot contexte sans preuve`
- Commit GREEN: `feat(m008): compacter contexte sans preuve factuelle`
