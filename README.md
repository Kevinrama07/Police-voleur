# POLICE – VOLEUR

Jeu de poursuite sur un plateau en forme de toile, en Python + Pygame. Trois policiers
traquent un voleur ; le voleur gagne s'il atteint le centre du plateau, la police gagne si
le voleur n'a plus aucun déplacement légal.

Le plateau du sujet est analysé depuis l'image fournie : ses sommets et ses arêtes sont
définis dans le graphe intégré au code (`core/graph.py`), et ses primitives géométriques
sont décrites dans `core/board_geometry.py`. Les pions sont rendus avec les images
`assets/images/voleur.png` et `assets/images/policier.png` (les identifiants du graphe
restent inchangés).

## Aperçu

| Mode | Description |
| --- | --- |
| **Automatique** | IA POLICE contre IA VOLEUR, graine reproductible, pause / pas à pas / vitesse. |
| **Solo** | Jouez le voleur ou la police ; l'autre camp est joué par son minimax. |
| **Manuel** | Deux joueurs sur le même écran : l'un déplace le voleur, l'autre un policier. |
| **Multijoueur** | Deux ordinateurs du même réseau local, serveur TCP autoritaire, choix des camps. |

L'interface suit une direction bleu nuit / bleu électrique / rouge, avec animations de
déplacement, halos des pièces actives, prévisualisation du coup de l'IA et overlays
(statistiques de recherche, écran de résultat).

## Installation

```powershell
python -m pip install -r requirements.txt
```

Prérequis : Python 3.11+ (testé sur 3.14), `pygame-ce`, `numpy`, `pillow`, `pytest`.

## Lancer le jeu

```powershell
python main.py
python main.py --mode auto --seed 12
python main.py --mode manuel --human-team thief
python main.py --mode manuel --human-team police
python main.py --mode multijoueur --role host
python main.py --mode multijoueur --role join
```

Menu :

- **Automatique** : lance IA vs IA.
- **Solo** : choisissez votre camp ; l'adversaire est joué par le minimax correspondant.
- **Manuel** : deux joueurs locaux (voleur puis police).
- **Multijoueur** : héberger ou rejoindre automatiquement, sans adresse IP à saisir.
- **Paramètres** : difficulté (Facile / Normal / Difficile), profondeur IA, temps de
  réflexion, vitesse d'animation, graine, cooldown du retour au centre, contestation du
  centre, limite de répétitions, limite de coups.
- **À propos** : règles, raccourcis, statistiques sauvegardées et crédits.

### Raccourcis

| Touche | Action |
| --- | --- |
| `Échap` | Retour / quitter l'écran courant |
| `Espace` | Pause / reprise (automatique) |
| `N` | Pas à pas (automatique) |
| `T` | Overlay statistiques IA et arbre Minimax exploré |
| `D` | Overlay debug (libellés français des intersections, arêtes, distances) |
| `V` | Plateau de référence (image d'origine) |
| `R` | Recommencer la partie |
| `F11` | Plein écran |
| `1` / `2` (salon réseau) | Prendre le camp voleur / police |

## Règles appliquées

- 3 policiers distincts sur le plateau, 1 voleur. Le centre est la zone de victoire du
  voleur.
- Alternance stricte : VOLEUR → 1 policier → VOLEUR → …
- Le voleur perd si `legal_moves(VOLEUR)` est vide ; la police perd si le voleur atteint le
  centre.
- **Retour au centre** : illégal tant que `ply < return_cooldown` (10 par défaut, réglable).
- **Centre contestable** : une fois le cooldown écoulé, les policiers peuvent entrer dans
  le centre (une case = une pièce).
- Match nul : position répétée 3 fois ou limite de coups atteinte (500 par défaut).
- Graine explicite : une même graine et les mêmes coups rejouent la même partie.

## IA

Deux bots indépendants, un seul contrat (`ai/contrat.py`), et **un minimax alpha-bêta
explicite pour chaque camp** :

- **Police** (`ai/minimax_police.py`) : minimax MAX avec évaluation feuille par table
  rétrograde exacte des 47 880 positions canoniques (`ai/exact_table.py`), filtre
  anti-répétition. Construction ~1,6 s une seule fois, mise en cache par graphe + règles.
- **Voleur** (`ai/minimax_voleur.py`) : minimax MIN avec heuristique 3 termes,
  approfondissement itératif et limite de temps.
- Recherche lancée dans un thread dédié (`AsyncSearch`) : la boucle graphique reste à
  60 FPS, la pause et le pas à pas fonctionnent même pendant une réflexion.
- L'overlay `T` affiche profondeur, nœuds, coupures, temps, scores racine et l'arbre des
  nœuds réellement visités (`Context.collect_tree=True`, `Result.tree`).

Détail algorithmique et mesures de profilage : [`docs/AI.md`](docs/AI.md).

### Benchmark (10 parties, graine 0)

| Profondeur | Temps / coup | Max | Nœuds / coup | Coups / partie | Issues |
| --- | --- | --- | --- | --- | --- |
| 3 (limite 1 s) | 24–29 ms | ~1–2 s | 44 | 19,4 | 10 victoires police |

Le pic correspond à la construction unique de la table policière. Reproduire :

```powershell
python tools/benchmark_ai.py --games 10 --depth 3
```

## Multijoueur réseau local

1. Machine A : **Multijoueur → Héberger** (ou `python main.py --mode multijoueur --role host`).
2. Machine B : **Multijoueur → Rejoindre** (ou `python main.py --mode multijoueur --role join`) ;
   l'hôte est détecté automatiquement sur le réseau local. Aucune adresse IP à saisir.
3. Si aucun hôte n'est trouvé, la recherche reprend automatiquement toutes les 2 s.
   Vérifiez le Wi-Fi, le broadcast UDP `50506` et autorisez Python dans le pare-feu Windows
   (réseau privé) sur les deux machines.
4. Choisir un camp chacun (Voleur / Police). Les camps identiques sont refusés par le
   serveur. La partie démarre automatiquement quand les deux camps sont prêts.
5. À la fin, **Rejouer** relance une revanche (rôles conservés, graine suivante).

Serveur TCP autonome (pour les clients compatibles avec le protocole) :

```powershell
python -m multiplayer.server --host 0.0.0.0 --port 50505 --seed 42
```

Protocole NDJSON sur TCP, serveur autoritaire (tour, `ply`, légalité vérifiés à chaque
coup), file de messages lue par la boucle Pygame. Détails :
[`docs/NETWORK_ARCHITECTURE.md`](docs/NETWORK_ARCHITECTURE.md).

## Tests

```powershell
python -m pytest -q
```

116 tests couvrent : fidélité du graphe au
dessin, initialisation, règles (cooldown, centre contestable, répétitions, blocage),
configuration et difficulté, bots (légalité, déterminisme, arbre exploré, victoires police),
modes AUTO/MANUEL/Solo, statistiques sauvegardées, protocole réseau, découverte UDP avec
relance automatique, démarrage CLI sans IP, session autoritaire, intégration TCP réelle,
contrôleurs et tests de rendu sans chevauchement.

Une CI GitHub Actions (`.github/workflows/ci.yml`) exécute les tests, la compilation et un
benchmark réduit à chaque push/PR.

## Structure

```
main.py                 point d'entrée (+ --mode auto|manuel|multijoueur --role host|join, --human-team)
config.py               réglages de l'application et presets de difficulté
match.py                moteur de match unique (AUTO/MANUEL/Solo)
stats.py                statistiques locales sauvegardées en JSON
net.py                  façade réseau (2 PC)
ai/                     contrat + minimax_voleur.py + minimax_police.py + exact_table.py
assets/images/          plateau d'origine
core/                   graphe, règles, état, gestionnaire de partie
docs/                   modèle du graphe, IA, analyse, réseau, méthodologie
interface/              thème, rendu du plateau, contrôles, écrans
modes/                  recherche asynchrone, contrôleur réseau
multiplayer/            protocole, découverte UDP, session, serveur, client
tests/                  suite Pytest
tools/                  benchmark IA
```

## Documentation

- [`docs/GRAPH_MODEL.md`](docs/GRAPH_MODEL.md) : graphe extrait, arêtes, règle du centre.
- [`docs/BOARD_ANALYSIS.md`](docs/BOARD_ANALYSIS.md) : géométrie et validation du plateau.
- [`docs/AI.md`](docs/AI.md) : contrat, minimax alpha-bêta des deux camps, table exacte de la police, optimisation.
- [`docs/NETWORK_ARCHITECTURE.md`](docs/NETWORK_ARCHITECTURE.md) : protocole et serveur.
- [`docs/SKILLS_USAGE.md`](docs/SKILLS_USAGE.md) : méthodologie de développement.

## Dépannage

- **Rejoindre ne trouve pas la partie** : la recherche se relance seule ; vérifier que les
  deux machines sont sur le même réseau local, que le broadcast UDP `50506` n'est pas
  bloqué et que Python est autorisé dans le pare-feu Windows (réseau privé).
- **Le plateau ne s'affiche pas** : vérifier `assets/images/board.png` depuis la racine
  du projet.
- **Aucun son** : le jeu n'utilise pas d'audio.
