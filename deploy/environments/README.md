# Piles d'environnement M13-environments

Les trois commandes opérateur sont les seules interfaces de sélection:

```console
uv run development
uv run test
uv run production
```

Chaque commande sélectionne un overlay fermé et attend la readiness agrégée.
`development` reste attaché jusqu'à `Ctrl+C`; `test` exécute deux cycles puis
supprime ses seuls volumes après préflight; `production` exécute une qualification
finie et arrête ses conteneurs sans supprimer ses volumes.

| Profil | Projet Compose | Entrée HTTPS locale | Configuration |
|---|---|---:|---|
| `development` | `ostrading-development` | `https://localhost:18443` | `config/environments/development.yaml` |
| `test` | `ostrading-test` | `https://localhost:19443` | `config/environments/test.yaml` |
| `production` | `ostrading-production` | `https://localhost:20443` | `config/environments/production.yaml` |

La base commune est `deploy/environments/compose.base.yaml`. Les overlays ne
sélectionnent jamais un profil par variable: ils fixent le projet, les DNS, les
ports, les réseaux, les volumes, le fichier applicatif et les secrets requis par
chaque service. Les seules variables techniques consommées par Compose servent à
étiqueter l'image avec la révision Git et la version du schéma PostgreSQL; le
lanceur les calcule et les injecte lui-même.

## Secrets locaux hors Git

Avant le démarrage, l'opérateur fournit les fichiers dans :

- `config/secrets/development/`;
- `config/secrets/test/`;
- `config/secrets/production/`.

Ces trois répertoires sont ignorés par Git. Le lanceur ne crée ni répertoire ni
valeur. Compose monte chaque fichier en lecture seule uniquement dans son
consommateur : mot de passe PostgreSQL, clé Qdrant ou token API local. Leur
contenu ne doit jamais être copié dans un rapport, un log ou un fichier
versionné. Un secret absent, illisible ou trop court provoque un échec terminal.

## Isolation et readiness

Chaque projet possède ses réseaux et ses volumes nommés. Aucun volume mutable
n'est partagé. Les conteneurs PostgreSQL, Qdrant, API, UI, gateway, les deux
workers documentaires, les deux workers de projection et les services de
traitement doivent tous être `running` et `healthy` avant la publication de
`ready`. Les actions recherche approfondie et backtest restent indisponibles
tant que leur chaîne asynchrone réelle n'est pas livrée.

Chaque pile possède aussi un moteur Docker interne `ocr-runtime`, son socket Unix
et ses volumes propres. Il précharge l'image OCRmyPDF exclusivement par digest
avant de devenir sain. Il n'écoute pas sur TCP 2375 et le socket Docker hôte
n'est jamais monté : un
worker documents ne peut donc pas inspecter les conteneurs ni les volumes des
deux autres profils. Les actifs Docling préchargés et scellés sous
`data/docling_assets/` sont des ressources techniques immuables; ils sont
partagés uniquement en lecture seule, tandis que les originaux, artefacts,
audits et marqueurs restent dans le volume applicatif propre au profil.

Les trois gateways appellent le service d'inférence Spark stateless réel
`http://192.168.1.120:8000/v1`, conformément à ADR-014. Son indisponibilité fait
échouer la readiness du gateway et donc le démarrage de la pile; aucun modèle ou
endpoint alternatif n'est utilisé.

Qdrant exige la clé API propre au profil sur chaque appel d'identité, de
readiness, d'écriture et de recherche. Un même daemon Docker local peut héberger
les trois qualifications conformément à ADR-046, mais les autorités de données
restent distinctes. Le profil local `production` ne certifie pas un hébergement
physique dédié.

L'arrêt standard ne passe jamais `--volumes`. Toute suppression de volume reste
une opération destructive distincte, hors de ces commandes.
