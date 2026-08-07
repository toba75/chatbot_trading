# Politique de persistance des observations fournisseur

Le registre ne conserve pas la réponse JSON brute de Google Books. Il conserve
uniquement une représentation normalisée et minimale : identifiant de volume,
titre, auteurs, éditeur, date publiée telle que fournie, langue, identifiants
ISBN, catégories et, seulement lorsque les deux champs sont présents, la note
moyenne et le nombre de votes. Chaque valeur est rattachée à l'identifiant du
volume et à l'instant `observed_at`; l'URL de requête est conservée sans clé
d'accès.

La recherche utilise d’abord les identifiants valides, puis des variantes de
titre combinées avec jusqu’à trois auteurs et l’éditeur. Les candidats fusionnés
par `volume_id` conservent les champs non vides de chaque réponse et exposent un
score de rapprochement initial (titre 0,60, auteur 0,20, éditeur 0,10, année
0,10, renormalisé aux signaux disponibles). Ce score sert à trier et à déclencher
la revue humaine ; il ne constitue pas une autorité éditoriale.

La date `publishedDate` devient `temporality.edition_published`. Elle ne devient
jamais `work_first_published` ni `content_revision`. Les réponses, descriptions,
images et extraits ne sont pas copiés dans le dépôt. Le texte du PDF et le
`DoclingDocument` restent les autorités de contenu.

Avant chaque enrichissement, l'opérateur vérifie les [conditions Google
Books](https://developers.google.com/books/terms) et la version de cette
politique. Si une donnée n'est plus conservable, elle n'est pas réécrite comme
`null` ou zéro : l'observation est marquée `withdrawn` dans le journal local,
les champs fournisseur sont supprimés du registre, puis le registre est
revalidé. Le rapport d'enrichissement conserve seulement le compte et la cause
du retrait. Une nouvelle consultation est nécessaire avant toute réintégration;
aucun index existant ne doit continuer à servir une valeur retirée.

Google Books est le seul fournisseur activé dans cette tranche. Les rangs
Amazon et les notes issues d'une autre source restent absents plutôt que
d'inventer une popularité. Aucun signal commercial n'entre dans le texte dense
ou ne modifie un drapeau de preuve.

## Accès aux credentials

La clé Google Books est conservée dans les credentials Rails chiffrés, sous
`google_books.api_key`. Le champ `google_books.email` peut conserver l'adresse
du compte de service, mais il n'est pas utilisé pour les requêtes publiques
authentifiées par clé API.

Le CLI Python demande cette valeur à Rails avec `docker compose ... rails
runner`. Il ne déchiffre pas `credentials.yml.enc`, ne lit pas la clé privée
du compte de service et ne copie aucune credential dans le catalogue ou le
rapport d'enrichissement. Une indisponibilité de Docker, de `master.key` ou de
la credential arrête explicitement l'enrichissement.
