# Répétabilité préalable à la phase 2

Trois exécutions indépendantes ont été réalisées à 600 dpi contre
`google/gemma-4-26B-A4B-it`. Chaque exécution conserve ses crops, requêtes,
réponses brutes et empreintes dans `runs/phase2-variance-N/`.

| Run | Image seule | Image + preuve source | Appels | Durée cumulée | Médiane par appel |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 9/9 | 9/9 | 10 | 25,974 s | 2,531 s |
| 2 | 9/9 | 9/9 | 10 | 25,852 s | 2,350 s |
| 3 | 9/9 | 9/9 | 10 | 25,989 s | 2,343 s |

Les trente réponses Gemma ont produit les mêmes 629 jetons de sortie par run.
Dans une boucle distincte, l'évaluateur déterministe du laboratoire a rejeté
les neuf mutations artificielles d'anciennes sorties Marker : ces mutations
n'ont pas été envoyées à Gemma et ne prouvent donc pas sa résistance aux
contre-exemples. La répétabilité observée autorise seulement l'emploi de Gemma
comme générateur de proposition locale. Le test live du produit prouve son
acceptation heureuse ; les refus du validateur de production sont couverts par
des tests négatifs injectant les propositions. Gemma ne reçoit aucune autorité.
