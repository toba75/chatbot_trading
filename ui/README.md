# Interface de conversion PDF

Application Rails 8.1.3 sur Ruby 4.0.6. Elle dépose un PDF, confie toutes ses
pages à Docling Serve Granite CUDA via Solid Queue, puis compare le PDF à
l’HTML Docling. Une relance ajoute une tentative au même document sans écraser
les sorties précédentes. PostgreSQL stocke le métier, Solid Queue et, dans une base
séparée de la même instance, Solid Cable. Aucun composant Rails ne s’exécute sur
Windows.

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
  up -d --no-build docling-serve web jobs --wait
```

L’interface est alors disponible sur `http://127.0.0.1:3000`. Le service
`setup` prépare explicitement les bases et les schémas avant `web` et `jobs`.

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

Les paramètres de capacité, les délais, les noms de bases et la taille maximale
du PDF sont tous déclarés dans `.env.rails` à partir de
`.env.rails.example`. La conversion Docling est limitée à 24 heures ; le délai
HTTP de Rails lui laisse cinq minutes supplémentaires pour publier sa réponse
terminale.
