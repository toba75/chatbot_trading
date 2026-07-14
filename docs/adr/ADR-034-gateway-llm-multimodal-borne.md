# ADR-034 - Gateway LLM multimodal borné

**Statut :** Acceptée
**Date :** 2026-07-14
**Décideurs :** Équipe OSTrading
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** Demande utilisateur du 2026-07-14 ; `docs/specs/m002_plateforme_locale_sure.md` ; ADR-014, ADR-015 et ADR-020

## Contexte

Le gateway LLM local expose aujourd’hui `POST /v1/infer`, mais son contrat ne
représente que des messages textuels. Une page PDF rendue localement ne peut
donc pas atteindre Gemma 4 par le chemin imposé `llm-gateway ->
spark-inference`. Appeler vLLM directement pour contourner cette limite
violerait ADR-014 et la frontière réseau M-002.

Gemma 4 peut traiter une image, mais cette capacité ne suffit pas à en faire
une autorité documentaire : M-004 exige toujours une route explicite, une
provenance pagewise, des coordonnées et une sélection d’autorité textuelle
unique. Cette décision porte uniquement sur le transport d’une inférence
multimodale traçable et bornée.

## Décision

- Le `llm-gateway` **DOIT** accepter deux variantes explicites de message : un
  message textuel et un message multimodal. Il **NE DOIT PAS** transformer
  implicitement un message textuel en message image, ni inversement.
- Un message multimodal **DOIT** contenir une instruction textuelle suivie d’au
  moins une image. Une image **DOIT** exposer exactement `media_type`,
  `data_base64` et `sha256`.
- Seuls `image/png` et `image/jpeg` sont admis. Les octets Base64 **DOIVENT**
  être canoniques, correspondre à la signature du type MIME annoncé, être
  limités à 10 Mio et correspondre exactement au SHA-256 déclaré.
- Le contrat **NE DOIT PAS** accepter d’URL distante, de chemin local, de PDF
  brut ou de référence de stockage comme partie image. Le gateway construit la
  représentation OpenAI compatible `image_url` avec une URI `data:` seulement
  pour son appel sortant vers le Spark.
- Le Spark reçoit l’image pour l’inférence courante seulement ; il ne reçoit ni
  identifiant documentaire, ni chemin local, ni donnée métier persistante. Les
  logs et la provenance **NE DOIVENT PAS** contenir les octets Base64 ; ils
  conservent les identifiants de requête et les empreintes déjà requises par
  ADR-015.
- Toute image invalide, altérée, trop grande ou d’un type interdit **DOIT**
  être refusée par un code stable. Aucune image de remplacement, aucune
  recompression et aucun second modèle ne sont essayés.
- Cette ADR **N’AUTORISE PAS** Gemma à devenir une autorité textuelle M-004,
  ni à s’exécuter après un échec Granite. Une future route documentaire Gemma
  exigera une ADR distincte, son benchmark comparatif, des sorties pagewise
  coordonnées et une mise à jour explicite d’ADR-032.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Étendre le gateway unique par un contrat image strict | Retenue | Permet l’inférence Gemma réelle sans ouvrir un accès direct au Spark. |
| Appeler vLLM directement depuis un worker de conversion | Rejetée | Viole ADR-014, contourne les contrôles de provenance et crée une sortie réseau concurrente. |
| Envoyer une URL ou un chemin de fichier au Spark | Rejetée | Expose la topologie et ne garantit ni l’accès contrôlé ni l’intégrité des octets. |
| Utiliser Gemma comme fallback automatique de Granite | Rejetée | Viole ADR-032, l’autorité textuelle unique et l’interdiction de fallback silencieux. |

## Conséquences

### Positives

- Une page fournie explicitement peut être évaluée par Gemma via le seul chemin
  réseau autorisé.
- L’intégrité et la taille de l’image sont contrôlées avant l’appel Spark.
- Le contrat OpenAI compatible est produit par un unique adaptateur auditable.

### Négatives ou coûts

- L’image est encodée Base64 dans la requête du gateway, ce qui augmente le
  volume mémoire et réseau dans la limite déclarée.
- La capacité de vision du modèle doit être évaluée séparément de la qualité de
  conversion canonique.

### Risques et contrôles

- Risque : exfiltrer un chemin ou une URL vers le Spark. Contrôle : les clés de
  partie image sont exactes et toute autre forme est refusée.
- Risque : accepter un contenu altéré. Contrôle : signature MIME, Base64
  canonique, limite de taille et SHA-256 sont vérifiés localement.
- Risque : confondre inférence de diagnostic et publication canonique. Contrôle
  : aucune route M-004 ni `TextAuthoritySelectionPolicy` n’est modifiée.

## Impact d'implémentation

- Modules concernés : `app/platform/llm_gateway/__init__.py` et
  `app/platform/local_runtime.py`.
- Configuration concernée : aucune ; le modèle, sa révision, son runtime et
  l’endpoint Spark restent ceux exigés par ADR-014 et ADR-015.
- Tests attendus : sérialisation OpenAI multimodale, validation de l’image,
  absence d’appel Spark direct et refus des données altérées.
- Milestones concernées : M-002, M-004 et M-013.

## Liens de traçabilité

- Spécification : `docs/specs/m002_plateforme_locale_sure.md`.
- Plan d'implémentation : demande utilisateur du 2026-07-14 ; la sélection
  d’une éventuelle route M-004 reste hors de ce changement.
- Tests d'acceptation :
  `gate_tests/ported/tests/m002/validate_llm_gateway_multimodal_contract_acceptance.py`.
- Tests unitaires :
  `gate_tests/ported/tests/m002/validate_llm_gateway_multimodal_contract_unit.py`.
- Commits : RED `4e2e87c15`, `9e76f5918` ; GREEN à renseigner après validation.

## Notes

ADR-014, ADR-015 et ADR-020 restent acceptées et inchangées. Cette ADR les
précise pour un contenu image transitant exclusivement par le gateway.
