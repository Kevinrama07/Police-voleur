# Modèle du graphe — POLICE – VOLEUR

## 1. Définition formelle

Le plateau est modélisé par un **graphe non orienté** :

```
G = (V, E)
|V| = 21 sommets
|E| = 36 arêtes
```

Chaque sommet possède :

- un **identifiant unique** (chaîne stable, voir §2) ;
- ses **coordonnées graphiques** dans le repère de l'image de référence (689 × 796 px, `y` vers le bas) ;
- la liste de ses **voisins** (liste d'adjacence).

Le graphe est la **source unique de vérité** pour les déplacements. Le rendu (Pygame) consomme le
graphe et applique lui-même sa transformation d'écran (échelle, translation) : aucune coordonnée de
rendu n'est stockée dans la logique du jeu.

## 2. Convention de nommage

| Préfixe | Signification |
|---|---|
| `T`, `B`, `L`, `R` | Sommets cardinaux : haut, bas, gauche, droite (cordes ∩ ellipse) |
| `CENTER` | Centre du plateau (intersection des deux cordes) |
| `J1`, `J2` | Jonctions des pétales sur la verticale (haut, bas) |
| `VCt`, `VCb` | Croisements verticale ∩ cercle central (haut, bas) |
| `HCl`, `HCr` | Croisements horizontale ∩ cercle central (gauche, droite) |
| `HAL`, `HAR` | Croisements horizontale ∩ grands arcs (gauche, droite) |
| `EA1`, `EA2`, `EA6`, `EA7` | Arcs pétales ∩ ellipse |
| `EALt`, `EALb`, `EARt`, `EARb` | Grands arcs ∩ ellipse (haut / bas, gauche / droite) |

## 3. Sommets (table complète)

| Id | x | y | Type | Degré | Voisins |
|---|---|---|---|---|---|
| `T` | 352.0 | 189.6 | V ∩ E | 3 | `J1`, `EA2`, `EA1` |
| `EA2` | 276.4 | 202.8 | E ∩ A2 | 3 | `T`, `EALt`, `J1` |
| `EALt` | 155.0 | 322.6 | E ∩ ALU haut | 3 | `EA2`, `L`, `HAL` |
| `L` | 138.1 | 406.5 | H ∩ E | 3 | `EALt`, `EALb`, `HAL` |
| `EALb` | 157.5 | 500.4 | E ∩ ALL bas | 3 | `L`, `EA6`, `HAL` |
| `EA6` | 269.3 | 611.4 | E ∩ A6 | 3 | `EALb`, `B`, `J2` |
| `B` | 352.0 | 627.5 | V ∩ E | 3 | `EA6`, `EA7`, `J2` |
| `EA7` | 434.6 | 608.4 | E ∩ A7 | 3 | `B`, `EARb`, `J2` |
| `EARb` | 545.4 | 486.0 | E ∩ ARL bas | 3 | `EA7`, `R`, `HAR` |
| `R` | 559.0 | 406.5 | H ∩ E | 3 | `EARb`, `EARt`, `HAR` |
| `EARt` | 542.9 | 324.5 | E ∩ ARU haut | 3 | `R`, `EA1`, `HAR` |
| `EA1` | 431.2 | 207.2 | E ∩ A1 | 3 | `EARt`, `T`, `J1` |
| `J1` | 352.0 | 272.7 | V ∩ A1 ∩ A2 | 4 | `T`, `VCt`, `EA2`, `EA1` |
| `VCt` | 352.0 | 365.3 | V ∩ C haut | 4 | `J1`, `CENTER`, `HCl`, `HCr` |
| `CENTER` | 352.0 | 406.5 | V ∩ H | 4 | `VCt`, `VCb`, `HCl`, `HCr` |
| `VCb` | 352.0 | 446.8 | V ∩ C bas | 4 | `CENTER`, `J2`, `HCl`, `HCr` |
| `J2` | 352.0 | 550.0 | V ∩ A6 ∩ A7 | 4 | `VCb`, `B`, `EA6`, `EA7` |
| `HAL` | 225.3 | 406.5 | H ∩ ALU ∩ ALL | 4 | `L`, `HCl`, `EALt`, `EALb` |
| `HCl` | 311.8 | 406.5 | H ∩ C gauche | 4 | `HAL`, `CENTER`, `VCt`, `VCb` |
| `HCr` | 393.3 | 406.5 | H ∩ C droite | 4 | `CENTER`, `HAR`, `VCt`, `VCb` |
| `HAR` | 476.1 | 406.5 | H ∩ AR | 4 | `HCr`, `R`, `EARt`, `EARb` |

## 4. Arêtes (table complète, découpées par primitive)

Chaque arête appartient à une primitive géométrique (utile pour le rendu courbe fidèle).

### Ellipse E — 12 arêtes (cycle)

`L–EALt`, `EALt–EA2`, `EA2–T`, `T–EA1`, `EA1–EARt`, `EARt–R`, `R–EARb`, `EARb–EA7`, `EA7–B`, `B–EA6`, `EA6–EALb`, `EALb–L`

### Verticale V — 6 arêtes

`T–J1`, `J1–VCt`, `VCt–CENTER`, `CENTER–VCb`, `VCb–J2`, `J2–B`

### Horizontale H — 6 arêtes

`L–HAL`, `HAL–HCl`, `HCl–CENTER`, `CENTER–HCr`, `HCr–HAR`, `HAR–R`

### Cercle central C — 4 arêtes (cycle)

`VCt–HCr`, `HCr–VCb`, `VCb–HCl`, `HCl–VCt`

### Arcs — 8 arêtes

| Arc | Arêtes |
|---|---|
| A1 | `J1–EA1` |
| A2 | `J1–EA2` |
| A6 | `J2–EA6` |
| A7 | `J2–EA7` |
| ALU | `EALt–HAL` |
| ALL | `HAL–EALb` |
| ARU | `EARt–HAR` |
| ARL | `HAR–EARb` |

## 5. Invariants et contrôles automatiques

1. **Symétrie** : si `u` est voisin de `v`, alors `v` est voisin de `u` (aucune arête dirigée).
2. **Unicité** : 21 identifiants uniques, aucune arête dupliquée.
3. **Degrés** : `Σ deg(v) = 2 × 36 = 72` ; 12 sommets de degré 3, 9 de degré 4.
4. **Connexité** : le graphe est connexe (BFS depuis `CENTER` atteint les 21 sommets).
5. **Fidélité géométrique** : sur les 17 114 pixels d'encre de l'image, distance moyenne 1,38 px,
   p95 2,69 px, maximum 6,25 px (3 px du renflement de jonction `J2` uniquement).
6. **Cycles** : cycles élémentaires attendus — triangle du haut (`T–J1–EA2` ? non : `T–EA2`, `EA2–J1`,
   `J1–T` forment un triangle) ; de même `T–EA1–J1–T`, `B–EA6–J2–B`, `B–EA7–J2–B` ; et les carrés
   du cercle central (`VCt–HCr–VCb–HCl–VCt` etc.).

## 6. Sémantique de jeu attachée au graphe

- **Déplacements** : uniquement le long des 36 arêtes, d'un sommet vers un voisin.
- **`CENTER`** : position initiale du voleur ; zone de victoire du voleur ; **contestable** — un
  policier peut y entrer après le départ du voleur (voir §6.1).
- **Occupation** : un sommet ne peut être occupé que par un seul personnage.
- **Configuration initiale** (règles officielles) : voleur sur `CENTER` ; trois policiers sur trois
  sommets distincts ≠ `CENTER`, tirés aléatoirement parmi les 20 autres sommets (graine reproductible).
- **Victoire policiers** : `LegalMoves(Voleur) = ∅` (aucun voisin libre).
- **Victoire voleur** : retour sur `CENTER` après l'avoir quitté, **une fois le cooldown écoulé**.
- **Nulles** : limite de coups (`max_moves`, défaut 500) ou répétition d'une position
  (`repetition_limit`, défaut 3) — jamais converties en victoire.

### 6.1 Amendement documenté : cooldown de retour + centre contestable

Les règles littérales (« centre interdit aux policiers ») rendent la victoire policière
**mathématiquement impossible** : le voleur part du centre, dispose toujours d'au moins un voisin
libre (4 voisins, 3 policiers), ne peut jamais être bloqué au centre, et revient en 3 demi-coups.
Le benchmark IA l'a confirmé : 20 parties sur 20 gagnées par le voleur en 3,0 coups en moyenne.

Décision validée par l'utilisateur, matérialisée par `core.ruleset.RuleSet` :

| Paramètre | Défaut | Effet |
|---|---|---|
| `return_cooldown` | 10 | le retour au centre est **illégal** tant que `ply < 10` (configurable) |
| `center_contestable` | `True` | les policiers peuvent occuper `CENTER` après le départ du voleur |

Conséquences stratégiques : la police doit **gagner la course au centre** (l'occuper pour nier le
retour) tout en traquant le voleur ; le voleur doit survivre au cooldown puis revenir si le centre
est libre. Sous jeu parfait, la police ne peut pas bloquer un voleur qui reste sur les sommets de
degré 4 : les nulles par répétition sont fréquentes (19/20 en auto-jeu à profondeur 3, 1 victoire
policière), ce qui est un résultat **légitime** au regard des règles.


## 7. Validation et débogage

- **Validation visuelle** : `docs/board_validation.png` — primitives détectées (couleurs), sommets
  (disque jaune + identifiant) superposés au dessin original.
- **Validation structurelle** : `tests/test_graph.py` vérifie les degrés, la connexité, la symétrie
  et la cohérence du graphe ; `tests/test_board_fidelity.py` compare les coordonnées au dessin.
- **Débogage en jeu** : l'interface permet de visualiser les sommets et les arêtes sur le plateau.

## 8. Symétries remarquables

Le graphe est invariant par :

- symétrie gauche/droite autour de la verticale `x = 348.5` environ :
  `EA1 ↔ EA2`, `EARt ↔ EALt`, `EARb ↔ EALb`, `R ↔ L`, `HAR ↔ HAL`, `EA7 ↔ EA6`, `HCr ↔ HCl` ;
- symétrie haut/bas imparfaite (le plateau est légèrement étiré verticalement : ellipse non
  circulaire) mais la topologie est identique haut/bas : `T ↔ B`, `J1 ↔ J2`, `VCt ↔ VCb`,
  `EA2 ↔ EA6`, `EA1 ↔ EA7`.

Ces symétries serviront de base aux heuristiques de l'IA (réflexions), sans jamais remplacer la
recherche Minimax réelle.
