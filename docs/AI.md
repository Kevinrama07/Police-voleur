# IA — un contrat, deux minimax alpha-bêta

Le dossier `ai/` ne dépend pas de Pygame. Chaque camp possède **son propre minimax** :

| Fichier | Rôle | Algorithme |
| --- | --- | --- |
| `ai/contrat.py` | Interface commune | `Bot`, `Context`, `Stats`, `SearchNode`, `Result` |
| `ai/minimax_voleur.py` | Voleur (MIN) | Minimax alpha-bêta + heuristique + approfondissement itératif |
| `ai/minimax_police.py` | Police (MAX) | Minimax alpha-bêta + table exacte comme évaluation feuille |
| `ai/exact_table.py` | Évaluation police | Table rétrograde des 47 880 positions canoniques |

```python
Bot = Callable[[Graph, GameState, int, Context | None], Move]
```

`Context` transporte `rules`, `depth`, `repetition_limit`, `history`, `deadline`, `stats` et
`collect_tree`.
Le moteur reste seul juge de la légalité et du résultat : les bots ne font que proposer un coup.

## 1. Voleur — minimax alpha-bêta (`ai/minimax_voleur.py`)

Scores du **point de vue police** : la police maximise, le voleur minimise.

Heuristique à 3 termes (plus un garde-fou de connectivité) :

| Terme | Poids | Intention |
| --- | --- | --- |
| distance voleur → centre | `+100 / arête` | éloigner le voleur de sa zone de victoire |
| mobilité du voleur | `−40 / coup` | réduire ses échappatoires |
| proximité du policier le plus proche | `−30 / arête` | resserrer l'étau |
| sommets atteignables | `−2 / sommet` | limiter son territoire |
| centre inaccessible | `+1 500` | renforcer un blocage durable |

Recherche :

- profondeur configurable (`ctx.depth`, défaut 3) ;
- élagage Alpha-Beta avec ordonnancement BFS (vers le centre pour le voleur, vers le
  voleur pour la police) ;
- approfondissement itératif : le meilleur coup complet reste disponible si `deadline`
  expire ;
- coup retour au centre détecté comme défaite immédiate (`-MATE`) ;
- `Stats` alimente l'overlay pédagogique : nœuds, coupures, scores racine et arbre exploré.

## 2. Police — minimax alpha-bêta (`ai/minimax_police.py`)

La police utilise le **même squelette minimax** que le voleur : `minimax(...)` alterne
les nœuds MAX (police) et MIN (voleur), avec élagage alpha-bêta et approfondissement
itératif. La différence est l'évaluation feuille : au lieu d'une heuristique approximative,
elle consulte la table exacte décrite ci-dessous.

La police ne devine pas : elle **résout le jeu** une fois pour toutes pour un graphe et
un `RuleSet` donnés.

État encodé : `(voleur, p0, p1, p2, camp)` avec `p0 < p1 < p2` (symétrie des policiers
éliminée). Pour 21 sommets : `21 × C(20,3) × 2 = 47 880` positions, stockées dans un
entier `sid = ((((v*21+p0)*21+p1)*21+p2)<<1)|camp`.

Deux attracteurs inverses :

1. **Victoire police** : si toutes les issues du voleur sont occupées, l'état est gagnant
   pour la police ; tout parent policier menant à un état gagnant devient gagnant.
2. **Défaite voleur** : si le voleur peut rejoindre le centre, l'état est perdant ; tout
   parent voleur dont **tous** les fils sont perdants devient perdant.

La propagation suit les prédécesseurs avec un compteur de fils restants. Le cooldown est
géré séparément par `value_sid(sid, k)` : tant que `k < return_cooldown`, la valeur est
recalculée avec mémoïsation sur `(sid, k)` ; au-delà, la table terminale s'applique.

Valeurs : victoire = distance de capture, défaite = `1 000 000 − distance`, nulle = `500 000`.

Au choix du coup, la racine MAX maximise cette valeur exacte, puis départage avec :
1. moins de répétitions ; 2. territoire atteignable réduit ; 3. destination lexicographique.
Une valeur gagnante est transformée en nulle si elle déclencherait la 3ᵉ répétition.

## 3. Arbre exploré exporté

Les deux minimax construisent un `SearchNode` par nœud réellement visité lorsque
`ctx.collect_tree=True`. Chaque nœud porte `score`, `camp maximisant`, `coup`, `enfants` et
`cutoff`. Le moteur demande cet export en mode graphique ; le benchmark le désactive pour
rester léger.

`AsyncSearch` copie `Stats.tree` dans `Result.tree` à chaque recherche terminée. L'overlay
`T` affiche alors la racine du dernier niveau complet, les 12 meilleurs coups racine et
les coupures. Seul le dernier niveau complet est conservé : une recherche interrompue par la
limite de temps ne remplace pas l'arbre précédent.

## 4. Optimisation mesurée

Profilage `cProfile` avant optimisation : `3,514 s`, `_build = 2,409 s`, `_attractor =
0,846 s`, 209 310 appels à `sorted`.

Actions appliquées :

- codage `sid` en ligne au lieu d'appels de méthode ;
- tri explicite des policiers par comparaisons au lieu de `tuple(sorted(...))` ;
- `remaining` construit depuis les clés de `predecessors` (47 k au lieu de 389 k états) ;
- `setdefault` lié une fois dans `_build`.

Après optimisation : table initiale `~1 630 ms` (au lieu de `~2 141 ms`), cProfile total
`3,062 s`, 10/10 victoires policières contre voleur aléatoire et contre voleur Alpha-Beta.

Principe appliqué : **profiler avant d'optimiser** (skill
`wshobson/agents@python-performance-optimization`, voir `docs/SKILLS_USAGE.md`).

## 5. Vérifications

```powershell
python -m pytest -q
python tools/benchmark_ai.py --games 10 --depth 3
```

- `tests/test_bots.py` : présence des deux minimax explicites, légalité, déterminisme,
  export d'arbre visité, 5 victoires contre aléatoire, 3 contre Alpha-Beta.
- `tests/test_config.py` : traduction unique des réglages et contrat `Context`.
- `tests/test_match.py` : modes `AUTO` / `MANUEL`.
- Benchmark attendu : `police_win=10`, `thief_win=0`, `draw=0`, ~19 demi-coups/partie.
