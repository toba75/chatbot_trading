# T-010 - Prouver le parcours réel en test

## Milestone

- Nom: M13-environments - Environnements explicites et données étanches.
- Source: chaîne complète T-003 à T-009.
- Objectif métier: exécuter un parcours reproductible et jetable sans droit d'accès aux données development ou production.

## Contexte DDD

- Domaine: qualification automatisée du produit.
- Bounded context: transverse, mêmes contrats réels que le produit.
- Objectif métier: faire de `uv run test` une preuve réelle, isolée et nettoyable du comportement livré.
- Langage ubiquitaire: fixture PDF réelle, installation test, état initial déterministe, nettoyage borné, preuve d'étanchéité.
- Invariants critiques: credentials et ressources test uniquement; aucune ressource non-test montée; nettoyage même après échec, borné par identité.
- Garde-fous: aucun SQLite, Qdrant mémoire, worker inline, faux gateway ou bypass de l'outbox.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-001 à T-009 GREEN.
- Présence des milestones amont dans master: M-000 à M-012 visibles.
- Décisions manquantes: aucune.
- Risques: une suite GREEN utilisant des doubles au lieu de la topologie réelle, ou un teardown trop large.

## Tâches

### T-010 - Prouver le parcours réel en test

- But métier: permettre une qualification automatisée complète qui ne connaît aucune credential de production.
- Portée DDD: cycle `create -> migrate -> run -> assert -> teardown` de la pile test et parcours documentaire complet.
- Scénario BDD:
  - Given les ressources test sont créées à partir d'un état déterministe et aucun secret development/production n'est accessible.
  - When `uv run test` exécute le parcours PDF réel jusqu'à la réponse vérifiée puis termine.
  - Then le résultat est GREEN, les identifiants test sont invisibles ailleurs et seules les ressources portant l'identité test sont supprimées, y compris après un RED.
- Tests d'acceptation à écrire: E2E réel test, reproductibilité de deux exécutions, absence de credentials non-test, teardown après succès/échec et sentinelles development/production préservées.
- Tests unitaires à écrire: état machine du lanceur test, cleanup idempotent borné, propagation du code RED, refus d'une cible non-test.
- Implémentation attendue: faire de l'entrypoint `test` le superviseur de la pile et de la gate test; utiliser PostgreSQL, Qdrant, workers, fichiers et gateway réels; produire un rapport avant teardown.
- Invariants et garde-fous: aucun test destructif hors profil test; aucune réutilisation de volume; aucune validation remplacée par un mock; aucun RED converti en GREEN pendant le nettoyage.
- Dépendances: T-008 et T-009; corpus réel de test; infrastructure Spark déclarée pour test.
- Commandes de validation: `uv run test`; exécution répétée; tests de sentinelles croisées; `uv run --locked gate`.
- Commit RED: `test(m13-environments): couvrir parcours reel test`.
- Commit GREEN: `feat(m13-environments): isoler et executer le profil test`.

## Preuve GREEN livrée

- Commande opérateur : `uv run test`, code `0`, durée `8093,1 s`.
- PDF source réel : `data/corpus/the-original-turtle-trading-rules.pdf`, 38
  pages, SHA-256
  `073f361ebb4ac6c10765a21ba7cca42d75fde8fabadc84340e6bbfca444fbda4`.
- Rapport agrégé sans secret :
  `data/environments/test/reports/test-e2e-20260722T012720Z.json`.
- Cycle 1 : document `DOC-EE140CC90ADADCD5`, version canonique
  `CVER-M004-ROUTED-EE140CC90ADADCD5E089C53A`, projection
  `PROJ-69572CA6B4F68FBC3E724EB9C7524A6DA9D511473243E46C2114B23EB321D885`,
  réponse `ANS-LIVE-DC524D9BD92D465A3C99`, citation PDF page 36 et réponse
  Spark brute `chatcmpl-REQ-TEST-E2E-SPARK-AEEEFD757965494FAB67B2254CFE3ADA`.
- Cycle 2 : document `DOC-D20D052ED84E8A50`, version canonique
  `CVER-M004-ROUTED-D20D052ED84E8A50B3F6602B`, projection
  `PROJ-CFB61CBF72B7CEF429E013DA159FAF60FE4712CF5C2B8076A9CA0A551BBD39A9`,
  réponse `ANS-LIVE-35657C78A8CCA1AD211F`, citation PDF page 36 et réponse
  Spark brute `chatcmpl-REQ-TEST-E2E-SPARK-1FE3E742F824496F8F541A3C0EDE7422`.
- Les deux cycles publient `SUCCEEDED` pour diagnostic, conversion et
  projection, vérifient quatre conteneurs workers et trois jobs portant
  l'identité `test` / `ostrading-test-ci`.
- Chaque rapport de cycle est écrit avant son teardown contrôlé. Après chaque
  préflight PostgreSQL, Qdrant et fichiers, seuls les conteneurs, réseaux et
  volumes `ostrading-test-*` sont supprimés.
- État final : zéro conteneur, réseau ou volume `ostrading-test-*`; sentinelles
  development et production inchangées; aucun chemin de configuration, secret
  ou donnée non-test visible dans le rendu ni dans les 14 conteneurs inspectés.
- Ressources : Docker dispose d'environ 31 Gio et chaque worker documentaire
  conserve exactement 8 Gio, 4 CPU et un healthcheck de 30 secondes.
