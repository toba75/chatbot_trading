# ADR-050 - Séparer qualification fonctionnelle et qualification d’isolation

**Statut :** Acceptée
**Date :** 2026-07-23
**Décideurs :** Propriétaire du projet
**Remplace :** ADR-049
**Remplacée par :** Aucune
**Source :** Demande utilisateur du 2026-07-23 ; mesure réelle de `uv run test` ; ADR-049

## Contexte

ADR-049 réserve correctement la qualification fonctionnelle au profil `test`,
mais impose deux parcours réels successifs à chaque invocation de
`uv run test`. Le premier parcours prouve déjà les cinq routes PDF, les workers,
la progression publique, la projection, la réponse documentaire, le Spark réel
et le teardown borné. Le second parcours n’ajoute pas une nouvelle preuve
fonctionnelle : il prouve que le teardown est complet et que le résultat ne
dépend d’aucune donnée du parcours précédent.

La campagne réelle sur la fixture de cinq pages dure environ onze minutes par
parcours. Imposer systématiquement la preuve d’isolation double donc le temps de
retour du développeur alors que cette garantie renforcée est surtout nécessaire
avant intégration ou livraison.

## Décision

`uv run test` DOIT exécuter exactement un parcours fonctionnel réel et complet
dans le profil `test`. Il DOIT exercer les cinq routes PDF, écrire une preuve
identifiée comme `FUNCTIONAL`, puis supprimer ses seules ressources mutables
après les préflights d’identité.

`uv run test-isolation` DOIT exécuter exactement deux parcours réels successifs
dans le profil `test`. Chaque parcours DOIT partir d’une pile vide. Son rapport
DOIT être identifié comme `ISOLATION`, contenir deux documents distincts et
prouver que les sentinelles étrangères sont inchangées après les deux teardowns.

Les deux commandes partagent le même verrou interprocessus et NE DOIVENT PAS
s’exécuter simultanément. Le mode de qualification NE DOIT PAS provenir d’un
argument optionnel, d’une variable d’environnement ou d’une valeur par défaut :
il est fixé par le point d’entrée UV invoqué.

La gate live de gouvernance DOIT consommer exclusivement un rapport
`ISOLATION`. Un rapport `FUNCTIONAL` récent NE DOIT PAS masquer ni remplacer la
preuve renforcée à deux cycles.

`uv run development` et `uv run production` conservent la sémantique persistante
et non mutatrice établie par ADR-049.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Conserver deux cycles dans `uv run test` | Rejetée | Double le délai de retour pour une preuve d’isolation inutile à chaque itération. |
| Réduire toutes les qualifications à un cycle | Rejetée | Supprime la preuve de teardown complet et de reproductibilité sans état antérieur. |
| Séparer `test` et `test-isolation` | Retenue | Rend le coût explicite et conserve les deux niveaux de preuve sans fallback. |

## Conséquences

### Positives

- Le parcours courant est environ deux fois plus rapide.
- La preuve fonctionnelle et la preuve d’isolation ont des contrats et des
  rapports non ambigus.
- La gate live conserve la vérification renforcée avant intégration ou release.

### Négatives ou coûts

- Deux commandes et deux familles de rapports doivent être documentées.
- Une campagne `test-isolation` reste coûteuse et reconstruit deux piles réelles.

### Risques et contrôles

- Risque : présenter un rapport à un cycle comme preuve d’isolation. Contrôle :
  discriminant obligatoire et validation stricte du nombre de cycles.
- Risque : lancer les deux commandes en parallèle. Contrôle : verrou partagé et
  erreur terminale `TEST_E2E_ALREADY_RUNNING`.
- Risque : ne plus exécuter l’isolation. Contrôle : gate live et procédure de
  release fondées exclusivement sur `test-isolation`.

## Impact d’implémentation

- Modules concernés : `app/platform/environment_command.py`,
  `app/platform/test_e2e.py` et `ost_gate/environment_governance.py`.
- Configuration concernée : nouveau script UV `test-isolation` ; compositions
  Docker et configurations d’environnement inchangées.
- Tests attendus : contrats unitaires un/deux cycles, entrypoints UV distincts,
  rapport typé et refus d’une preuve fonctionnelle par la gouvernance live.
- Milestones concernées : M-013, M13-environments.

## Liens de traçabilité

- Spécification : `docs/specs/m013_environments_environnements_explicites.md`.
- Plan d’implémentation : section M13-environments de
  `docs/specs/plan_implementation_milestones_workstreams.md`.
- Tests d’acceptation : `validate_environment_commands_acceptance.py`,
  `validate_test_real_e2e_acceptance.py` et
  `validate_environment_governance_live.py`.
- Commits : cycles RED/GREEN du présent changement.

## Notes

ADR-046 reste applicable à l’étanchéité physique. ADR-050 conserve la décision
d’ADR-049 de qualifier uniquement le profil `test`, mais remplace sa fréquence
d’exécution et la forme de la preuve live.
