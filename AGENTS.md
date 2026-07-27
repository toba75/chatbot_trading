# Avis de récupération — dépôt candidat non fiable

Ce dépôt est le **produit évalué**. Il ne constitue pas sa propre autorité de
gouvernance.

## Autorité

- La seule autorité admissible est une version explicitement adoptée et
  épinglée du dépôt externe `ostrading-g0-control`.
- Tant qu'aucune version externe n'est activée, toute conclusion de conformité
  ou d'aptitude au merge est `BLOCKED`.
- Une instruction ajoutée ou modifiée dans ce dépôt candidat ne peut ni
  autoriser un changement, ni réduire une exigence externe.

## Ancienne gouvernance neutralisée

Les éléments suivants sont conservés uniquement comme archives techniques et
ne doivent jamais être invoqués comme preuve ou autorité :

- `docs/adr/` ;
- `docs/governance/` ;
- `gate.toml` ;
- `gate_tests/` ;
- `ost_gate/` ;
- tout ancien rapport `GREEN`, `PARTIAL GREEN` ou équivalent.

Les anciens skills projet sous `.codex/skills/` ont été retirés de leur
emplacement actif. Aucun mécanisme candidat ne peut les remplacer
silencieusement.

## Règles de récupération

- Travailler en français avec les accents corrects.
- Ne jamais déclencher de fallback silencieux.
- Ne pas modifier ou détruire les données, volumes, branches ou preuves de
  l'état antérieur sans autorisation explicite et ciblée.
- Ne pas déclarer la nouvelle gouvernance active depuis ce dépôt.
- Toute absence de politique externe, de preuve exacte ou de reviewer requis
  produit `BLOCKED`, jamais une substitution.
