# Docling Serve natif sur Metal/MPS

Ce projet isolé exécute `docling-serve 1.28.0` nativement sur Apple Silicon.
`DOCLING_DEVICE=mps` fait sélectionner au preset `granite_docling` son moteur
MLX et l’export officiel `ibm-granite/granite-docling-258M-mlx`. MLX exécute
l’inférence sur Metal ; le lanceur vérifie aussi un calcul PyTorch sur `mps:0`
avant chaque démarrage.

Le service conserve l’API officielle, notamment `POST /v1/convert/file`. Il
n’active aucune clé API et écoute sur `0.0.0.0:5001`. Il est donc réservé à un
LAN de confiance.

## Installation

Depuis la racine du dépôt :

```bash
uv sync --project services/docling-serve-mps --frozen
git lfs pull \
  --include=reference/ostrading-environment-qualification-5-pages.pdf \
  --exclude=
services/docling-serve-mps/.venv/bin/hf download \
  ibm-granite/granite-docling-258M-mlx \
  --revision e9939db25d2f296c8678d0491c4609a8c596c50a \
  --local-dir data/docling_assets/ibm-granite--granite-docling-258M-mlx
services/docling-serve-mps/.venv/bin/docling-serve-mps install \
  --repo-root "$PWD"
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/ch.chatbot-trading.docling-serve.plist"
```

Le LaunchAgent démarre avec la session utilisateur et redémarre s’il tombe.
Ses journaux sont dans `~/Library/Logs/chatbot-trading/`. Le modèle est chargé
hors ligne depuis `data/docling_assets` et ses quinze empreintes sont vérifiées
avant l’ouverture du serveur.

## Accès

Sur le Mac, l’URL est `http://127.0.0.1:5001`. Depuis le LAN, utiliser
`http://<nom-mDNS-du-Mac>.local:5001` ou l’adresse IPv4 du Mac. Depuis un
conteneur Colima du même Mac, utiliser `http://host.docker.internal:5001`.
Aucun en-tête d’authentification n’est ajouté aux clients existants.

```bash
curl http://127.0.0.1:5001/health
launchctl print "gui/$(id -u)/ch.chatbot-trading.docling-serve"
```

## Qualification et exploitation

La qualification réelle appelle exactement `/v1/convert/file` avec le PDF de
cinq pages et les quatre sorties attendues par Rails :

```bash
DOCLING_DEVICE=mps DOCLING_SERVE_MPS_LIVE=1 \
  services/docling-serve-mps/.venv/bin/pytest \
  services/docling-serve-mps/tests/test_live_service.py -vv -s --durations=0
```

Le run réel du 8 août 2026 a converti les cinq pages en 13,23 secondes et le
test complet a réussi en 18,51 secondes. Ce résultat qualifie le chemin Metal ;
ce n’est pas un benchmark de charge.

Pour redémarrer ou arrêter le service :

```bash
launchctl kickstart -k "gui/$(id -u)/ch.chatbot-trading.docling-serve"
launchctl bootout "gui/$(id -u)/ch.chatbot-trading.docling-serve"
```
