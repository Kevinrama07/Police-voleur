# Analyse géométrique du plateau — POLICE – VOLEUR

## 1. Référence et contraintes

- **Image de référence** : `assets/images/board.png`, 689 × 796 px, RGBA, fond transparent.
- Cette image est la **référence géométrique officielle** : la topologie du jeu en est déduite, jamais inventée.
- Aucune bibliothèque de vision n'étant installée (ni OpenCV, ni SciPy), l'analyse a été réalisée
  **programmatiquement** avec `Pillow` + `NumPy`, avec des ajustements (moindres carrés, Levenberg-Marquardt,
  RANSAC, rejet d'outliers) implémentés sur mesure.

## 2. Caractéristiques de l'image (mesurées)

| Valeur de gris | Contenu |
|---|---|
| 0 | Encre noire : traits du plateau |
| 2 | Encre noire (anti-crénelage sombre) |
| 43 | **Pion du voleur** (gris foncé) |
| 84 | **Pions des policiers** (gris moyen) |
| 249–254 | Anti-crénelage des traits |
| 255 | Fond blanc / transparence composée |

L'encre du plateau est isolée par le seuil `gris < 30` ; les pions (43 et 84) sont donc exclus automatiquement
du tracé et analysés séparément (voir §6).

## 3. Méthodologie

La topologie et les coordonnées retenues sont intégrées dans `core/graph.py` ; les formes utilisées
pour le rendu sont décrites dans `core/board_geometry.py`. La géométrie a été déterminée à partir
de l'image de référence, en isolant l'encre, en ajustant les primitives et en vérifiant leurs
intersections.

Découverte clé n° 1 : le contour extérieur n'est **pas un cercle** mais une **ellipse**
(l'ajustement circulaire présentait des résidus incompatibles ; l'ajustement elliptique les annule).
Découverte clé n° 2 : les taches grises sont les **pions**, positionnés exactement sur des sommets du graphe
(validation croisée forte, voir §6).

## 4. Primitives géométriques extraites

Repère : pixels de l'image, origine en haut à gauche, `y` vers le bas.

### 4.1 Contour extérieur — ellipse E

- Centre `(348.54 ; 408.54)`, demi-grand axe `a = 210.43`, demi-petit axe `b = 218.98`
  (l'axe vertical est le grand axe).
- Équation : `((x − 348.54)/210.43)² + ((y − 408.54)/218.98)² = 1`.
- Ajustement sur les milieux de trait, rejet itératif des outliers des zones de jonction :
  1281/1316 points conservés, résidu max final **0,045 px**.

### 4.2 Ligne verticale V (corde)

- `x = 352` (trait de 5 px : colonnes 350–354).
- Extrémités sur l'ellipse : sommet haut `T ≈ (352 ; 189.6)`, sommet bas `B ≈ (352 ; 627.5)`.

### 4.3 Ligne horizontale H (corde)

- `y = 406.5` (trait de 6 px : lignes 404–409).
- Extrémités sur l'ellipse : sommet gauche `L ≈ (138.1 ; 406.5)`, sommet droit `R ≈ (559.0 ; 406.5)`.

### 4.4 Cercle central C

- Centre `(352.54 ; 406.05)`, rayon `r = 40.74`.
- Le centre du cercle coïncide avec l'intersection V ∩ H (à moins de 0,5 px).
- Les deux cordes traversent le cercle de part en part (vérifié : encre continue aux croisements).

### 4.5 Arcs intérieurs (portions de cercles, toutes tracées à l'intérieur de l'ellipse)

| Arc | Cercle support (cx ; cy ; r) | Portion tracée (approx.) | Rôle visuel |
|---|---|---|---|
| **A1** | (360.38 ; 202.29 ; 70.99) | de l'ellipse ≈ (431 ; 207) à la jonction `J1` | pétale haut-droite |
| **A2** | (347.05 ; 202.21 ; 70.65) | de l'ellipse ≈ (276 ; 203) à la jonction `J1` | pétale haut-gauche |
| **ALU** | (144.03 ; 403.13 ; 81.23) | ellipse ≈ (155 ; 323) → croise H ≈ (225.3 ; 406.5) | grand arc gauche, moitié haute |
| **ALL** | (141.69 ; 417.37 ; 84.49) | croise H ≈ (225.3 ; 406.5) → ellipse ≈ (157 ; 500) | grand arc gauche, moitié basse |
| **ARU** | (553.56 ; 401.36 ; 77.60) | ellipse ≈ (543 ; 324) → croise H ≈ (476.1 ; 406.5) | grand arc droit, moitié haute |
| **ARL** | (553.63 ; 408.91 ; 77.54) | croise H ≈ (476.1 ; 406.5) → ellipse ≈ (545 ; 486) | grand arc droit, moitié basse |
| **A6** | (340.74 ; 620.81 ; 72.08) | de la jonction `J2` à l'ellipse ≈ (269 ; 611) | pétale bas-gauche |
| **A7** | (365.63 ; 618.66 ; 69.69) | de la jonction `J2` à l'ellipse ≈ (435 ; 608) | pétale bas-droit |

Notes de précision :
- Les cercles supports d'un même "pétale" se recoupent au point de jonction
  (A1 ∩ A2 ≈ `J1`, A6 ∩ A7 ≈ `J2`), ce qui confirme l'intention du dessin.
- **Chaque flanc est dessiné en deux arcs distincts** (haut / bas) qui se rencontrent sur
  l'horizontale : par exemple à gauche, le tracé haut suit le cercle (144.03 ; 403.13 ; 81.23)
  et le tracé bas le cercle (141.69 ; 417.37 ; 84.49). Le coude est invisible sur le dessin
  (les deux arcs se raccordent à moins de 1 px en `HAL`), mais il est nécessaire pour expliquer
  l'encre : un cercle unique laissait jusqu'à 14 px d'écart près de la fourche supérieure.
- À `J1` et `J2`, les centres calculés des arcs ne tombent pas exactement sur la verticale
  (écart de 5 à 7 px) : c'est une imprécision de tracé. Les jonctions sont donc calées sur
  `x = 352` à l'ordonnée moyenne des deux arcs (`J1 = (352 ; 272.7)`, `J2 = (352 ; 550.0)`),
  ce qui est cohérent avec les taches d'encre observées (les deux arcs et la ligne fusionnent
  dans un renflement local).
- Pour `A1`, l'intersection mathématique avec l'ellipse est `(431.4 ; 207.3)` ; l'encre s'arrête
  vers `(423 ; 204)`. L'écart (< 9 px) est de l'ordre de l'épaisseur cumulée des traits et de
  l'anti-crénelage ; le sommet est **calé sur l'ellipse exacte** (projection orthogonale radiale).

### 4.6 Jonctions et croisements remarquables

- `J1 = V ∩ A1 ∩ A2 ≈ (352 ; 272.7)` — pétales supérieurs sur la verticale.
- `J2 = V ∩ A6 ∩ A7 ≈ (352 ; 550.0)` — pétales inférieurs sur la verticale.
- Croisements H ∩ flancs ≈ `(225.3 ; 406.5)` et `(476.1 ; 406.5)` : les quatre arcs latéraux
  traversent l'horizontale.
- Croisements V ∩ C et H ∩ C : quatre points (partie centrale), les cordes étant continues.

## 5. Sommets du graphe (21)

Coordonnées finales (pixels, arrondies à 0,1) — les sommets appartenant à l'ellipse y sont
projetés exactement, ceux appartenant aux cordes sont alignés exactement :

| Id | Position | Type | Degré |
|---|---|---|---|
| `T` | (352.0 ; 189.6) | V ∩ E (sommet haut) | 3 |
| `EA2` | (276.4 ; 202.8) | E ∩ A2 | 3 |
| `EALt` | (155.0 ; 322.6) | E ∩ ALU (haut) | 3 |
| `L` | (138.1 ; 406.5) | H ∩ E (sommet gauche) | 3 |
| `EALb` | (157.5 ; 500.4) | E ∩ ALL (bas) | 3 |
| `EA6` | (269.3 ; 611.4) | E ∩ A6 | 3 |
| `B` | (352.0 ; 627.5) | V ∩ E (sommet bas) | 3 |
| `EA7` | (434.6 ; 608.4) | E ∩ A7 | 3 |
| `EARb` | (545.4 ; 486.0) | E ∩ ARL (bas) | 3 |
| `R` | (559.0 ; 406.5) | H ∩ E (sommet droit) | 3 |
| `EARt` | (542.9 ; 324.5) | E ∩ ARU (haut) | 3 |
| `EA1` | (431.2 ; 207.2) | E ∩ A1 | 3 |
| `J1` | (352.0 ; 272.7) | V ∩ A1 ∩ A2 | 4 |
| `VCt` | (352.0 ; 365.3) | V ∩ C (haut) | 4 |
| `CENTER` | (352.0 ; 406.5) | V ∩ H (centre) | 4 |
| `VCb` | (352.0 ; 446.8) | V ∩ C (bas) | 4 |
| `J2` | (352.0 ; 550.0) | V ∩ A6 ∩ A7 | 4 |
| `HAL` | (225.3 ; 406.5) | H ∩ ALU ∩ ALL | 4 |
| `HCl` | (311.8 ; 406.5) | H ∩ C (gauche) | 4 |
| `HCr` | (393.3 ; 406.5) | H ∩ C (droite) | 4 |
| `HAR` | (476.1 ; 406.5) | H ∩ ARU ∩ ARL | 4 |

Degrés : 12 sommets de degré 3, 9 sommets de degré 4 ; Σ degrés = 72 = 2 × 36 arêtes.

## 6. Les pions — lecture des règles sur l'image

Extraction des composantes grises (hors encre noire) :

| Pion | Niveau de gris | Aire (px) | Centroïde | Sommet correspondant |
|---|---|---|---|---|
| Voleur | 43 | 341 | (353.0 ; 404.0) | **`CENTER`** (352.0 ; 406.5) |
| Policier 1 | 84 | 587 | (353.5 ; 191.1) | **`T`** (352.0 ; 189.6) |
| Policier 2 | 84 | 571 | (394.1 ; 405.1) | **`HCr`** (393.3 ; 406.5) |
| Policier 3 | 84 | 687 | (559.0 ; 405.5) | **`R`** (559.0 ; 406.5) |

Chaque centroïde coïncide avec un sommet calculé indépendamment — **validation croisée du modèle**.
La configuration représentée est conforme aux règles : voleur au centre, trois policiers sur des
sommets valides, distincts, jamais au centre.

## 7. Validation du modèle

1. **Couverture de l'encre** : chaque pixel noir (`gris < 30`) doit être proche d'une primitive.
   Mesure effectuée sur **les 17 114 pixels d'encre** : distance moyenne
   **1,38 px**, p95 **2,69 px**, maximum **6,25 px** (3 px du renflement de jonction `J2`).
   → 100 % de l'encre est expliquée par le modèle (aucun trait oublié, aucun trait inventé).
2. **Réciprocité** : l'image de validation `docs/board_validation.png` superpose primitives, sommets
   et identifiants sur le plateau original (système de validation visuel).
3. **Cohérence combinatoire** : degrés = 2 × arêtes, graphe symétrique, connexe, aucun sommet isolé
   (vérifié par assertions et test dédié, cf. `docs/GRAPH_MODEL.md` §5).
4. **Validation croisée par les pions** : voir §6.

## 8. Ambiguïtés résiduelles et décisions

| Point | Constat | Décision |
|---|---|---|
| Renflements à `J1`/`J2` | Les cercles d'arcs se coupent légèrement hors de la verticale (±5–7 px) ; l'encre forme une tache | Jonction calée en `x = 352`, ordonnée moyenne des deux arcs (tache d'encre couvrante) |
| Flancs dessinés en deux arcs | Les quatre flancs sont tracés en deux arcs circulaires (haut/bas) qui se raccordent sur `H` | Deux primitives par flanc (`ALU/ALL`, `ARU/ARL`) : topologie inchangée, fidélité exacte |
| Fin de `A1` côté ellipse | Intersection mathématique (431.4 ; 207.3) vs fin d'encre (423 ; 204) | Sommet projeté sur l'ellipse exacte ; écart < épaisseur de trait |
| Croisements cordes × cercle central | Les cordes sont tracées en continu à travers le cercle | Croisements traités comme sommets jouables (degré 4) |
| Centre `V ∩ H` | Intersection des deux cordes au centre du cercle | Sommet jouable `CENTER` (position initiale du voleur) |
| Sens des arcs E∩arcs | Les arcs s'arrêtent sur l'ellipse (pas de prolongement au-delà) | Sommets de degré 3 (2 directions d'ellipse + l'arc) |

Aucune connexion ambiguë ne subsiste : la topologie est entièrement déterminée par le dessin
et validée numériquement. Si une divergence visuelle est constatée sur `docs/board_validation.png`,
les coordonnées du graphe intégré peuvent être corrigées sans modifier la topologie.
