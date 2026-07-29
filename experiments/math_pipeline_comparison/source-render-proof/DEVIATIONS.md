# Écarts au protocole

## Run 1 — crop invalide

Le premier crop `p2_sign_and_negative` utilisait la boîte
`(215, 270, 475, 330)` en points PDF. L’inspection de la planche de contact a
montré qu’elle coupait le début et la continuation de la phrase contenant
`-1`. Le fait `p2_negative_one` ne se trouvait donc pas intégralement dans
l’entrée transmise au modèle.

Ce run est conservé dans `runs/run1-invalid-crop/` et exclu de la comparaison
principale. La boîte est remplacée par `(60, 270, 480, 335)`. Aucun fait, aucun
validateur et aucun critère de succès n’a été modifié.

## Contre-revue — portée de la preuve exhaustive

La première version du rapport supplémentaire affichait `0 divergence` alors
qu’elle ne comptait que les écarts de GID et d’association `rawdict`. Une
contre-revue indépendante a relevé 20 désaccords Unicode entre MuPDF et l’AGL,
ainsi que 21 entrées `ToUnicode` contradictoires.

Le vérificateur et le rapport ont été corrigés pour publier séparément ces
mesures. Le verdict porte désormais sur la traçabilité structurelle
code PDF → CharString CFF → GID rendu. Il ne revendique ni la correction
Unicode de tous les glyphes, ni leur apparence raster. Les scores préenregistrés
sur les neuf faits ciblés ne changent pas.
