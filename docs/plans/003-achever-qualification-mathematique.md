# Achever la qualification mathématique

Ce fichier est l’autorité d’exécution de cette tranche. Une qualification réussie,
des tests verts ou une revue du seul diff ne suffisent pas à déclarer la tranche
terminée. Elle est terminée uniquement lorsque les six lignes ci-dessous portent
le statut **terminé** avec la preuve indiquée.

| Étape | Prescription | Condition de complétude | Statut |
|---|---|---|---|
| 1 | Présenter séparément l’exécution, la couverture PDF, le verdict sémantique et l’intégrité HTML. | L’interface et le rapport exposent les quatre axes sans assimiler `succeeded` à un document valide. Un test Rails couvre cette distinction. | terminé |
| 2 | Localiser toute exclusion PDF au lieu d’invalider silencieusement une page entière, et supprimer la dépendance sémantique au nom des polices. | Chaque exclusion conserve la ressource, la raison, les opérations PDF concernées, les indices de glyphes absents et une boîte conservatrice. Une région intersectée reste non vérifiable ; les exclusions police et XObject se cumulent. Les exclusions impossibles à localiser restent explicitement à l’échelle de la page. La détection mathématique repose sur les glyphes, Unicode, les attributs rendus et la géométrie ; renommer une police ne change aucun candidat. | terminé |
| 3 | Qualifier le HTML statiquement et dans un vrai navigateur. | L’audit statique contrôle toutes les pages, ancres, images et formules. Un smoke test navigateur reproductible vérifie le débordement et la coupure des MathML ; une formule large défile dans son propre conteneur sans élargir ni couper son parent. | terminé |
| 4 | Relier une région mathématique PDF à son élément Docling puis à son nœud HTML. | Le rapport publie pour chaque région liée une identité DOM stable. L’audit échoue si une région prouvée et liée n’a pas exactement un nœud `<math>` correspondant dans la bonne page, ou si ce nœud est dupliqué. Les simples comptages par page restent un contrôle secondaire. | terminé |
| 5 | Étendre les primitives PDF uniquement après mesure de leur gain. | `Tr`, CID/GID et Form XObject sont évalués séparément sur le document 22. Une primitive n’entre en production que si elle rend au moins une région supplémentaire vérifiable sans fallback. Sinon, le résultat mesuré et la décision de non-implémentation sont consignés ici. | terminé |
| 6 | Vérifier le résultat complet. | Fixtures positives et contre-exemples, tests rapides compatibles `xdist`, absence de régression des régions déjà prouvées, qualification réelle du document 22, puis contrôle navigateur des pages 9, 52, 62 et 75. Le bilan final recoupe chaque ligne de ce fichier avec sa preuve. | terminé |

## Contraintes invariantes

- La donnée PDF et le `DoclingDocument` natif restent les autorités conservées.
- Aucune limitation n’est transformée en succès par fallback ou heuristique non
  prouvée.
- Aucun moteur ou dépendance lourde n’est ajouté sans gain démontré et
  proportionné.
- Une anomalie de rendu n’altère pas le verdict sémantique : elle possède son axe
  d’intégrité propre.
- Le nom `/BaseFont` ou le nom rendu peut servir à relier une ressource PDF à sa
  trace, jamais à décider qu’un contenu est mathématique. Les rôles sont déduits
  des caractères effectivement décodés, des noms de glyphes, des attributs
  rendus et de leur géométrie. Un test métamorphique renomme les polices sans
  modifier les régions détectées.

## Preuves à reporter avant clôture

- identifiant et synthèse de la qualification réelle finale ;
- résultat des tests Python, Rails et navigateur avec leur durée ;
- pages contrôlées visuellement et automatiquement ;
- mesure marginale de chaque primitive PDF ;
- résultat de la revue contradictoire portant explicitement sur l’adhérence aux
  six étapes.

## Preuves acquises

- Les exclusions de police et de XObject publient désormais leurs indices
  d’opérations et de glyphes ; les tests Python et Rails refusent les formes
  incomplètes. Les indices d’une police non décodée sont conservateurs : ils
  désignent les emplacements d’octets potentiellement absents, pas des glyphes
  faussement décodés.
- Le chemin réel d’une page composée uniquement d’une police non supportée
  conserve maintenant la ressource, les opérations, les indices et une boîte
  d’exclusion, même si le statut de la page reste `unsupported`. Une police
  partiellement interprétable est retirée en entier de la preuve plutôt que de
  conserver des glyphes sélectifs trompeurs.
- Le test métamorphique renomme toutes les polices sans changer les 53 régions
  du PDF de référence. La résolution sémantique utilise le mapping du glyphe
  embarqué et la concordance GID, jamais une famille ou un nom de police.
- Chaque MathML porte `data-docling-ref` et `data-docling-charspan`. L’audit
  `region_links` exige une occurrence dans `page-N` et couvre les cas présents,
  absents et dupliqués. Une région déclarée liée sans ces deux identités
  échoue explicitement avec `linked_math_identity_missing`. Il refuse aussi un
  charspan qui ne désigne pas exactement le texte candidat dans le nœud Docling.
- Une formule Docling non sérialisable n’est plus exposée sous forme de LaTeX
  brut : l’HTML paginé reproduit son crop PDF exact et l’audit conserve la limite
  `formula_rendered_from_pdf_source`.
- Qualification 73 : `Tr` apparaît sur 17 pages et permet d’y conserver 58
  régions vérifiables, dont 55 conformes et 3 contradictoires. Sa prise en
  charge est conservée avec un contre-exemple `Tr 8`.
- Qualification 73 : les flux `CIDToGIDMap` sont présents dans 91 ressources de
  91 pages, mais aucune région mathématique vérifiable ne dépend de ces flux.
  Leur prise en charge n’est donc pas conservée ; ils redeviennent des exclusions
  localisées `cid_to_gid_stream_not_qualified`. Type0 avec mapping identité reste
  supporté.
- Les trois Form XObject de la page 1 ne contiennent que des rectangles
  vectoriels et leurs `/BBox` sont inversées. Leur normalisation n’a créé aucune
  région mathématique et a seulement déplacé la page vers une ambiguïté de
  rendu ; cette modification n’est donc pas conservée.
- La qualification 76 reproduit le PDF réel de cinq pages qui dépassait la
  limite de rapport. Après sérialisation compacte et plages d'indices
  réversibles, elle réussit avec un rapport de 1 838 554 octets au lieu d'un
  préfixe tronqué à 33 554 432 octets.
- La qualification 78 du document 22 réussit avec 344 régions : 185 conformes,
  9 contradictoires et 150 non vérifiables. Son rapport complet mesure
  3 603 172 octets. Les deux formules Docling non sérialisables de la page 75
  sont rendues depuis leurs crops PDF exacts ; aucun LaTeX brut ni dollar
  visible ne subsiste sur cette page.
- L'audit navigateur de la qualification 78 parcourt les 92 ancres et ne trouve
  aucun dollar visible. Les seuls blocs `pre` sont deux extraits de code Python
  légitimes de la page 78. Douze pages ont été observées visuellement : 1, 9,
  18, 27, 36, 45, 54, 63, 72, 75, 81 et 90. La page 36 expose une répétition de
  prose déjà présente dans le `DoclingDocument` natif ; elle reste une limite
  de conversion Docling, distincte de la qualification mathématique.
- La revue contradictoire a démontré deux contrats Rails permissifs. Ils sont
  maintenant fermés : une page `unsupported` portant une raison de police doit
  conserver ses exclusions localisées, et `html_integrity.pages` doit décrire
  exactement toutes les pages. Les contre-exemples correspondants sont des
  tests Rails. Les exclusions répétées d'une même police sur plusieurs lignes
  restent légitimes et couvertes par un test positif.
- Les dollars monétaires `M$` et `$5` ne perturbent plus une formule `$x_i$`
  adjacente. Les délimiteurs `(]` et `[)` sont refusés. Le test du rendu source
  compare désormais le PNG produit au pixmap de la provenance exacte, sans
  marge ajoutée.
- La qualification réelle finale 81 du document 22 réussit avec un rapport de
  3 603 172 octets. Elle conserve 344 régions : 185 conformes, 9 contradictoires
  et 150 non vérifiables. La couverture reste 89 pages partielles et 3 pages
  non supportées. L'intégrité HTML reste explicitement `failed`, donc le succès
  d'exécution ne masque pas ses anomalies.
- Le contrôle navigateur de la qualification 81 vérifie les pages 9, 52, 62 et
  75 : aucun dollar visible ni fallback LaTeX brut. La page 62 contient deux
  MathML ; la page 75 contient sept MathML et deux crops PDF source. Les deux
  formules du bas de la page 75 ont été extraites du DOM et contrôlées
  visuellement.
- La revue contradictoire finale a ajouté trois contre-exemples : une identité
  de formule dont le charspan ne correspond pas au texte candidat, une page
  HTML `passed` dont les inventaires attendu et rendu divergent, et une raison
  de police sans `font_resource`. Les trois rapports sont maintenant refusés.
- La qualification réelle 84 du document 22 passe ce contrat renforcé avec un
  rapport de 3 608 520 octets. Elle conserve les mêmes 344 régions et expose
  toujours honnêtement `contradicted` et `html_integrity: failed`. Dans le
  navigateur, la page 75 du HTML paginé contient sept MathML, deux reproductions
  exactes depuis le PDF source et aucun bloc de fallback LaTeX brut.
- Le dernier renforcement recoupe la liste complète des régions évaluables liées
  avec `region_links`, la cohérence entre le statut de chaque page et ses
  anomalies, ainsi que la présence effective des indices d'opérations et de
  glyphes pour chaque exclusion de police. La logique de liaison DOM est isolée
  dans une unité de 95 lignes ; l'audit HTML principal reste à 212 lignes.
- La qualification réelle 87 du document 22 passe ce contrat avec un rapport de
  3 608 520 octets. Elle conserve le verdict `contradicted` et expose
  `html_integrity: failed`, 92 pages contrôlées, 182 anomalies et 194 liens de
  régions. Sur la page 75, le navigateur compte sept MathML, deux reproductions
  exactes depuis le PDF source, aucun fallback LaTeX brut, aucun dollar visible
  et aucun fragment `\\begin{...}` visible. Le contrôle visuel du bas de page
  confirme la matrice gaussienne composée sans doublon LaTeX.
- La revue contradictoire suivante a trouvé deux défauts supplémentaires : le
  locus d'une correction acceptée restait exprimé dans les coordonnées du texte
  natif, et Rails ne recoupait que l'identifiant d'une région avec son lien DOM.
  Le document dérivé publie maintenant le `docling_ref` et le charspan réellement
  matérialisés ; l'audit exige aussi le `data-correction-id`. Rails recoupe page,
  référence, charspan candidat et sélecteur DOM, et refuse une anomalie rattachée
  à une page inexistante. Les contre-exemples sont conservés comme tests.
- La qualification réelle 89 du document 22 passe le contrat renforcé avec le même
  rapport de 3 608 520 octets. Ses neuf propositions sont rejetées explicitement
  et aucune correction n'est appliquée ; le test unitaire combiné couvre donc en
  plus le chemin d'une correction acceptée jusqu'à l'audit du DOM dérivé. Le
  contrôle navigateur de la page 75 confirme sept MathML, deux reproductions PDF
  exactes, aucun fallback LaTeX brut, aucun dollar visible et aucun fragment
  `\\begin{...}` visible.
- Une dernière contre-revue a démontré qu'un `dom_charspan` arbitraire restait
  acceptable si son faux sélecteur répétait la même valeur. Rails recoupe
  désormais ce locus avec le texte du `DoclingDocument` natif ou dérivé et tient
  compte du déplacement produit par chaque correction antérieure. Toute
  correction acceptée doit publier son `derived_docling_ref` et son
  `derived_charspan`. Deux tests couvrent une correction complète et une formule
  inline non modifiée mais déplacée.
- La qualification réelle finale 91 du document 22 réussit avec un rapport de
  3 608 520 octets, 92 pages contrôlées et 194 liens. Son verdict reste
  honnêtement `contradicted`, l'intégrité HTML reste `failed` avec 182 anomalies,
  et les neuf propositions sont explicitement rejetées. Le contrôle navigateur
  final de la page 75 confirme encore sept MathML, deux reproductions PDF exactes,
  aucun fallback LaTeX brut, aucun dollar visible et aucun `\\begin{...}` visible.
- La contre-revue finale confirme la fermeture de ses deux findings sans nouveau
  contre-exemple reproductible. Elle a rejoué 51 tests Rails et 187 assertions,
  ainsi que le test Python combinant génération dérivée et audit du locus.
- Le smoke test système convertit réellement le PDF de cinq pages puis vérifie
  dans Chromium la synchronisation des formats et l'isolation du débordement.
  Son élément MathML volontairement large isole de façon déterministe la règle
  CSS ; la preuve que le pipeline réel produit le rendu final est distincte et
  portée par la qualification 81 et son contrôle navigateur.
- Validation finale : 380 tests Python passent sous `xdist` en 13,19 s ; un
  seul test sans rapport avec cette tranche reste rouge à cause de l'empreinte
  historique incohérente de `qualification/math_audit/results/docling-response.json`.
  Ruff est vert. Rails passe 163 tests et 876 assertions en 8,43 s. Le test
  système réel passe avec 26 assertions en 123,95 s.
