# Interface de conversion PDF

Application Rails 8.1.3 sur Ruby 4.0.6. Elle convertit toutes les pages avec
Docling Serve Granite puis qualifie automatiquement les expressions
mathématiques à partir du PDF et du `DoclingDocument`. PostgreSQL stocke le
métier et Solid Queue ; une base séparée de la même instance stocke Solid Cable.
Aucun composant Rails ne s’exécute directement sur Windows.

Les commandes suivantes se lancent depuis la racine du dépôt.

## Configuration initiale

```powershell
Copy-Item .env.rails.example .env.rails
docker compose --env-file .env.rails -f compose.rails.yaml build setup
```

Le LaunchAgent Docling Serve Metal/MPS et ses actifs Granite qualifiés doivent
déjà être présents selon le README racine. Dans Colima,
`DOCLING_SERVE_URL=http://host.docker.internal:5001` conserve exactement le
même contrat HTTP que le service CUDA.

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
docker compose --env-file .env.rails -f compose.rails.yaml `
  up -d --no-build math-audit web jobs --wait
```

L’interface est alors disponible sur `http://127.0.0.1:3000`. Le service
`setup` prépare explicitement les bases et les schémas avant `web` et `jobs`.
Les files `conversions` et `math_qualifications` ont leurs propres workers.
Chaque job persiste son identifiant de prise en charge. Après un arrêt brutal,
le réconciliateur relie la `FailedExecution` Solid Queue à l’état métier et
rend l’exécution `failed` avec `interrupted_execution`, sans rejouer
silencieusement Docling ou l’analyse mathématique. Sa cadence vient de
`INTERRUPTED_EXECUTION_RECONCILIATION_SCHEDULE`.

## Tests rapides

```powershell
docker compose --env-file .env.rails -f compose.rails.yaml --profile test `
  run --rm test bundle exec rails test
```

## Qualification réelle

Cette commande convertit réellement le PDF de référence ; elle n’est pas un
test rapide et ne doit pas être relancée après chaque modification locale.

```powershell
docker compose --env-file .env.rails -f compose.rails.yaml `
  --profile test run --rm test `
  bundle exec rails test:system test/system/pdf_conversion_test.rb
```

Les paramètres de capacité, les délais, les noms de bases, la taille maximale
du PDF et les limites du flux et des artefacts de qualification sont tous
déclarés dans `.env.rails` à partir de
`.env.rails.example`. La conversion Docling est limitée à 24 heures ; le délai
HTTP de Rails lui laisse cinq minutes supplémentaires pour publier sa réponse
terminale. L’analyse mathématique possède également une limite de 24 heures et
un délai de réception multipart indépendant.
