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
| image_only | p1_feature_indices | 4 | 4 | 5.787 |
| image_only | p2_hyperplane | 1 | 1 | 0.718 |
| image_only | p2_sign_and_negative | 2 | 2 | 2.663 |
| image_only | p2_model | 1 | 1 | 1.272 |
| image_only | p2_constraints | 1 | 1 | 2.916 |
| image_plus_source | p1_feature_indices | 4 | 4 | 6.079 |
| image_plus_source | p2_hyperplane | 1 | 1 | 0.504 |
| image_plus_source | p2_sign_and_negative | 2 | 2 | 2.49 |
| image_plus_source | p2_model | 1 | 1 | 1.2 |
| image_plus_source | p2_constraints | 1 | 1 | 2.735 |

## Verdict préenregistré

- Rejet de toutes les mutations : **OUI**
- Aucune acceptation sans preuve source : **OUI**
- Source + crop non inférieur au contrôle : **OUI**
- Correction ciblée de `x_k` : **OUI**

Une conformité porte uniquement sur les neuf faits préenregistrés. Elle ne prouve pas l’intégralité des pages.
