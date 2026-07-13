# Rapport T-005 - Benchmark de routes documentaires M-012

## Scénario BDD

- Given un corpus pilote figé et un jeu annoté page par page.
- When les routes `Docling standard`, `Granite-Docling direct`, `prétraitement + Granite-Docling` et `double conversion et adjudication` sont mesurées.
- Then chaque route publie les métriques documentaires, le temps, la mémoire, la stabilité, les échecs et les raisons d'échec sans retirer les pages en erreur du dénominateur.

## Source

- Source corpus: `PCORP-M012-*`.
- Source annotations: `ASET-M012-*`.
- Politique: `DocumentRouteBenchmarkPolicy-1.0`.
- ADR appliquées: ADR-002 et ADR-010.

## Routes obligatoires

- `Docling standard`
- `Granite-Docling direct`
- `prétraitement + Granite-Docling`
- `double conversion et adjudication`

## Métriques publiées

| Métrique | Sens | Dénominateur |
|---|---|---|
| `document_cer` | Taux d'erreur caractère sur transcription de référence. | Pages benchmark, échecs inclus. |
| `document_wer` | Taux d'erreur mot sur transcription de référence. | Pages benchmark, échecs inclus. |
| `document_numeric_token_accuracy` | Exactitude des tokens numériques critiques. | Pages benchmark, échecs inclus. |
| `document_sign_accuracy` | Exactitude des signes des valeurs critiques. | Pages benchmark, échecs inclus. |
| `document_formula_fidelity` | Fidélité des formules attendues. | Pages benchmark, échecs inclus. |
| `document_cell_accuracy` | Exactitude des cellules annotées. | Pages benchmark, échecs inclus. |
| `document_reading_order_accuracy` | Respect de l'ordre de lecture annoté. | Pages benchmark, échecs inclus. |
| `document_page_time_seconds` | Temps de traitement par page. | Pages benchmark, échecs inclus. |
| `document_memory_bytes` | Mémoire observée par page. | Pages benchmark, échecs inclus. |
| `document_route_stability_rate` | Stabilité de route sur page attendue. | Pages benchmark, échecs inclus. |
| `document_failure_rate` | Pages échouées par route. | Pages benchmark. |

## Échecs

Chaque `RoutePageMeasurement` conserve `status`, `output_id` et `failure_reason`. Une sortie en échec sans raison explicite est refusée par le modèle de domaine; une page échouée reste comptée dans les métriques de route et dans les détails par strate.

## Commandes de preuve

```console
uv run --locked gate
uv run --locked gate
```
