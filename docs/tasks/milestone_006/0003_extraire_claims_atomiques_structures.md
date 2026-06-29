# T-003 - Extraire des claims atomiques structurés

## Milestone
- Nom: M-006 - Claims vérifiables.
- Source: spécification M-006 à publier et spécification v4.1, section EG `Claim`, phase `Registre d'affirmations et de preuves`.
- Objectif métier: transformer des passages argumentatifs en propositions atomiques sans les vérifier automatiquement.

## Contexte DDD
- Domaine: gouvernance des preuves.
- Bounded context: EG.
- Objectif métier: capturer des claims candidats qui conservent modalité, négation, conditions, limites et span de preuve.
- Langage ubiquitaire: `DraftClaim`, `ClaimDrafted`, `CanonicalProposition`, `ClaimAtomicityPolicy`, `ClaimCanonicalizationPolicy`, `ClaimExtractor`, preuve candidate.
- Invariants critiques: une affirmation doit être atomique; la canonicalisation ne supprime ni négation ni modalité; la sortie LLM reste une proposition.
- Garde-fous: aucun auto-approval par extracteur; aucun claim créé sans span source; aucune décontextualisation qui perd une condition métier.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 et T-002 attendues GREEN.
- Présence des milestones amont dans master: M-004 et M-005 requis et présents.
- Décisions manquantes: aucune si l'extraction applique le port `ClaimExtractor`; ADR requise si un fournisseur LLM externe devient autorisé.
- Risques: claim trop large; proposition non normalisée; usage du texte conversationnel comme source.

## Tâches
### T-003 - Extraire des claims atomiques structurés
- But métier: créer des brouillons de claims auditables à partir de preuves candidates, sans les considérer comme vrais.
- Portée DDD: value objects `CanonicalProposition`, `ClaimScope`, `ClaimCondition`, `Limitation`, politique d'atomicité, handler `ExtractClaimsFromEvidenceHandler` et événement `ClaimDrafted`.
- Scénario BDD:
  - Given un passage source publié contient deux conclusions et une limitation explicite.
  - When EG extrait les claims candidats.
  - Then deux claims `DRAFT` atomiques sont créés avec leur portée, leur limitation et leur span de preuve sans statut `VERIFIED`.
- Tests d'acceptation à écrire: `tests/m006/validate_claim_extraction_acceptance.ps1`, couvrant extraction atomique, conservation des conditions et absence de vérification automatique.
- Tests unitaires à écrire: tests de `ClaimAtomicityPolicy`, `ClaimCanonicalizationPolicy`, parsing de sortie structurée, refus de champ absent, refus de claim vide et conservation de négation/modalité.
- Implémentation attendue: créer les objets de domaine EG nécessaires, le port `ClaimExtractor`, un double déterministe de test, le handler d'extraction et le repository de brouillons sans persistance structurante.
- Invariants et garde-fous: pas de valeur par défaut pour le type de claim; pas de correction silencieuse des champs manquants; pas de `try/catch` masquant une sortie LLM invalide.
- Dépendances: T-002; `app/contracts/evidence_claims.py`; `app/knowledge_access/application/search_knowledge.py`; ADR-006; DDD-ADR-005; DDD-ADR-007.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_claim_extraction_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_claim_extraction_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m006): couvrir extraction claims atomiques`
- Commit GREEN: `feat(m006): extraire claims atomiques structures`
