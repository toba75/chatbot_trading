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

Les étapes 1 → 2 → 3 sont séquentielles. Les sous-étapes 3.0 à 3.6 du plan des
métadonnées ci-dessous font partie de l'étape 3 : cette étape ne peut pas être
déclarée terminée tant qu'elles ne le sont pas. Les étapes 4 et 5 dépendent du
contrat de l'étape 3. L'étape 6 est indépendante et peut avancer en parallèle.
L'étape 7 dépend de l'étape 3 et ses sous-étapes 7.1 et 7.2 qualifient séparément
chaque signal de classement.

| Étape | Prescription | Condition de complétude | Statut |
|---|---|---|---|
| 1 | Assainir et geler le corpus de référence. Purger les artefacts AppleDouble (`._*`, `.__*`), trancher le doublon exact (`document.pdf` = `short-term-trading-strategies-that-work-.pdf`) et les deux paires quasi-doublons (« high frequency trading », « trading-on-momentum »), classer chaque PDF (texte ou scan), acter le sort des quatre livres scannés (voie OCR ou exclusion motivée) et le mode de conservation du corpus (LFS ou hors dépôt). | Un manifeste committé (`docs/corpus_reference/manifest.json`) couvre 100 % des fichiers du répertoire : SHA-256, pages, classe texte/scan, décision et motif pour chaque exclusion. Un script rejouable vérifie que le répertoire et le manifeste coïncident exactement — aucun fichier hors manifeste, aucune entrée sans fichier. Les quatre scans portent une décision explicite ; aucune ne repose sur un OCR non encore réalisé. | terminé |
| 2 | Mesurer la couverture réelle. Convertir puis qualifier chaque PDF textuel du manifeste en mode audit (sans correction Gemma), et agréger par livre : régions, verdicts, codes de refus, pages exclues, durées. | Un rapport de couverture committé donne l'histogramme des codes de refus par livre et agrégé, le nombre de régions par verdict, et chiffre le gain potentiel des trois causes de non-vérifiabilité dominantes. Chaque livre du manifeste y figure : qualifié, ou échec d'exécution avec le constat exact — un crash du pipeline sur un PDF sauvage est un résultat documenté, jamais une exclusion silencieuse. Aucun oracle n'est requis à cette étape. | terminé |
| 3 | Définir et implémenter le contrat de l'index RAG. Un export de chunks depuis les artefacts de qualification : texte avec LaTeX inline, drapeau par formule (`proven`, `corroborated`, `unverified`, `contradicted`), provenance de citation (document, page, bbox) permettant de produire le crop source, identité et version du contrat. Le contrat transporte aussi la projection bibliographique, temporelle et éditoriale définie par le sous-plan ci-dessous. | Le schéma est versionné et documenté. L'exporteur est testé : un chunk dont une formule n'a ni drapeau ni provenance est refusé (contre-exemple en test). L'export réel d'au moins cinq livres du corpus existe avec comptages par drapeau. Le registre de sources couvre les 38 documents retenus, y compris les états ambigus ou non résolus, et chaque champ projeté est traçable. Aucun drapeau, fournisseur externe ni signal éditorial ne surclasse la preuve : `proven` exige le verdict du pipeline, `corroborated` exige l'accord d'un second modèle indépendant mesuré par l'étape 6, jamais une heuristique. | terminé |
| 4 | Étendre la vérification aux tableaux. Chaque cellule numérique d'un tableau Docling est confrontée aux glyphes PDF de sa zone par la machinerie de preuve existante ; les cellules reçoivent des verdicts au même contrat que les formules, avec raison explicite quand la vérification est impossible. | La mesure porte sur un échantillon d'au moins vingt tableaux réels issus d'au moins cinq livres distincts, avec taux de cellules vérifiées publié. Un contre-exemple synthétique — un tableau dont une cellule est altérée après conversion — est détecté. Les tableaux non vérifiables portent une raison localisée, pas un silence. | à faire |
| 5 | Acter la politique des graphiques. Décider entre l'exclusion avec marqueur de présence et la description générée par VLM ; dans les deux cas, aucun texte généré ne se présente comme contenu source. Implémenter la politique dans l'export de chunks. | La politique est écrite dans ce dossier. L'export marque chaque figure conformément ; un test vérifie qu'une description générée porte son origine (`generated`) et qu'aucun chunk ne la présente comme texte du document. | à faire |
| 6 | Construire les scorecards des composants stochastiques. Un banc rejouable par modèle sur cibles épinglées : granite-docling (taux de jetons exacts par formule contre les oracles existants), Gemma (taux d'acceptation prouvée sur un jeu de cibles épinglé), Nougat (généralisation du harnais shadow existant). Résultats datés, versionnés, conservés en série temporelle. | Chaque banc s'exécute par une commande unique et dépose un résultat daté portant la révision exacte du modèle mesuré. Une ligne de base est enregistrée pour les versions actuelles des trois modèles. Un changement de révision de modèle sans nouvelle mesure est détecté — le banc ou la qualification le signale explicitement. Les seuils binaires à 1.0 restent réservés aux invariants du code déterministe ; les modèles se suivent en courbes, pas en portes. | à faire |
| 7 | Construire les evals de récupération. Un jeu d'au moins cinquante questions de trading, chacune liée aux passages sources attendus (livre, page) dans le corpus gelé. Les jugements nomment tous les passages acceptables et leur pertinence graduée lorsqu'un ordre de préférence est attendu. Un harnais mesure la récupération sur l'index issu de l'étape 3. Le jeu couvre explicitement les questions intemporelles, sensibles à la date, exigeant une source actuelle, les sources avec ou sans ISBN, et les ouvrages peu populaires mais pertinents. Les evals de qualité de réponse restent hors de cette tranche tant que le chatbot n'existe pas. | Les questions et leurs passages attendus sont committés. Le harnais est rejouable par une commande et publie hit@k, MRR et nDCG@k, globalement et par strate. Une ligne de base lexicale et dense est mesurée sans autorité, fraîcheur ni popularité ; chaque signal est ensuite ajouté isolément et conservé seulement s'il améliore les strates visées sans dégrader les autres. L'absence de métadonnée vaut `unknown`, jamais zéro. La limite de périmètre (pas d'eval de réponses sans chatbot) est écrite, pas implicite. | à faire |

## Sous-plan des étapes 3 et 7 — métadonnées et valeur des sources

### Responsabilité et frontières

Le manifeste `docs/corpus_reference/manifest.json` reste le registre mécanique
de l'identité des fichiers, de leur couche de texte et de leur inclusion. Il
n'accueille aucune métadonnée bibliographique ou commerciale : son générateur
reconstruit exactement ses champs, et le répertoire `docs/corpus_reference/`
refuse tout fichier étranger hormis le manifeste et les PDF.

Un registre de sources distinct, prévu sous `docs/source_catalog/`, porte les
revendications bibliographiques, temporelles et éditoriales. Chaque entrée est
reliée à `source_sha256`. Elle ne modifie ni le PDF ni le `DoclingDocument` et
devient une entrée reproductible de la projection de chunks.

L'implémentation prévue est un petit module Python sous
`qualification/source_catalog/`, accompagné de ses tests ciblés sous
`tests/source_catalog/`. Il réutilise d'abord la bibliothèque standard pour le
JSON, les empreintes et les appels HTTP ; aucune dépendance n'est ajoutée tant
qu'un besoin réel ne l'impose. Deux commandes explicites sont attendues :

- `enrich` propose des correspondances de fournisseur sans les promouvoir
  silencieusement ;
- `verify` confronte le registre, le manifeste et les preuves de correspondance,
  puis échoue sur toute dérive, identité absente ou valeur acceptée sans preuve.

### Contrat du registre

Le schéma versionné distingue quatre familles qui ne sont jamais aplaties dans
une note globale :

1. **Identité bibliographique** : titre d'affichage, auteurs, langue, éditeur,
   type de publication, ISBN/ISSN/autres identifiants et identifiants des
   fournisseurs. `source_sha256` reste l'identité du fichier et de ses
   citations. Les relations optionnelles `work → edition → source_asset` ne
   sont acceptées qu'après revue ; un ISBN désigne une édition candidate, jamais
   le PDF lui-même. Les valeurs inconnues restent nulles.
2. **Temporalité** : date de publication originale, date de l'édition du
   fichier et date de révision du contenu lorsqu'elle est prouvée. Une
   réimpression récente ne devient pas une révision récente.
3. **Appréciation éditoriale** : domaines dans lesquels la source ou l'auteur
   est pertinent, nature de la méthode, présence de preuves ou de références,
   limites observées, justification, auteur et date de la revue. Il n'existe ni
   `authority_score` global ni autorité d'un auteur valable pour tous les sujets.
4. **Observations commerciales** : fournisseur, identifiant, marché, catégorie,
   note moyenne, nombre de notes, rang et instant d'observation. Une note sans
   nombre de votes et un rang sans marché, catégorie et date sont invalides.

Chaque consultation externe porte son fournisseur, son identifiant de ressource,
la requête ou l'identifiant utilisé, l'instant de lecture et, lorsque le contrat
du fournisseur l'impose, son expiration. L'état de consultation distingue
`not_queried`, `succeeded`, `no_match`, `unavailable` et `expired`. L'état de
chaque candidat distingue séparément `candidate`, `accepted`, `ambiguous` et
`rejected`. Une correspondance par ISBN lu dans le contenu source peut être
acceptée après contrôles de cohérence ; plusieurs ISBN dans un même PDF restent
des candidats d'édition distincts. Une correspondance par titre et auteur reste
candidate jusqu'à revue. La propriété PDF et le nom de fichier ne peuvent jamais
suffire seuls.

Le registre conserve la preuve utilisée pour accepter une valeur : localisation
dans le PDF lorsque l'information y figure, ou référence précise du fournisseur
externe. Une réponse externe brute n'est conservée que si les conditions du
fournisseur l'autorisent ; sinon la donnée ne peut pas devenir une autorité
durable et cette limite est observable dans l'entrée.

### Fournisseurs autorisés dans cette tranche

Google Books est le seul enrichissement réseau prévu initialement. La résolution
essaie dans l'ordre : identifiant ISBN/ISSN issu du contenu, puis titre et auteur.
Elle conserve tous les candidats plausibles et ne choisit jamais le premier
résultat par défaut. Le bilan sépare les correspondances exactes, acceptées après
revue, ambiguës, absentes et les documents sans identifiant de livre, notamment
les articles et working papers. Avant toute donnée committée, le contrat de
persistance documente les champs conservés, les conditions Google Books alors
applicables et la procédure de retrait d'un contenu fourni par l'API. Une valeur
qui ne peut pas être conservée selon ces conditions reste une observation non
persistée et ne peut pas devenir une autorité du registre.

Amazon n'est pas une dépendance de cette tranche. Au 7 août 2026, la Creators
API est liée au programme d'affiliation et à des ventes référées ; ses règles de
cache limitent `BrowseNodeInfo` à une heure et les informations produit à un
jour. Elle expose des rangs de vente par marché et catégorie, parfois absents,
mais ne documente pas comme ressource par ouvrage le couple note moyenne/nombre
de notes nécessaire à une pondération fiable. Un adaptateur Amazon ne sera
planifié qu'après une preuve distincte d'accès durable, de droit de conservation
et de disponibilité des champs, puis une mesure de son apport. Aucun scraping de
page produit ne remplace cette preuve.

Références vérifiées pour l'implémentation :

- [Google Books — ressource Volume](https://developers.google.com/books/docs/v1/reference/volumes) ;
- [Google Books — recherche par ISBN, titre ou auteur](https://developers.google.com/books/docs/v1/using) ;
- [Google Books — conditions d'utilisation](https://developers.google.com/books/terms) ;
- [Amazon Creators API — accès et limites](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/concepts/api-rates) ;
- [Amazon Creators API — cache](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/concepts/best-programming-practices) ;
- [Amazon Creators API — rangs de vente](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/api-reference/resources/browse-node-info).

### Développement non destructif (3.6)

Le modèle est celui d'un développement photographique : le `DoclingDocument`
natif est le négatif, jamais modifié ; la recette de développement est la liste
ordonnée des retouches, chacune portant sa provenance ; le document développé
est le tirage, intégralement reproductible depuis le négatif et la recette — et
identique au négatif quand la recette est vide.

La recette admet deux opérations, jamais confondues :

- `correction` : remplacement d'une transcription contredite par le texte
  prouvé, portée par les records de correction acceptés existants (moteur,
  preuves par octets, crop et confirmation visuelle) ;
- `pdf_supplement` : insertion d'un contenu prouvé par les octets du PDF mais
  absent de la transcription (régions sources sans conteneur Docling), portant
  la référence de sa région, ses jetons prouvés, sa page et sa boîte.

Le développé est l'unique base des sorties aval : les chunks de l'index, l'HTML
paginé et le Markdown affichés par l'interface en dérivent tous. Aucune sortie
ne repart du natif. Chaque contenu déclare son origine — `transcription`,
`correction` ou `pdf_supplement` — et un contenu dérivé ne se présente jamais
comme transcription : la démarcation vit dans les métadonnées et, à l'écran,
dans un marquage visible. Le texte dense de l'index inclut les corrections et
les suppléments (la meilleure information disponible, prouvée) ; les signaux
commerciaux en restent exclus.

### Ordre d'implémentation

| Sous-étape | Travail | Preuve de complétude | Statut |
|---|---|---|---|
| 3.0 | Rétablir la frontière du corpus avant l'enrichissement : déplacer `coverage.json`, `coverage-sample.json` et `coverage-report.md` hors de `docs/corpus_reference/`, puis mettre à jour leur producteur, leurs tests et leurs références. | `uv run python -m qualification.corpus_reference.manifest verify` rend zéro écart avec les rapports présents à leur nouvel emplacement ; aucun artefact documentaire n'est ajouté à l'exception du manifeste dans le répertoire des PDF. | terminé |
| 3.1 | Publier le schéma versionné du registre, ses états, ses règles de provenance, la politique de persistance des fournisseurs et le validateur local. | Des contre-exemples prouvent le refus d'un champ accepté sans preuve, d'une note sans nombre de votes, d'un rang sans contexte et d'une date d'édition confondue avec une date de révision. Le manifeste reste inchangé et vérifiable. La politique Google Books nomme les champs conservés et la procédure de retrait. | terminé |
| 3.2 | Implémenter le résolveur Google Books et sa commande `enrich`, avec configuration explicite de l'accès réseau, délais bornés et erreurs observables. | Les tests unitaires couvrent ISBN exact, recherche titre/auteur ambiguë, volume absent, réponse invalide et fournisseur indisponible. Un test réseau simulé prouve seulement le contrat local ; la preuve de frontière appelle l'API réelle sur un document autorisé. | terminé |
| 3.3 | Enrichir les 38 documents retenus et revoir manuellement les candidats non exacts. | Un rapport réel donne les comptes de consultations `succeeded`, `no_match` et `unavailable`, puis de candidats `accepted`, `ambiguous` et `rejected`. Il distingue livres, publications sans ISBN et PDF contenant plusieurs ISBN, et relie chaque acceptation à sa preuve. Aucun document ne disparaît parce que le fournisseur ne le connaît pas. | terminé |
| 3.4 | Réaliser l'appréciation éditoriale et temporelle minimale du corpus. | Les 38 documents portent soit une revue datée avec domaines, justification et limites, soit `not_assessable` avec une raison précise ; aucun ne reste `unreviewed`. Les trois dates sont distinctes et nullables. Un échantillon contradictoire couvre un classique ancien encore pertinent, une information ancienne devenue obsolète et une source méconnue pertinente. | terminé |
| 3.5 | Projeter dans les chunks uniquement les champs stables nécessaires au filtrage, à l'affichage et à l'évaluation. | La projection est reconstruite depuis le PDF, le `DoclingDocument` et le registre. La copie dans l'index conserve `source_sha256`, les références de provenance et la version du registre. Aucun signal commercial n'entre dans le texte dense ni ne modifie le statut de preuve. | terminé |
| 3.6 | Développer sans détruire : construire chunks, HTML paginé et Markdown depuis le document développé (natif + recette), étendre la recette aux `pdf_supplement`, faire déclarer son origine à chaque contenu, et épingler dans chaque export les empreintes du natif et de la recette. | À recette vide, le développé est identique au natif (test d'identité). Le développé se reconstruit depuis natif + recette à l'empreinte près (test de reproductibilité). Un contenu de chunk sans origine déclarée est refusé (contre-exemple en test). L'export réel des 37 livres publie les comptages par origine. L'HTML paginé et le Markdown servis par l'interface proviennent du développé, suppléments inclus, et un supplément y est visiblement démarqué comme dérivé — un test le prouve. Aucun signal commercial n'entre dans le texte dense. | terminé |
| 7.1 | Sélectionner, figer et construire la ligne de base de récupération lexicale+dense sans a priori de source. | Un contrat de run porte la révision du code exécuté et les empreintes du manifeste, du registre, de l'export de chunks, de l'index et du jeu de questions avec ses jugements. Il épingle aussi la révision de l'encodeur dense, l'analyseur lexical, le moteur et sa version, les paramètres d'index, les valeurs de `k`, la normalisation et la règle de fusion. Toute nouvelle dépendance est justifiée par un essai ciblé. Tous les documents inclus peuvent produire des candidats ; la popularité absente n'est ni zéro ni exclusion. Les scores et rangs des deux voies, puis leur fusion, restent observables séparément. | à faire |
| 7.2 | Évaluer séparément l'adéquation temporelle, l'autorité de domaine, puis une éventuelle popularité Google Books. | Une ablation appariée avant/après est publiée pour chaque signal sur les strates de l'étape 7, avec intervalles d'incertitude et protocole figé avant le run. La pertinence du passage reste dominante ; aucun signal n'est activé sans satisfaire les seuils ci-dessous et sans contre-exemple montrant qu'une pépite reste récupérable. | à faire |

### Protocole d'évaluation des signaux

Chaque strate utilisée pour autoriser un signal contient au moins dix questions
jugées. Les questions peuvent porter plusieurs étiquettes, mais les effectifs et
leurs intersections sont publiés : `timeless`, `time_sensitive`,
`current_source_required`, `with_identifier`, `without_identifier`, `popular`
et `little_known`. Un résultat sur une strate plus petite reste exploratoire et
ne peut pas activer le signal.

La métrique principale de classement est nDCG@10 ; hit@10 mesure la couverture
et MRR la position du premier passage pertinent. Avant chaque ablation, le
protocole fige l'effet minimal attendu et la régression maximale admise. Les
valeurs initiales sont un gain d'au moins 0,02 nDCG@10 sur les strates ciblées,
aucune baisse de hit@10 et au plus 0,01 de baisse nDCG@10 sur chaque strate non
ciblée. Le rapport publie aussi l'intervalle de confiance à 95 % du delta par
rééchantillonnage apparié. Si l'effectif ou l'incertitude ne permet pas de
conclure, le signal reste désactivé au lieu d'être qualifié par intuition.

### Politique de récupération

La génération de candidats est toujours l'union des voies lexicale et dense,
sans filtre d'autorité, d'âge ou de popularité. Les filtres durs sont réservés
aux contraintes explicites de la question et aux champs fiables, par exemple la
langue ou une période demandée.

Le reclassement distingue la pertinence du passage, la qualité de sa preuve,
l'adéquation temporelle à la question et l'autorité dans le domaine demandé.
Une popularité évaluée ultérieurement reste un signal faible et ne compense
jamais une faible pertinence. L'absence de fournisseur vaut `unknown` et conserve
le candidat à égalité sur ce signal.

La fraîcheur dépend de l'intention : une question intemporelle n'applique aucune
décote automatique ; une question de microstructure, réglementation, coûts ou
technologie peut privilégier une révision récente ; une question explicitement
actuelle ne peut pas être satisfaite par le seul corpus de livres et doit rendre
cette insuffisance observable.

Une diversification par source et par auteur est évaluée comme stratégie de
classement avant toute activation. Une source méconnue peut être présentée sur
la seule force d'un passage pertinent et prouvé ; son manque de popularité ne
déclenche ni décote ni demande de corroboration. Seuls la faiblesse de la preuve
ou un statut éditorial non revu peuvent justifier une corroboration indépendante.

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
- Une métadonnée externe ne modifie jamais l'identité du PDF, sa décision
  d'inclusion ni l'autorité du contenu source. Une divergence reste visible.
- Il n'existe aucune décote universelle liée à l'âge, aucun score global
  d'autorité et aucun filtre de popularité. Ces signaux dépendent de la question
  et restent désactivés tant que les evals ne prouvent pas leur apport.
- L'absence d'un fournisseur ou d'une métadonnée est un état explicite. Elle ne
  vaut ni zéro, ni faible qualité, ni autorisation de choisir une autre valeur
  sans le signaler.

## Preuves à reporter avant clôture

- le manifeste du corpus, son script de vérification et le journal des
  décisions (doublons, scans, conservation) ;
- les identifiants des runs d'audit de l'étape 2, le rapport de couverture
  agrégé et l'histogramme des refus qui fonde la feuille de route de
  généralisation ;
- le schéma du contrat de chunks, l'export réel et ses comptages par drapeau ;
- le registre versionné des sources, le rapport de résolution des 38 documents
  et les preuves de revue des correspondances non exactes ;
- les résultats de base des trois bancs avec les révisions exactes des modèles
  mesurés ;
- la ligne de base hit@k, MRR et nDCG@k des evals de récupération et les
  ablations séparées de l'adéquation temporelle, de l'autorité de domaine et de
  toute popularité candidate ;
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

- Étape 2 : les 38 documents retenus sont mesurés — 37 qualifiés, et un échec
  d'exécution documenté avec son constat exact : « Pipeline VlmPipeline failed »
  de docling-serve à l'assemblage, après conversion complète des 365 pages,
  reproduit cinq fois sur les deux convertisseurs (l'API traduit ce crash en
  404, ce qui avait d'abord masqué la cause). Le rapport committé comprend `coverage.json` (agrégat rejouable,
  histogrammes et partition par famille de levier via `lever_partition`),
  `coverage-report.md` (chiffrage) et `coverage-sample.json` (échantillon
  audité de 90 régions, rejouable depuis ses coordonnées).
- Chiffrage des leviers : preuve PDF seule 2 525 régions (93 % de vraies
  mathématiques sur échantillon, gain 1 800–2 350) ; transcription Docling
  seule 1 003 régions (47 %, gain ≈ 470, cible du témoin Nougat) ; mixtes
  1 306 (gain ≈ 610 conditionné aux deux leviers). Le support des polices est
  le levier dominant et fonde la tranche suivante de généralisation.
- Pendant la mesure, un défaut majeur de la revue d'août a été corrigé sur
  preuve réelle : les exceptions fontTools font désormais une exclusion
  localisée (`embedded_font_not_interpretable`) au lieu d'abattre la
  qualification — trois livres (768 pages) récupérés, mutation testée.
- Deux corrections des seuils de promotion de polices ont été tentées puis
  réfutées : l'une par l'oracle du gate (rappel 0,774 < 1,0), l'autre par
  contrôle visuel (48 régions conformes détruites sur le document 22 — α, ε,
  ζ, β et équations complètes). Le finding est consigné avec son ampleur
  mesurée (≈ 1 300 fausses régions, ~15 % du total, hétérogènes) ; sa
  correction exige un refactor de portée, hors de cette tranche.
- La mesure a été distribuée sur deux convertisseurs à pile identique
  (garde `require_identical_versions`, noyau hôte exclu de la comparaison) ;
  configuration retenue après mesure : 1 worker et 12 CPU par machine, le
  parallélisme intra-GPU ayant été mesuré contre-productif. Une panne d'un
  convertisseur remet le livre en file (`ConverterUnreachable`) au lieu de le
  condamner — défaut découvert par un redémarrage réel, corrigé et testé.

- Étape 3, contrat et projection : le
  contrat de chunks est implémenté et documenté
  (`docs/rag/chunk-contract.md`, schéma version 1 ;
  `qualification/corpus_reference/chunks.py`, 13 tests dont le contre-exemple
  de refus exigé). Les drapeaux suivent le champ `verdict` du pipeline — la
  revue contradictoire a démontré que `candidate_status` seul laissait une
  région `missing` (verdict `contradicted`) passer pour non vérifiée, avec un
  cas réel dans l'export. La règle `proven` est fondée sur mesure : sur les 37
  livres, 93 formules portent des preuves conformes sans contradiction — 23 à
  couverture exactement 1,0, aucune entre 0,55 et 1,0, 70 en dessous — donc
  `proven` exige la couverture intégrale ; `corroborated` n'est jamais émis en
  attendant l'étape 6. La boîte de citation exige le contenement du span
  (un chevauchement partiel issu de l'appariement naïf des dollars citerait de
  la prose), porte sa `precision`, et les items du corps sans localisation
  (artefacts Kindle) gardent leur texte ou sont consignés `unlocatable_items` —
  quatre livres réels que l'exporteur faisait planter passent désormais.
  Export réel des 37 livres qualifiés, zéro échec : 4 919 formules —
  4 806 `unverified`, 90 `contradicted`, 23 `proven`. Crops de citation
  vérifiés visuellement pour les trois drapeaux émis.

- Sous-étape 3.0 : la frontière du corpus est rétablie — `docs/corpus_reference/`
  ne contient plus que le manifeste et les PDF ; `manifest verify` refusait
  réellement les quatre fichiers étrangers avant le déplacement et rend zéro
  écart après. Les artefacts de couverture vivent dans `docs/corpus_coverage/`
  (producteur et références mis à jour), le contrat de chunks dans
  `docs/rag/chunk-contract.md`. L'agrégat se régénère au nouvel emplacement.

- Sous-étape 3.1 : le registre versionné est publié sous `docs/source_catalog/`.
  Le validateur refuse une valeur bibliographique sans preuve, une note sans
  nombre de votes, un rang sans marché/catégorie/instant et une date d'édition
  copiée comme date de révision. La politique de persistance ne conserve pas la
  réponse brute Google Books.

- Sous-étape 3.2 : `qualification.source_catalog` fournit les commandes
  `build`, `enrich`, `review` et `verify`, avec le client Google Books de la
  bibliothèque standard et un délai explicite. Les tests couvrent ISBN exact,
  ambiguïté, absence, réponse invalide et indisponibilité. L'appel réel du
  7 août 2026 a été exécuté sur le corpus mais Google Books a répondu HTTP 429 ;
  cet état reste `unavailable`, jamais `no_match`.

- Le pont d'accès ne duplique pas le secret : `rails runner` déchiffre
  `google_books.api_key` et lit facultativement `google_books.email`, puis le
  Python ne conserve la clé qu'en mémoire. Le chemin réel a confirmé la
  présence des deux champs sans afficher la clé. Une sonde réelle a ensuite
  obtenu `200 OK` sans variable d'environnement Python.

- Sous-étape 3.3 : les 38 documents retenus sont consultés, aucun ne reste
  indisponible. `docs/source_catalog/enrichment-report.json` publie
  32 consultations `succeeded`, 6 `no_match`, 0 `unavailable`, et les
  résolutions 23 `accepted`, 0 `ambiguous`, 0 `candidate`, 9 `rejected`,
  6 `no_match`. Il distingue 31 documents avec ISBN détecté, 7 sans identifiant
  et 25 avec plusieurs ISBN ; aucun document n'est supprimé.
- La reprise après indisponibilité est ciblée : `enrich --only-unresolved` ne
  consulte que les entrées sans consultation aboutie. Le défaut a été découvert
  sur le chemin réel — une re-consultation complète des 38 documents a été
  limitée en débit par Google Books et a dégradé l'état committé (16
  `unavailable` et 6 acceptations contre 1 et 22), état restauré par git. La
  reprise ciblée a ensuite résolu `understanding-hedged-scale-trading.pdf` par
  ISBN exact (Thomas McCafferty, McGraw Hill Professional, édition 2001).
- Le rapport ne décrit plus une passe mais l'état du registre
  (`summarize_catalog`) : il reste complet quel que soit le périmètre consulté
  et se régénère sans réseau. Cinq définitions changent et la version de schéma
  reste 1 : les six consultations `no_match` apparaissent comme telles au lieu
  d'être comptées `succeeded` ; `candidate_count` compte les candidats observés
  et non la liste retenue par le résolveur (39 au lieu de 37) ; la liste
  `documents` couvre les 38 entrées et non les seules consultées ; `observed_at`
  date le résumé et non les observations, qui portent chacune la leur ; les
  champs `reviewed`, `accepted_candidate_id` et `accepted_proof` sont ajoutés
  pour que le rapport relie lui-même chaque acceptation à sa preuve. La
  dérivation corrige au passage un chiffre faux du rapport précédent, qui
  annonçait 15 candidats rejetés là où le registre en portait 14.
- Tous les états du contrat sont publiés, `not_queried` et `expired` compris :
  un test vérifie que la somme des consultations égale le nombre de documents,
  de sorte qu'aucun document ne puisse disparaître d'un total sans signal.
- La revue des candidats non exacts est une donnée rejouable
  (`qualification/source_catalog/candidate_review.py`), pas un geste manuel.
  `bear-market-trading-strategies.pdf` en est le cas réel : la page de titre
  prouve l'œuvre et l'auteur (`#/texts/3`, `#/texts/5`) ainsi que la mention
  `2ND EDITION` (`#/texts/4`), alors que le volume Google Books de Matthew R.
  Kratter porte l'édition de 2018 et l'autre candidat un ouvrage différent. Les
  deux candidats sont donc rejetés — accepter le premier aurait attaché une date
  d'édition 2018 à une seconde édition — et le titre et l'auteur restent inscrits
  avec leur preuve `source_text`, sans date d'édition inventée. La revue refuse
  de surclasser une correspondance prouvée par identifiant, de nommer un candidat
  non observé ou d'accepter deux éditions.
- La revue contradictoire en contexte vierge a corrigé cinq défauts du premier
  jet, tous couverts par un contre-exemple : une acceptation par revue rendait
  la seconde exécution impossible (garde aveugle à sa propre décision) ; elle
  écrasait la preuve fournisseur du candidat, si bien qu'une date d'édition se
  serait retrouvée prouvée par la décision elle-même au lieu de sa notice ; une
  revendication de titre ou d'auteur n'était reliée à aucune des preuves citées
  et pouvait donc être inventée ; l'échec « une seule édition » survenait après
  avoir déjà écrit deux candidats acceptés ; et le résumé omettait `not_queried`,
  ce qui faisait disparaître des documents du total sans le signaler.

- Sous-étape 3.4 : les 38 entrées sont datées et portent soit `reviewed`, soit
  `not_assessable` avec une raison. Trois revues locales servent d'échantillon
  contradictoire (`classic_still_relevant`,
  `dated_context_requires_current_validation`, `little_known_relevant`) ;
  aucune n'est transformée en score d'autorité global.

- Sous-étape 3.5 : l'export réel regénère 15 530 chunks sur 37 artefacts
  Docling disponibles, tous avec `source_sha256`, la version et l'empreinte de
  l'entrée du registre, les dates et la revue éditoriale. Les observations
  commerciales restent hors projection et hors texte dense.

- Sous-étape 3.6 : l'export réel des 37 livres passe sans aucun échec en 57 s et
  publie ses comptages par origine — 95 242 `transcription`, 789
  `pdf_supplement`, 0 `correction` sur 15 547 chunks, pour 789 opérations de
  recette et 207 items sans localisation consignés. Les corrections restent à
  zéro parce que la mesure du corpus tourne en mode audit, sans Gemma : la
  recette n'y porte donc que des suppléments. Chaque en-tête épingle
  `native_document_sha256` et `recipe_sha256`, et refuse un export dont le
  rapport annonce une autre empreinte. Les drapeaux de formule deviennent
  5 595 `unverified`, 90 `contradicted` et 23 `proven` : les suppléments
  ajoutent des formules prouvées au niveau des glyphes mais explicitement non
  vérifiées sémantiquement, jamais promues.
- Les preuves manquantes de 3.6 ont été ajoutées après la revue contradictoire,
  qui a montré qu'aucun test ne portait la reproductibilité exigée mot à mot :
  le développé se reconstruit désormais depuis le seul couple natif + recette et
  revient à l'empreinte près, une recette différente rendant un tirage différent.
  Les deux gardes d'export qui refusent un rapport annonçant une autre empreinte
  de natif ou de recette étaient elles aussi sans test ; elles en ont un.
  Côté interface, la branche qui sert le Markdown développé n'était pas
  exercée : un test du contrôleur prouve maintenant qu'elle sert le développé au
  lieu de rediriger vers le Markdown natif, et que le supplément y reste
  démarqué. Rails : 45 tests, 449 assertions, 0 échec.

## Limites connues

- Douze documents retenus n'embarquent aucune police sur les pages
  échantillonnées, dont six conversions calibre EPUB→PDF. Leur pagination n'est
  pas celle de l'ouvrage imprimé : la provenance de citation de l'étape 3 devra
  en tenir compte.
- Le corpus n'existe que dans l'arbre de travail. `git clean -xd` le supprimerait
  et le manifeste ne permet pas de le reconstituer ; une copie hors dépôt reste
  à la charge du développeur.
- Google Books limite le débit : une consultation complète des 38 documents
  n'est pas rejouable à volonté. `enrich --only-unresolved` protège l'état
  acquis, mais une reconstruction depuis un registre vide resterait exposée à
  cette limite et devrait être étalée.
- Le PDF retenu de liquidité systémique ne possède pas encore d'artefact
  `DoclingDocument`, donc il n'entre pas dans l'export de chunks et reste
  observable dans le manifeste. L'export porte donc 37 livres sur 38.
- La revue éditoriale de 3.4 est une dérivation déterministe rejouée par
  commande, pas une lecture humaine document par document ; son réviseur et sa
  date décrivent la campagne. Seule l'entrée dont la résolution a changé a été
  modifiée lors de la reprise ; les 37 autres restent identiques. Conséquence
  visible : `understanding-hedged-scale-trading.pdf` porte une revue datée du
  7 août alors que la notice qui la fonde a été consultée le 8 — la date est
  celle de la campagne, pas de la lecture, et le registre ne les distingue pas.
- La démarcation visible d'un supplément est prouvée par les chaînes et le CSS
  produits, non par un contrôle à l'œil du rendu final dans un navigateur.
- L'onglet reste intitulé « HTML corrigé » alors que le développé du corpus ne
  porte aujourd'hui que des suppléments et aucune correction.
