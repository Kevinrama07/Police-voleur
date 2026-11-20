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
  `record_tree`, `tree_depth`, `rules` (`RuleSet`), `evaluator` (optionnel).
- `search(state, config, ply=0)` : la racine est jouée à fenêtre pleine, donc les scores racine sont
  **exacts** ; `SearchResult` expose `move`, `score`, `depth`, `nodes`, `cutoffs`, `tt_hits`,
  `elapsed`, `root_scores` et l'arbre pédagogique (`SearchNode`).
- `value_full(state, depth, ply=0)` : Minimax pur, référence des tests d'équivalence.
- Le cooldown est propagé (`ply` + 1 par demi-coup) : le retour au centre est illégal tant que
  `ply < rules.return_cooldown`, et la détection de blocage tient compte de cette restriction.
- Les nulles par répétition ne sont **pas** modélisées dans l'arbre : `core.game_manager` reste seul
  juge du résultat ; le moteur POLICE ajoute son propre filtre en racine (section suivante).

## 3. Minimax renforcé de la POLICE (`ai/police_minimax.py`)

La POLICE utilise le même **Minimax/Alpha-Beta** que le VOLEUR, avec deux renforts :

- `evaluator=exact_evaluation` note les feuilles avec la table rétrograde (`ai/police_solver.py`) :
  victoire, défaite ou nulle, avec distance de capture. La recherche reste bien un Minimax,
  mais chaque feuille connaît la valeur exacte du jeu.
- Le coup racine est choisi parmi `root_scores` en écartant ceux qui provoqueraient une 3ᵉ
  répétition, tant qu'un coup non répétitif reste disponible.

Le VOLEUR n'est pas modifié : `MatchController` lui passe toujours `SearchEngine` avec
l'évaluation heuristique historique. La POLICE gagne ainsi contre le Minimax du VOLEUR
quel que soit le réglage de profondeur de ce dernier.

## 4. Vérifications

- `tests/test_ai.py` : légalité multi-graines, équivalence stricte Alpha-Beta ↔ Minimax,
  élagage effectif (`nodes`, `cutoffs`), transposition, limite de temps, cooldown du centre,
  blocage policier, heuristiques, arbre enregistré.
- `tests/test_police_minimax.py` : parties complètes où le Minimax renforcé de la POLICE bat
  le Minimax du VOLEUR.
- `python tools/benchmark_ai.py --games 20 --depth 3` : auto-jeu complet, temps par coup, nœuds,
  coupures.
