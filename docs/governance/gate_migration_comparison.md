# Rapport comparatif de migration de la gate

## Diagnostic historique revalidé

L’inventaire avant bascule a relevé 61 scripts sous `scripts/`, 374 tests sous `tests/` et 435 fichiers de scripts historiques suivis. Le scénario déclaré par l’ancienne commande regroupait 37 validations et 309 tests, contre les chiffres initiaux respectifs de 58, 329, 387 et 36 : les écarts sont donc de +3, +45, +48 et +1.

Les préconditions réentraient dans la validation globale et rejouaient des nœuds. Le diagnostic a mesuré environ 2 606 sous-commandes pour un parcours complet, une amplification structurelle proche de ×7,55 et 15 contrôles de configuration M-013 rejoués onze fois.

## État canonique après bascule

La seule commande complète est maintenant :

```console
uv run --locked gate
```

L’exécution finale du 13 juillet 2026 est conservée dans [gate_final_report.json](gate_final_report.json). Elle a produit les résultats suivants :

| Mesure | Résultat |
| --- | ---: |
| Nœuds planifiés | 395 |
| Nœuds GREEN | 395 |
| Exécutions totales | 395 |
| Nœuds non uniques | 0 |
| Amplification structurelle | ×1,00 |
| Durée murale | 70,9 s |
| Phase noyau de gate | 0,85 s |
| Phase préconditions | 0,03 s |
| Phase tests | 12,63 s |
| Phase réelle | 32,63 s |

Les 15 contrôles M-013 de configuration sont chacun présents une seule fois dans le rapport. Le nœud `test.m013.validate-m013-reality-product-acceptance` y apparaît une fois, en phase `live`, avec 31,40 s : le pipeline produit réel reste donc inclus dans la commande canonique.

## Contrat de bascule

- `uv run gate` exécute la gate complète.
- `uv run --locked gate` exécute la même gate avec environnement verrouillé.
- `uv run gate --scope m008` et `uv run gate --offline` restent explicitement partiels.
- Le manifeste racine, le plan DAG et le rapport JSON sont les seules autorités d’exécution.
- La liste fermée [historical_reference_allowlist.json](historical_reference_allowlist.json) protège les seules preuves documentaires historiques restantes ; toute référence active ou toute modification d’une preuve listée rend la gate RED.

La décision de bascule est [ADR-029](../adr/ADR-029-gate-python-uv-manifeste-unique.md).
