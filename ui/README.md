# Interface de conversion PDF

Application Rails 8.1.3 sur Ruby 4.0.6. Elle convertit toutes les pages avec
Docling Serve Granite CUDA puis qualifie automatiquement les expressions
mathématiques à partir du PDF et du `DoclingDocument`. PostgreSQL stocke le
métier et Solid Queue ; une base séparée de la même instance stocke Solid Cable.
Aucun composant Rails ne s’exécute directement sur Windows.

Les commandes suivantes se lancent depuis la racine du dépôt.

## Configuration initiale

```powershell
Copy-Item .env.rails.example .env.rails
docker compose --env-file .env.rails -f compose.rails.yaml build setup
```

Le fichier `.env.docling-serve` et les actifs Granite qualifiés doivent déjà
être présents selon le README racine.

Les fichiers Active Storage sont montés directement sur l’hôte. Par défaut,
`.env.rails.example` sépare `development` et `test` dans `data/development/active_storage`
et `data/test/active_storage`. Pour `production`, renseigner un fichier
d’environnement dédié avec `RAILS_ENV=production` et un
`RAILS_ACTIVE_STORAGE_HOST_PATH` propre à la production, par exemple
`./data/production/active_storage`.

Si une version précédente a déjà écrit des fichiers dans le volume Docker
`chatbot_trading_rails_storage`, les copier vers le dossier hôte avant le
premier démarrage avec cette configuration :

```powershell
New-Item -ItemType Directory -Force data\development\active_storage | Out-Null
docker run --rm `
  -v chatbot_trading_rails_storage:/from:ro `
  -v "${PWD}\data\development\active_storage:/to" `
  alpine:3.20 sh -c "cp -a /from/. /to/"
```

Adapter le chemin de destination si les fichiers doivent rejoindre un autre
environnement, par exemple `data\production\active_storage`.

## Démarrage

```powershell
docker compose `
  --env-file .env.docling-serve `
  --env-file .env.rails `
  -f compose.docling-serve.yaml `
  -f compose.rails.yaml `
  up -d --no-build docling-serve math-audit web jobs --wait
```

L’interface est alors disponible sur `http://127.0.0.1:3000`. Le service
`setup` prépare explicitement les bases et les schémas avant `web` et `jobs`.
Les files `conversions` et `math_qualifications` ont leurs propres workers.
`DOCLING_SERVERS` déclare la liste ordonnée des serveurs et leur priorité. Un
worker réserve le premier serveur libre dans PostgreSQL : le distant est P1 et
le local P2 dans la configuration fournie. Deux conversions peuvent donc être
traitées simultanément ; les suivantes attendent qu'un retour Docling soit
effectivement reçu. Un échec Rails ou réseau sans retour conserve donc la
capacité occupée. Une erreur sur le serveur réservé n'est pas rejouée sur un autre
serveur.
Chaque job persiste son identifiant de prise en charge. Après un arrêt brutal,
le réconciliateur relie la `FailedExecution` Solid Queue à l’état métier et
rend l’exécution `failed` avec `interrupted_execution`, sans rejouer
silencieusement Docling ou l’analyse mathématique. Sa cadence vient de
`INTERRUPTED_EXECUTION_RECONCILIATION_SCHEDULE`.

## Chaîne de test de l'interface

Cette chaîne utilise un document déjà converti et ne contacte pas Docling.

```powershell
docker compose --env-file .env.rails -f compose.rails.yaml --profile test `
  run --rm test bundle exec rails test test/system/document_interface_test.rb
```

## Chaîne réelle de conversion

Cette commande convertit réellement le PDF de référence. Elle est réservée aux
changements du pool, du client Docling ou du contrat de conversion et ne doit
pas être lancée pour une modification limitée à l'interface.

```powershell
docker compose `
  --env-file .env.docling-serve `
  --env-file .env.rails `
  -f compose.docling-serve.yaml `
  -f compose.rails.yaml `
  -f compose.rails-system-test.yaml `
  --profile test run --rm system-test
```

La pile réelle de test possède son propre serveur Rails et ses propres workers,
en `RAILS_ENV=test`. Elle utilise les bases fixes `ui_system_test` et
`ui_system_test_cable`, ainsi que le volume Docker dédié
`rails_system_test_storage`, quel que soit l'environnement applicatif actif.
Son worker utilise exclusivement le service `docling-serve` de cette pile. Le
lanceur compare avant tout import l'identité HTTP aux ressources réellement
ouvertes par le serveur : environnement Rails, bases primaire et Cable, puis
racine Active Storage.

Les paramètres de capacité, les délais, les noms de bases, la taille maximale
du PDF et les limites du flux et des artefacts de qualification sont tous
déclarés dans `.env.rails` à partir de
`.env.rails.example`. La conversion Docling est limitée à 24 heures ; le délai
HTTP de Rails lui laisse cinq minutes supplémentaires pour publier sa réponse
terminale. L’analyse mathématique possède également une limite de 24 heures et
un délai de réception multipart indépendant.
