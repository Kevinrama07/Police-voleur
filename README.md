# POLICE – VOLEUR

Jeu de poursuite sur un plateau en forme de toile, en Python + Pygame. Trois policiers
traquent un voleur ; le voleur gagne s'il atteint le centre du plateau, la police gagne si
le voleur n'a plus aucun déplacement légal.

Le plateau du sujet est analysé depuis l'image fournie : ses sommets et ses arêtes sont
définis dans le graphe intégré au code (`core/graph.py`), et ses primitives géométriques
sont décrites dans `core/board_geometry.py`.

## Aperçu

| Mode | Description |
| --- | --- |
| **Démonstration** | IA POLICE contre IA VOLEUR, graine reproductible, pause / pas à pas / vitesse. |
| **Solo** | Vous jouez le voleur ou la police contre l'IA Minimax du camp adverse. |
| **Multijoueur** | Deux ordinateurs du même réseau local, serveur TCP autoritaire, choix des camps. |

L'interface suit une direction bleu nuit / bleu électrique / rouge, avec animations de
déplacement, halos des pièces actives, prévisualisation du coup de l'IA et overlays
(arbre Minimax exploré, écran de résultat).

## Installation

```powershell
python -m pip install -r requirements.txt
```

Prérequis : Python 3.11+ (testé sur 3.14), `pygame-ce`, `numpy`, `pillow`, `pytest`.

## Lancer le jeu

```powershell
python main.py
```

Menu :

- **Démonstration** : lance IA vs IA.
- **Solo** : choisir VOLEUR ou POLICE.
- **Multijoueur** : héberger ou rejoindre.
- **Paramètres** : profondeur IA, temps de réflexion, vitesse de démo, graine, cooldown du
  retour au centre, contestation du centre, limite de répétitions, limite de coups.
- **À propos** : règles, raccourcis et crédits.

### Raccourcis

| Touche | Action |
| --- | --- |
| `Échap` | Retour / quitter l'écran courant |
| `Espace` | Pause / reprise (démo) |
| `N` | Pas à pas (démo) |
| `T` | Overlay arbre Minimax |
| `D` | Overlay debug (sommets, arêtes, distances) |
| `V` | Plateau de référence (image d'origine) |
| `R` | Recommencer la partie |
| `F11` | Plein écran |
| `1` / `2` (solo) | Choisir voleur / police |
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

- Minimax avec élagage alpha-bêta, approfondissement itératif, table de transposition
  bornée par sommet et demi-coup, limite de temps stricte.
- Évaluation par distances BFS : contrôle des issues, distance du voleur au centre,
  mobilité, cohésion des policiers, sécurité du centre.
- Recherche lancée dans un thread dédié (`AsyncSearch`) : la boucle graphique reste à
  60 FPS, la pause et le pas à pas fonctionnent même pendant une réflexion.
- Rejouer l'arbre : l'overlay `T` affiche les nœuds réellement visités (jusqu'à 2 niveaux),
  scores, coupures et statistiques de la recherche.

### Benchmark (20 parties, graine 0)

| Profondeur | Temps / coup | Max | Nœuds / coup | Coups / partie | Issues |
| --- | --- | --- | --- | --- | --- |
| 3 (limite 1 s) | 52,96 ms | 323 ms | 165 | 35,1 | 1 victoire police, 19 nulles |
| 4 (limite 1 s) | 163,16 ms | 689 ms | 539 | 18,8 | 10 nulles |

Les nulles proviennent de la règle de répétition (les deux IA évitent la perte en
alternant) ; elles sont un résultat valide du règlement. Reproduire :

```powershell
python tools/benchmark_ai.py --games 20 --depth 3 --seed 0
```

## Multijoueur réseau local

1. Machine A : **Multijoueur → Héberger** pour créer une partie. L'adresse `IP:port` de
   l'hôte s'affiche dans le salon.
2. Machine B : **Multijoueur → Rejoindre** ; l'hôte est recherché automatiquement sur le
   réseau local pendant quelques secondes. Si aucun hôte n'est trouvé, vérifiez le réseau
   local et le pare-feu Windows, puis réessayez. Autoriser Python dans le pare-feu Windows
   (réseau privé) sur les deux machines.
3. Si la découverte UDP est bloquée (pare-feu, VLAN, VPN), saisir l'adresse affichée chez
   l'hôte dans **Connexion directe (IP:port)** puis cliquer sur **Se connecter**.
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

108 tests couvrent : fidélité du graphe au
dessin, initialisation, règles (cooldown, centre contestable, répétitions, blocage), IA
(légalité, déterminisme, budget de temps), protocole réseau, découverte automatique UDP,
filtrage des parties complètes, connexion directe, hébergement malgré un port de
découverte occupé, annulation de recherche, session autoritaire, intégration TCP réelle,
contrôleurs de mode et tests de rendu sans chevauchement.

## Structure

```
main.py                 point d'entrée
config.py               réglages de l'application
ai/                     évaluation + Minimax/alpha-bêta
assets/images/          plateau d'origine
core/                   graphe, règles, état, gestionnaire de partie
docs/                   modèle du graphe, IA, analyse, réseau, méthodologie
interface/              thème, rendu du plateau, contrôles, écrans
modes/                  contrôleurs démo / solo / réseau + recherche asynchrone
multiplayer/            protocole, découverte UDP, session, serveur, client, façade réseau
tests/                  suite Pytest
tools/                  benchmark IA
```

## Documentation

- [`docs/GRAPH_MODEL.md`](docs/GRAPH_MODEL.md) : graphe extrait, arêtes, règle du centre.
- [`docs/BOARD_ANALYSIS.md`](docs/BOARD_ANALYSIS.md) : géométrie et validation du plateau.
- [`docs/AI.md`](docs/AI.md) : évaluation, recherche, budget de temps, benchmark.
- [`docs/NETWORK_ARCHITECTURE.md`](docs/NETWORK_ARCHITECTURE.md) : protocole et serveur.
- [`docs/SKILLS_USAGE.md`](docs/SKILLS_USAGE.md) : méthodologie de développement.

## Dépannage

- **Rejoindre ne trouve pas la partie** : vérifier que les deux machines sont sur le même
  réseau local et que Python est autorisé dans le pare-feu Windows (réseau privé) ; en cas
  de doute, utiliser la **Connexion directe (IP:port)** avec l'adresse affichée chez l'hôte.
- **Le plateau ne s'affiche pas** : vérifier `assets/images/board.png` depuis la racine
  du projet.
- **Aucun son** : le jeu n'utilise pas d'audio.
