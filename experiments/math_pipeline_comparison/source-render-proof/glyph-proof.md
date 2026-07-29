# Traçabilité structurelle des glyphes texte PDF

- PDF : `source-pages-7-10.pdf`
- SHA-256 : `219c2064ba9292d286f4b3bcc65eb9e94b418705c51b9f98f54f2ad70321ddf1`
- Verdict : **TRAÇABILITÉ_STRUCTURELLE_COMPLÈTE**

Ce verdict signifie que chaque code texte sélectionne un CharString CFF et que MuPDF rend le même GID. Il ne signifie pas que l'Unicode ou l'apparence raster de chaque glyphe est prouvé.

## Couverture

| Page | Codes source | CFF | GID conformes | Unicode trace = AGL | Associations rawdict |
|---:|---:|---:|---:|---:|---:|
| 1 | 2161 | 2161 | 2161 | 2161/2161 | 2161 |
| 2 | 1927 | 1927 | 1927 | 1907/1927 | 1927 |
| **Total** | **4088** | **4088** | **4088** | **4068/4088** | **4088** |

Les caractères supplémentaires de `rawdict` sont des espaces de regroupement synthétiques ; ils ne sont pas comptés comme codes PDF.

## Bilan Unicode

- `ToUnicode` absent : **4067** occurrences ;
- `ToUnicode` conforme à AGL : **0** occurrences ;
- `ToUnicode` en conflit avec AGL : **21** occurrences ;
- Unicode MuPDF en conflit avec AGL : **20** occurrences.

## Conflits ToUnicode

| Page | Police | Code | Glyphe CFF | ToUnicode | AGL | Occurrences |
|---:|---|---|---|---|---|---:|
| 2 | `/Ty16` | `0x21` | `/ff` | U+0000 | U+FB00 | 1 |
| 2 | `/Ty18` | `0x21` | `/minus` | U+2260 | U+2212 | 10 |
| 2 | `/Ty21` | `0x21` | `/asteriskmath` | U+00FA | U+2217 | 8 |
| 2 | `/Ty18` | `0x22` | `/greaterequal` | U+00D8 | U+2265 | 1 |
| 2 | `/Ty18` | `0x23` | `/lessequal` | U+00C6 | U+2264 | 1 |

## Preuve `x_k`

Le `k` est le code `0x6b` de `/Ty10`, mappé sur `/k`, GID `5`. Son origine est `[322.8609924316406, 419.7160339355469]` et sa ligne de base est plus basse de `1.495` point que celle du `x`.

## Preuve ciblée `/minus`

Les 10 codes `0x21` de `/Ty18` sélectionnent `/minus`, GID `1`. `ToUnicode` annonce U+2260 ; le nom CFF `/minus`, l'AGL U+2212 et le tracé en barre horizontale étayent l'interprétation comme signe moins. Le tracé a les bornes `[83, 230, 694, 270]`.

## Périmètre supporté

- contenus de page directs
- polices Type1 avec FontFile3 Type1C embarqué
- codes monooctets MacRoman ou StandardEncoding avec Differences
- ToUnicode bfchar et bfrange directs
- association source-rendu par ordre et GID CFF
- association aux blocs MuPDF par police, origine et Unicode rendu

## Limites et rejets explicites

- PDF dont le SHA-256 diffère
- Form XObjects ou opérateur Do
- mode de rendu Tr
- polices Type0/CID, Type3, non embarquées ou non CFF
- CMap multioctet ou bfrange en tableau
- rotation de page
- écart de longueur, de police, de GID ou association rawdict non univoque
- dessins vectoriels et images sans glyphe texte

Commande : `python source-render-proof/verify_all_glyphs.py`
