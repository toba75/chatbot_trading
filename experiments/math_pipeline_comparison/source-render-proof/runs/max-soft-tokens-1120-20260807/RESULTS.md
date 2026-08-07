# Résultats — preuve PDF source + rendu

- PDF : `219c2064ba9292d286f4b3bcc65eb9e94b418705c51b9f98f54f2ad70321ddf1`
- Faits prouvés par la source : **9/9**
- Mutations rejetées : **9/9**

## Candidats existants

| Candidat | Faits conformes | Faits prouvés |
|---|---:|---:|
| marker_force_ocr | 9 | 9 |
| gemma_200dpi | 9 | 9 |
| gemma_300dpi | 8 | 9 |
| gemma_200_300_reconciled | 7 | 9 |
| docling_granite | 8 | 9 |
| mineru | 8 | 9 |

## Reconnaissance ciblée

| Mode | Crop | Faits conformes | Faits ciblés | Durée (s) |
|---|---|---:|---:|---:|
| image_only | p1_feature_indices | 4 | 4 | 8.784 |
| image_only | p2_hyperplane | 1 | 1 | 2.625 |
| image_only | p2_sign_and_negative | 2 | 2 | 4.527 |
| image_only | p2_model | 1 | 1 | 3.178 |
| image_only | p2_constraints | 1 | 1 | 4.928 |
| image_plus_source | p1_feature_indices | 4 | 4 | 8.338 |
| image_plus_source | p2_hyperplane | 1 | 1 | 2.419 |
| image_plus_source | p2_sign_and_negative | 2 | 2 | 4.417 |
| image_plus_source | p2_model | 1 | 1 | 3.09 |
| image_plus_source | p2_constraints | 1 | 1 | 4.915 |

## Verdict préenregistré

- Rejet de toutes les mutations : **OUI**
- Aucune acceptation sans preuve source : **OUI**
- Source + crop non inférieur au contrôle : **OUI**
- Correction ciblée de `x_k` : **OUI**

Une conformité porte uniquement sur les neuf faits préenregistrés. Elle ne prouve pas l’intégralité des pages.
