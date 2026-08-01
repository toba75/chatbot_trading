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
docker compose `
  --env-file .env.docling-serve `
  --env-file .env.rails `
  -f compose.docling-serve.yaml `
  -f compose.rails.yaml `
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
