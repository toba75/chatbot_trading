# Orienter la qualification vers l'index RAG du corpus de trading

Ce fichier est l'autorité d'exécution de cette tranche. Elle acte une décision
produit : la finalité du système est un chatbot de trading fondé sur RAG, dont
les sources sont les PDF de `docs/corpus_reference/`. Le pipeline de
qualification mathématique cesse d'être un éditeur de documents dont l'audit
HTML gate la publication ; il devient le **service de qualité et de provenance
de l'index RAG**. La fidélité qui compte est textuelle (le contenu des chunks),
la preuve sert à étiqueter la confiance et à fonder la citation, et l'axe
HTML/MathML n'appelle plus aucun investissement nouveau.

La tranche est terminée uniquement lorsque les sept lignes ci-dessous portent
le statut **terminé** avec la preuve indiquée. Une étape « presque finie », des
tests verts ou une démonstration ponctuelle ne suffisent pas.

Les étapes 1 → 2 → 3 sont séquentielles. Les étapes 4 et 5 dépendent du contrat
de l'étape 3. L'étape 6 est indépendante et peut avancer en parallèle. L'étape 7
dépend de l'étape 3.

| Étape | Prescription | Condition de complétude | Statut |
|---|---|---|---|
| 1 | Assainir et geler le corpus de référence. Purger les artefacts AppleDouble (`._*`, `.__*`), trancher le doublon exact (`document.pdf` = `short-term-trading-strategies-that-work-.pdf`) et les deux paires quasi-doublons (« high frequency trading », « trading-on-momentum »), classer chaque PDF (texte ou scan), acter le sort des quatre livres scannés (voie OCR ou exclusion motivée) et le mode de conservation du corpus (LFS ou hors dépôt). | Un manifeste committé (`docs/corpus_reference/manifest.json`) couvre 100 % des fichiers du répertoire : SHA-256, pages, classe texte/scan, décision et motif pour chaque exclusion. Un script rejouable vérifie que le répertoire et le manifeste coïncident exactement — aucun fichier hors manifeste, aucune entrée sans fichier. Les quatre scans portent une décision explicite ; aucune ne repose sur un OCR non encore réalisé. | terminé |
| 2 | Mesurer la couverture réelle. Convertir puis qualifier chaque PDF textuel du manifeste en mode audit (sans correction Gemma), et agréger par livre : régions, verdicts, codes de refus, pages exclues, durées. | Un rapport de couverture committé donne l'histogramme des codes de refus par livre et agrégé, le nombre de régions par verdict, et chiffre le gain potentiel des trois causes de non-vérifiabilité dominantes. Chaque livre du manifeste y figure : qualifié, ou échec d'exécution avec le constat exact — un crash du pipeline sur un PDF sauvage est un résultat documenté, jamais une exclusion silencieuse. Aucun oracle n'est requis à cette étape. | à faire |
| 3 | Définir et implémenter le contrat de l'index RAG. Un export de chunks depuis les artefacts de qualification : texte avec LaTeX inline, drapeau par formule (`proven`, `corroborated`, `unverified`, `contradicted`), provenance de citation (document, page, bbox) permettant de produire le crop source, identité et version du contrat. | Le schéma est versionné et documenté. L'exporteur est testé : un chunk dont une formule n'a ni drapeau ni provenance est refusé (contre-exemple en test). L'export réel d'au moins cinq livres du corpus existe avec comptages par drapeau. Aucun drapeau ne surclasse la preuve : `proven` exige le verdict du pipeline, `corroborated` exige l'accord d'un second modèle indépendant mesuré par l'étape 6, jamais une heuristique. | à faire |
| 4 | Étendre la vérification aux tableaux. Chaque cellule numérique d'un tableau Docling est confrontée aux glyphes PDF de sa zone par la machinerie de preuve existante ; les cellules reçoivent des verdicts au même contrat que les formules, avec raison explicite quand la vérification est impossible. | La mesure porte sur un échantillon d'au moins vingt tableaux réels issus d'au moins cinq livres distincts, avec taux de cellules vérifiées publié. Un contre-exemple synthétique — un tableau dont une cellule est altérée après conversion — est détecté. Les tableaux non vérifiables portent une raison localisée, pas un silence. | à faire |
| 5 | Acter la politique des graphiques. Décider entre l'exclusion avec marqueur de présence et la description générée par VLM ; dans les deux cas, aucun texte généré ne se présente comme contenu source. Implémenter la politique dans l'export de chunks. | La politique est écrite dans ce dossier. L'export marque chaque figure conformément ; un test vérifie qu'une description générée porte son origine (`generated`) et qu'aucun chunk ne la présente comme texte du document. | à faire |
| 6 | Construire les scorecards des composants stochastiques. Un banc rejouable par modèle sur cibles épinglées : granite-docling (taux de jetons exacts par formule contre les oracles existants), Gemma (taux d'acceptation prouvée sur un jeu de cibles épinglé), Nougat (généralisation du harnais shadow existant). Résultats datés, versionnés, conservés en série temporelle. | Chaque banc s'exécute par une commande unique et dépose un résultat daté portant la révision exacte du modèle mesuré. Une ligne de base est enregistrée pour les versions actuelles des trois modèles. Un changement de révision de modèle sans nouvelle mesure est détecté — le banc ou la qualification le signale explicitement. Les seuils binaires à 1.0 restent réservés aux invariants du code déterministe ; les modèles se suivent en courbes, pas en portes. | à faire |
| 7 | Construire les evals de récupération. Un jeu d'au moins cinquante questions de trading, chacune liée aux passages sources attendus (livre, page) dans le corpus gelé. Un harnais mesure la récupération (hit@k) sur l'index issu de l'étape 3. Les evals de qualité de réponse restent hors de cette tranche tant que le chatbot n'existe pas. | Les questions et leurs passages attendus sont committés. Le harnais est rejouable par une commande et publie hit@k. Une ligne de base est mesurée sur l'index réel. La limite de périmètre (pas d'eval de réponses sans chatbot) est écrite, pas implicite. | à faire |

## Contraintes invariantes

- La donnée PDF et le `DoclingDocument` natif restent les autorités conservées.
  Un drapeau de confiance ne transforme jamais un contenu non prouvé en contenu
  prouvé ; il rend l'incertitude explicite au lieu de la masquer.
- Aucun contenu généré — description de figure, sortie OCR, correction de
  modèle — ne se présente comme contenu source. Chaque fragment porte son
  origine et son statut.
- La précision se prouve, la couverture se mesure. Aucun invariant nouveau ne
  gate sur un seuil de couverture ; aucune mesure de couverture ne dispense
  d'une preuve pour publier `proven`.
- Un échec d'exécution sur un PDF du corpus est un constat documenté avec sa
  cause, jamais une exclusion silencieuse du manifeste ni un contournement.
- Les livres scannés ne reçoivent aucun traitement tant que la décision de
  l'étape 1 n'est pas actée ; aucune preuve glyphique n'est simulée sur un scan.
- L'axe HTML/MathML existant reste maintenu en l'état ; tout investissement
  nouveau sur cet axe doit être justifié par un besoin de l'index RAG, pas par
  la complétude du visualiseur.

## Preuves à reporter avant clôture

- le manifeste du corpus, son script de vérification et le journal des
  décisions (doublons, scans, conservation) ;
- les identifiants des runs d'audit de l'étape 2, le rapport de couverture
  agrégé et l'histogramme des refus qui fonde la feuille de route de
  généralisation ;
- le schéma du contrat de chunks, l'export réel et ses comptages par drapeau ;
- les résultats de base des trois bancs avec les révisions exactes des modèles
  mesurés ;
- la ligne de base hit@k des evals de récupération ;
- le résultat de la revue contradictoire portant explicitement sur l'adhérence
  aux sept étapes et aux contraintes invariantes.

## Preuves acquises

- Le corpus compte 47 PDF réels, 10 602 pages. Les 43 artefacts AppleDouble
  (8 398 octets, en-tête `00 05 16 07` vérifié) ont été supprimés par le
  développeur.
- `qualification/corpus_reference/manifest.py` construit et vérifie le manifeste.
  `build` décrit chaque fichier du répertoire hormis le manifeste lui-même et
  refuse un corpus vide comme un fichier étranger — MuPDF ouvrant aussi bien un
  texte brut qu'un PDF, un intrus serait sinon décrit comme un ouvrage. `verify`
  ne compare pas seulement les empreintes : il reconstruit le manifeste et
  confronte chaque champ, de sorte qu'une décision modifiée sans reconstruction
  soit signalée.
- La couche de texte est classée sur preuve structurelle et non sur la
  métadonnée du producteur : un raster couvrant la page **sous** du texte signe
  une sortie d'OCR. La métadonnée s'est révélée trompeuse — `trading-for-a-living`
  annonce `Paper Capture Plug-in` sans porter le moindre raster, et reste donc
  classé `text`.
- Classement obtenu : 40 `text`, 4 `scanned`, 3 `ocr`. Les trois `ocr` étaient
  invisibles au premier jet et ont été révélés par la revue contradictoire :
  `Macro_to_micro_volatility_trading` (police `GlyphLessFont` à 2 glyphes,
  raster sur 8 pages sur 8) et `short-term-trading-strategies-that-work-` avec
  son doublon `document.pdf` (polices ClearScan synthétiques, fautes d'OCR
  visibles : « TIle », « Indicntors »).
- Décision actée : un document sans couche de texte rédigée est écarté par
  règle, sans décision manuelle. Les 4 scans le sont faute de glyphes à décoder,
  les 3 OCR parce qu'un contenu produit ne peut pas passer pour la source et que
  leurs glyphes synthétiques rendraient toute preuve fictive. Aucune de ces
  décisions ne repose sur un OCR non réalisé ; toutes sont réversibles en une
  ligne.
- Les trois doublons sont tranchés sur preuve : `document.pdf` (SHA-256
  identique), `high frequency trading.pdf` (257 pages et texte identiques, même
  producteur) et `trading-on-momentum.pdf` (refonte `Multivalent Merge` contre la
  sortie Distiller d'origine, qui porte plus de texte pour une page de moins).
- Conservation : hors dépôt. Les livres sont sous droit d'auteur ; `.gitignore`
  ignore `docs/corpus_reference/*` et ré-inclut le seul `manifest.json`, ce que
  `git check-ignore -v` confirme dans les deux sens.
- Corpus retenu pour la suite : **38 documents, 8 981 pages**.
- Vérification : 17 tests Python en 1,22 s, identiques sous `xdist -n 4` ; `ruff`
  vert ; `verify` sur le corpus réel rend 0 écart.
- Revue contradictoire en contexte vierge : sept défauts confirmés, tous corrigés
  — trois OCR classés `text` et retenus, `verify` aveugle à la dérive des
  décisions, corpus vide écrasant le manifeste avec un code de succès, fichiers
  non-PDF invisibles, seuils de classification non épinglés (12 mutations sur 14
  survivaient), test de sérialisation ne testant ni tri ni indentation,
  dépendance au répertoire courant.

## Limites connues

- Douze documents retenus n'embarquent aucune police sur les pages
  échantillonnées, dont six conversions calibre EPUB→PDF. Leur pagination n'est
  pas celle de l'ouvrage imprimé : la provenance de citation de l'étape 3 devra
  en tenir compte.
- Le corpus n'existe que dans l'arbre de travail. `git clean -xd` le supprimerait
  et le manifeste ne permet pas de le reconstituer ; une copie hors dépôt reste
  à la charge du développeur.
