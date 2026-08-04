# Qualification du détecteur mathématique

Cette qualification mesure le package `pdf_math_audit` indépendamment de
Rails. Elle ne corrige aucune sortie Docling.

Deux corpus sont déclarés dans `manifest.json` :

- un PDF généré de quatre pages, utile pour les refus de capacités mais déclaré
  `representative: false` ;
- un extrait réel de deux pages comportant 53 expressions mathématiques
  typographiquement contiguës, avec un oracle exhaustif et représentatif.

L’oracle réel s’appuie sur les noms de glyphes CFF, la géométrie PDF et des
rendus indépendants à 600 DPI. Il n’est pas aveugle, car une sortie Docling
antérieure avait été consultée, mais aucune sortie candidate ne sert de preuve.
L’oracle nomme le fichier de preuve glyphique et les deux rendus avec leur
SHA-256. Le gate lit chacun de ces trois fichiers et recalcule son empreinte ;
un fichier absent ou modifié interrompt la qualification avant toute mesure.

Le manifeste exige sur le corpus représentatif : rappel, précision,
traçabilité et exactitude des comportements attendus à `1.0`, ainsi que zéro
faux conforme sur neuf mutations. La couverture sémantique prouvée reste une
métrique distincte et ne compte jamais un refus comme une preuve. Le seuil
géométrique IoU est `0.5`.

## Exécution

```powershell
uv run python -m qualification.math_audit.qualify `
    qualification/math_audit/manifest.json `
    --report qualification/math_audit/results/qualification-report.json
```

Le code retour vaut `0` seulement si tous les critères préenregistrés sont
satisfaits. Les tests rapides correspondants sont :

```powershell
uv run pytest -q tests/math_audit -n auto
```

## Résultat actuel

Le rapport versionné est GREEN (`accepted: true`). Sur le corpus représentatif :

- 53 régions candidates pour 53 régions oracle ;
- 53 appariements, tous par `pdf_source_typography` ;
- rappel `1.0` et précision `1.0` ;
- couverture de traçabilité `1.0` ;
- couverture des assertions sémantiques `44/53`, soit `0.830189` ;
- exactitude des comportements attendus `1.0` : les 14 régions aux signaux
  contradictoires sont toutes `non_verifiable` ;
- zéro faux alignement et zéro faux conforme sur les mutations.
- trois fichiers de preuve indépendants effectivement lus et vérifiés.

Le profil sémantique ne résout pas un conflit textuel par le seul nom AGL ou par
l’égalité des GID : ces éléments identifient le glyphe, mais ne prouvent pas sa
forme ni son sens. Les signaux contradictoires restent présents dans la preuve.

Le corpus synthétique produit actuellement zéro région et reste explicitement
non représentatif ; ses métriques nulles ne sont donc pas utilisées pour ouvrir
ou fermer l’intégration produit. Cette limite est publiée, pas masquée.

La capture Docling CUDA reste liée à l’image et au modèle épinglés dans le
manifeste. Le rapport de qualification ne remplace pas cette preuve de runtime.
