# IA — Minimax, Alpha-Beta et évaluation heuristique

Module `ai/` (aucune dépendance à Pygame). La POLICE est le **maximizer**, le VOLEUR le
**minimizer** ; les scores terminaux (victoire police `+10 000`, victoire voleur `−10 000`) sont
fixes et toujours prioritaires sur l'heuristique.

## 1. Évaluation (`ai/evaluation.py`)

Score heuristique du point de vue de la police :

| Terme | Poids | Intention |
|---|---|---|
| distance voleur → centre | `+120 / arête` | éloigner le voleur de sa zone de victoire |
| course au centre (police) | `−60 / arête` | occuper le centre avant le voleur (centre libre) |
| proximité du policier le plus proche | `−40 / arête` | resserrer l'étau |
| mobilité du voleur | `−45 / coup` | réduire ses échappatoires |
| sommets atteignables par le voleur | `−3 / sommet` | limiter son territoire |
| pression sur le chemin voleur → centre | `−35 / sommet` | couper la route du retour |
| chemins d'évasion (mobilité gardant le centre accessible) | `−30 / coup` | anticiper les fuites |
| centre inaccessible au voleur | `+2 500` | centre occupé : retour impossible |

`evaluate(graph, state, ply=None)` : `ply=None` = évaluation statique (cooldown ignoré) ; la
recherche transmet le `ply` réel pour rester cohérente avec `legal_moves`.

## 2. Recherche (`ai/minimax.py`)

- **Minimax** récursif à profondeur limitée, **Alpha-Beta** optionnel, **table de transposition**
  (drapeaux `EXACT` / `LOWER` / `UPPER`, clé = position + état du cooldown écrêté), **ordonnancement
  des coups** (policiers : rapprochement du voleur ; voleur : rapprochement du centre),
  **approfondissement itératif** avec limite de temps (`SearchTimeout`).
- `SearchConfig` : `max_depth`, `time_limit`, `alpha_beta`, `use_transposition`, `order_moves`,
  `record_tree`, `tree_depth`, `rules` (`RuleSet`).
- `search(state, config, ply=0)` : la racine est jouée à fenêtre pleine, donc les scores racine sont
  **exacts** ; `SearchResult` expose `move`, `score`, `depth`, `nodes`, `cutoffs`, `tt_hits`,
  `elapsed`, `root_scores` et l'arbre pédagogique (`SearchNode`).
- `value_full(state, depth, ply=0)` : Minimax pur, référence des tests d'équivalence.
- Le cooldown est propagé (`ply` + 1 par demi-coup) : le retour au centre est illégal tant que
  `ply < rules.return_cooldown`, et la détection de blocage tient compte de cette restriction.
- Les nulles par répétition ne sont **pas** modélisées dans l'arbre : `core.game_manager` reste seul
  juge du résultat.

## 3. Vérifications

- `tests/test_ai.py` : légalité multi-graines, équivalence stricte Alpha-Beta ↔ Minimax,
  élagage effectif (`nodes`, `cutoffs`), transposition, limite de temps, cooldown du centre,
  blocage policier, heuristiques, arbre enregistré.
- `python tools/benchmark_ai.py --games 20 --depth 3` : auto-jeu complet, temps par coup, nœuds,
  coupures.
