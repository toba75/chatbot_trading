# T-006 - Publier EvidenceRef et VerifiedClaimRef

## Milestone
- Nom: M-001 - Frontières DDD et contrats publiés.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrables `EvidenceRef` et `VerifiedClaimRef`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 2, 4, 7, 8, 10, 20 et 21.
- Objectif métier: permettre à RA et SD de consommer des preuves et affirmations vérifiées sans dépendre du modèle interne de EG.

## Contexte DDD
- Domaine: gouvernance des preuves et consommation d'affirmations vérifiées.
- Bounded context: EG producteur; RA et SD consommateurs; SP fournit le `SourceLocator` inclus.
- Objectif métier: conserver preuve directe, portée, version d'affirmation et dépendances dans un langage publié.
- Langage ubiquitaire: span de preuve, preuve directe, affirmation vérifiée, portée, dépendance de source, version de claim, décision de vérification.
- Invariants critiques: une affirmation vérifiée référence au moins une preuve directe; la portée est conservée; les groupes de dépendance ne sont pas perdus; le statut n'est pas inventé par le consommateur.
- Garde-fous: ne pas confondre preuve candidate KA et claim vérifié EG; ne pas accepter `VERIFIED` sans preuve; ne pas masquer les dépendances.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 doit être GREEN; T-005 fournit le contrat documentaire inclus dans `EvidenceRef`.
- Présence des milestones amont dans master: M-000 est présent dans `master`.
- Décisions manquantes: aucune ADR nouvelle si la tâche matérialise DDD-ADR-005 et la séparation EG/KA existante sans changer leur sens.
- Risques: publier un claim sans preuve directe; transformer une preuve candidate en fait vérifié; perdre la portée d'affirmation au passage vers RA ou SD.

## Tâches
### T-006 - Publier EvidenceRef et VerifiedClaimRef
- But métier: rendre les preuves et claims vérifiés consommables par recherche, réponse et stratégie sans couplage au registre interne EG.
- Portée DDD: contrats `EvidenceRef`, `VerifiedClaimRef`, relation de preuve, statut de claim, portée, version de claim et dépendances.
- Scénario BDD:
  - Given EG a vérifié une affirmation avec une preuve directe et une portée explicite.
  - When RA ou SD consomme `VerifiedClaimRef`.
  - Then le consommateur reçoit le claim versionné, ses preuves, sa portée et ses dépendances sans lire l'agrégat interne EG.
- Tests d'acceptation à écrire: un test de contrat EG vers RA et EG vers SD qui accepte une fixture vérifiée complète et refuse une fixture `VERIFIED` sans `evidence_refs`.
- Tests unitaires à écrire: tests de statut autorisé, version de claim obligatoire, portée obligatoire, `EvidenceRef.source_locator` valide et dépendances conservées.
- Implémentation attendue: créer les contrats, fixtures producteur-consommateur et validateurs stricts pour `EvidenceRef` et `VerifiedClaimRef`.
- Invariants et garde-fous: aucune preuve vide; aucun statut par défaut; aucune portée implicite; aucun accès au modèle interne EG depuis RA ou SD.
- Dépendances: T-004; T-005; DDD-ADR-005; sections 4 et 7 de la spécification v4.1.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m001): couvrir les contrats de preuves et claims`.
- Commit GREEN: `feat(m001): publier les contrats evidence et verified claim`.
