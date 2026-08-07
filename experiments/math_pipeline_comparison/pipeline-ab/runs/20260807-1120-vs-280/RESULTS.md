# A/B du pipeline mathématique — 280 contre 1120 tokens visuels

## Verdict

Le passage de `max_soft_tokens=280` à `1120` n'apporte aucun gain observé sur
le chemin réel testé. Les deux bras produisent exactement les mêmes corrections
matérialisées : 33 cibles acceptées, 3 rejetées, aucun échec et deux sélections
Gemma prouvées par la source sur trois appels vision.

Le profil 1120 consomme 3 456 tokens de prompt par qualification, contre 964
pour 280, soit +258,5 %. Sa médiane de bout en bout est 6,272 s, contre 6,032 s
pour 280, soit +4,0 %. Les `DoclingDocument`, Markdown et HTML dérivés sont
bit à bit identiques entre les deux bras.

## Protocole

- PDF figé : `source-pages-7-10.pdf`, SHA-256
  `219c2064ba9292d286f4b3bcc65eb9e94b418705c51b9f98f54f2ad70321ddf1`.
- DoclingDocument figé : `docling-subset-document.json`, SHA-256
  `a1a6fea517971cee7771417610db9ae619a6996516f81bb1028067c77d6104fe`.
- Même service `pdf_math_audit`, même modèle
  `google/gemma-4-26B-A4B-it`, crops 600 dpi et température nulle.
- Un run d'échauffement exclu, puis trois runs mesurés par bras.
- Le bras 1120 a été rejoué après restauration du conteneur afin de neutraliser
  l'effet d'ordre.

| Mesure | 280 | 1120 | Écart |
|---|---:|---:|---:|
| Runs mesurés | 3 | 3 | — |
| Durées (s) | 5,870 · 6,160 · 6,032 | 6,272 · 6,204 · 6,283 | — |
| Moyenne (s) | 6,021 | 6,253 | +3,9 % |
| Médiane (s) | 6,032 | 6,272 | +4,0 % |
| Tokens de prompt par run | 964 | 3 456 | +258,5 % |
| Tokens de complétion par run | 48 | 51 | +6,3 % |
| Cibles acceptées | 33/36 | 33/36 | identique |
| Cibles rejetées | 3/36 | 3/36 | identique |
| Échecs | 0 | 0 | identique |
| Appels vision | 3 | 3 | identique |
| Sélections `vision_proven_by_source` | 2 | 2 | identique |

## Résultat produit

Les trois sorties dérivées stables ont les mêmes empreintes dans tous les runs
mesurés des deux bras :

| Artefact | SHA-256 |
|---|---|
| DoclingDocument dérivé | `bc5e8092d04ff838fa6e1c75be6077f81cf58242e55b9c836d2e211c86f76079` |
| Markdown dérivé | `722ce80cb099cee1cc27fcefb16d793b512f1265002b3fab4ee6160934197c3a` |
| HTML dérivé | `5bace6e491a667810ba6c56d1abb0b77bbd1ebe6ed3ad80040f46e9ac8446d47` |

Les trois crops vision sont eux aussi bit à bit identiques entre les bras. Les
cibles `pdf-source:2:840` et `pdf-source:2:1173` sont acceptées exactement dans
tous les runs. La cible `pdf-source:2:449`, dont le crop dessine `\mathbf{wx}-b=0,`,
reste rejetée dans les runs mesurés :

- 280 propose `wx-b=0,` et perd le gras ;
- 1120 propose `\mathbf{WX}-b=0,` et transforme les minuscules en majuscules.

Le warmup 280 a produit une fois `\mathbf{wx}-b=0,` et accepté cette troisième
cible vision. Cette observation non reproduite est conservée, mais elle ne fait
pas partie des mesures préchauffées et ne prouve pas une supériorité de 280.

Les lettres visuellement ambiguës sont bien des minuscules dans le programme du
PDF : `w` est le code `0x77`, le glyphe CFF `w` et l'Unicode rendu `w` ; `x` est
le code `0x78`, le glyphe CFF `x` et l'Unicode rendu `x`. Les deux glyphes
proviennent de `LMRoman10-Bold`. Des majuscules auraient les codes `0x57` et
`0x58`. Le rejet de `\mathbf{WX}` est donc conforme à la source.

## Identité des runtimes

- 280 : image NVIDIA
  `sha256:581f653cd3f1d4d161fcb9926be5b35adc199177b4e8eaaacb001779f03c03a1`,
  `processor_config.json` annonce `max_soft_tokens: 280`.
- 1120 : image dérivée
  `sha256:d407711cfe5572be6050ac8b65cc44ef14c308b5831de8923388bc67a192e181`,
  `/opt/nim/fallback.yaml` a le SHA-256
  `0a5bc3ad21d0e4177299871081dcc79cceeefe7f853b9ad325404acec4dca2e1`
  et fixe `mm_processor_kwargs.max_soft_tokens: 1120`.
- Les cold starts observés sont 471,8 s pour 280 et 472,8 s pour la restauration
  de 1120. Ils sont exclus des latences de qualification.
- À la fin de l'expérience, le conteneur 1120 est restauré et prêt.

Les identités ne reposent pas seulement sur les arguments du harnais. Les
preuves [`runtime-280.json`](runtime-280.json) et
[`runtime-1120.json`](runtime-1120.json) ont été capturées directement par
`docker inspect` et `docker cp`, sans conserver l'environnement du conteneur.
Pour 280, l'intervalle Docker
`2026-08-07T21:51:39.595604121Z`–`2026-08-07T22:02:21.047707477Z`
encadre les quatre runs. Pour 1120, le démarrage
`2026-08-07T22:02:21.618832866Z` précède les quatre runs post-restauration.
Le harnais exige désormais cette preuve et refuse un
`effective_max_soft_tokens` différent du bras demandé.

## Limites

Le chemin est réel mais l'échantillon reste petit : deux pages, 36 cibles et
seulement trois appels Gemma par qualification. Ce résultat suffit à montrer
l'absence de gain sur ce document et le surcoût en tokens ; il ne mesure pas un
corpus étendu de petites formules inline. L'export RAG actuel ne consomme pas le
document corrigé par Gemma, donc aucun bénéfice d'indexation direct n'est testé.
