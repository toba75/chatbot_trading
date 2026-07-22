# ADR-049 - Qualification complète réservée au profil test

**Statut :** Acceptée
**Date :** 2026-07-23
**Décideurs :** Propriétaire du projet
**Remplace :** Sémantique de qualification des commandes d'ADR-046
**Remplacée par :** Aucune
**Source :** Demande utilisateur du 2026-07-23 ; ADR-046 ; spécification M13-environments

## Contexte

ADR-046 établit trois profils locaux explicites et étanches, mais attribue encore
à `uv run production` une responsabilité de qualification fonctionnelle. La
première campagne M13-environments exécutait ainsi un même parcours PDF réel en
`development`, `test` et `production`.

Cette répétition confond l'environnement ciblé par les tests et les
environnements dans lesquels l'application est utilisée. Elle multiplie le coût
de conversion, introduit des données de qualification dans des autorités de
données persistantes et ne fournit pas une meilleure preuve fonctionnelle : le
même code applicatif est déjà qualifié dans le profil isolé prévu à cet effet.

Les garanties d'étanchéité, de secrets, d'identité et de composition définies
par ADR-046 restent nécessaires pour chacun des trois profils.

## Décision

`uv run test` EST l'unique commande qui DOIT exécuter la qualification
fonctionnelle complète. Elle DOIT démarrer la pile `test`, injecter uniquement la
fixture de qualification versionnée, exercer les cinq routes PDF attendues,
publier son rapport puis détruire les ressources mutables de cette exécution.

`uv run development` et `uv run production` DOIVENT démarrer respectivement une
pile persistante `development` ou `production`, puis la superviser jusqu'à son
arrêt explicite. Ces commandes NE DOIVENT PAS injecter de fixture, créer de
données de qualification ni lancer automatiquement un parcours métier.

La vérification automatisée de `development` et `production` DOIT rester non
mutatrice. Elle PEUT valider statiquement la configuration rendue, l'étanchéité
des ressources, le périmètre des secrets et le contrat de la commande. Pour une
pile effectivement déployée, elle PEUT aussi vérifier la readiness et l'identité
publique sans écrire de données métier.

La gate fonctionnelle réelle DOIT exécuter uniquement le parcours `test`. Une
preuve fonctionnelle obtenue en `test` NE remplace PAS les contrôles de
déploiement propres à la production distante ; ceux-ci restent responsables de
la readiness, de l'identité du profil, des migrations et de la connectivité,
sans corpus de test.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Rejouer la qualification PDF dans les trois profils | Rejetée | Coût triplé, pollution des données persistantes et absence de preuve fonctionnelle supplémentaire. |
| Qualifier uniquement `test` et contrôler `development` et `production` sans mutation | Retenue | Respecte la responsabilité de chaque profil et conserve les garanties d'étanchéité. |
| Ne plus vérifier `development` et `production` | Rejetée | L'étanchéité, la configuration et la readiness doivent toujours être prouvées. |

## Conséquences

### Positives

- La conversion PDF réelle n'est exécutée qu'une fois par campagne.
- Les autorités de données `development` et `production` ne reçoivent aucune
  fixture de qualification automatique.
- Les commandes reflètent une séparation familière : exécution persistante pour
  `development` et `production`, tests isolés et destructibles pour `test`.
- La preuve Granite directe et la récupération Gemma explicite restent couvertes
  par la fixture cinq pages du profil `test`.

### Négatives ou coûts

- Une réussite en `test` ne prouve pas à elle seule qu'une infrastructure de
  production distante est correctement raccordée.
- Les contrôles de déploiement doivent distinguer clairement readiness non
  mutatrice et qualification fonctionnelle.

### Risques et contrôles

- Risque : déployer une configuration `production` invalide malgré des tests
  fonctionnels verts. Contrôle : validation statique, migrations, readiness et
  identité du profil avant exposition.
- Risque : réintroduire une fixture dans une commande persistante. Contrôle :
  tests de contrat interdisant tout appel au qualificateur depuis `development`
  et `production`.
- Risque : perdre la preuve d'un chemin de conversion. Contrôle : manifeste
  versionné des cinq pages et assertion exacte des cinq routes dans le rapport
  `test`.

## Impact d'implémentation

- Modules concernés : `app/platform/environment_command.py`, gouvernance des
  preuves M13 et manifestes de gate.
- Configuration concernée : scripts UV `development`, `test` et `production` ;
  compositions des trois profils inchangées.
- Tests attendus : contrat persistant et non mutateur pour `development` et
  `production`, qualification réelle cinq pages uniquement pour `test`,
  gouvernance live fondée sur les deux cycles `test`.
- Milestones concernées : M-013, M13-environments.

## Liens de traçabilité

- Spécification : `docs/specs/m013_environments_environnements_explicites.md`.
- Plan d'implémentation : section `M13-environments` de
  `docs/specs/plan_implementation_milestones_workstreams.md`.
- Tests d'acceptation :
  `gate_tests/ported/tests/m013_environments/validate_environment_commands_acceptance.py`,
  `validate_test_real_e2e_acceptance.py` et
  `validate_environment_governance_live.py`.
- Commits : cycle RED/GREEN de la correction M13-environments du 2026-07-23.

## Notes

ADR-046 reste applicable à l'étanchéité des données, à l'autorité Docker locale,
à Qdrant, au périmètre des secrets et au socket OCR. La présente ADR remplace
uniquement sa sémantique de qualification des commandes.
