# Utilisation des Skills — POLICE – VOLEUR

## 1. Procédure suivie

1. **Énumération** des Skills réellement installés :
   - `C:\Users\Kevin\.claude\skills\` (52 entrées) ;
   - `C:\Users\Kevin\.config\opencode\skills\` ;
   - `C:\Users\Kevin\.agents\skills\` ;
   - répertoires locaux du projet : `.opencode/skills/`, `.claude/skills/`, `.agents/skills/` →
     **aucun Skill local au projet** (répertoires absents).
2. **Lecture intégrale** des `SKILL.md` des Skills potentiellement pertinents avant toute utilisation :
   `frontend-design` et `modern-web-design`.
3. **Filtrage** : le projet est une application desktop **Python + Pygame + Socket TCP** (choix
   technologique définitif). Aucun Skill spécialisé Python, Pygame, jeux ou réseau TCP n'est installé.
4. **Aucun Skill n'a été utilisé comme substitut d'une bibliothèque du projet** : les Skills retenus
   n'ont servi que de guides de conception visuelle (principes transférables), jamais de dépendances.

## 2. Skills examinés et décision

| Skill | Chemin | Utilité pour le projet | Partie concernée | Décision |
|---|---|---|---|---|
| **frontend-design** | `C:\Users\Kevin\.agents\skills\frontend-design\SKILL.md` | Direction artistique : intentionnalité, hiérarchie, typographie distinctive, éviter les esthétiques génériques | PHASE 4 (interface, menus, HUD) | **Retenu** (principes transposés à Pygame) |
| **modern-web-design** | `C:\Users\Kevin\.config\opencode\skills\modern-web-design\SKILL.md` | Minimalisme maîtrisé, palette limitée, échelles d'espacement/typographie, micro-interactions, timings d'animation, contraste | PHASE 4 (design system du jeu) | **Retenu** (principes uniquement, aucune techno web) |
| **pixijs-2d** | `C:\Users\Kevin\.claude\skills\pixijs-2d\SKILL.md` | Rendu 2D/animation | — | **Non retenu** : moteur graphique imposé = Pygame |
| **webapp-testing** | `C:\Users\Kevin\.claude\skills\webapp-testing\SKILL.md` | Validation d'applications web | — | **Non retenu** : tests imposés = Pytest |
| **skill-creator** | `C:\Users\Kevin\.claude\skills\skill-creator\SKILL.md` | Création d'un Skill spécialisé | — | **Non utilisé** : aucune nécessité justifiée |
| Autres Skills installés (threejs, react-three-fiber, babylonjs, aframe, gsap, expo-*, motion-framer, mcp-builder, etc.) | — | — | — | **Non retenus** : orientés web/React/3D web, hors périmètre |

## 3. Consignes réellement appliquées

### Depuis `frontend-design`

- **Direction artistique intentionnelle** : identité « jeu de stratégie moderne, minimaliste, bleu nuit /
  bleu électrique / rouge » (imposée par le cahier des charges), exécutée avec précision.
- **Éviter les rendus génériques** : composants dessinés (boutons, panneaux, anneaux de sélection)
  plutôt que des rectangles bruts ; cohérence des formes et des rayons.
- **Typographie** : une police d'affichage pour les titres + une police de texte lisible, résolues
  parmi les polices système par ordre de préférence (`Segoe UI`, `Calibri`, `Verdana`, `Arial` ;
  monospace `Consolas`, `Cascadia Mono`, `Courier New`), sans dépendance à un fichier local.
- **Composition spatiale** : plateau comme élément central, panneau latéral d'informations,
  marges généreuses, grille d'espacement régulière.

### Depuis `modern-web-design`

- **Palette limitée** (3–5 couleurs dominantes + neutres) avec accents francs — transposée en
  constantes de thème Pygame.
- **Échelle typographique** hiérarchisée (titre, sous-titre, corps, légende) et **échelle
  d'espacement** (4/8/12/16/24/32 px) appliquées à tous les écrans.
- **Micro-interactions** : survol (~1,05×), appui (0,95×), transitions 150–250 ms, easings naturels ;
  feedback de sélection et de personnage actif.
- **Timings d'animation** centralisés (`150 ms` rapide, `250 ms` standard, `400 ms` ample) ;
  animations au service de la lisibilité, jamais décoratives au détriment des règles.
- **Contraste** : texte clair sur fond bleu nuit (ratio élevé), couleurs d'équipe distinctes
  (bleu police / rouge voleur) et signalétique de sélection non chromatique (formes) en complément.
- **Panneau IA** (mode démo) traité comme un tableau de bord : hiérarchie claire, chiffres
  alignés, libellés courts, densité contrôlée.

## 4. Limites assumées

- Aucun Skill installé ne couvre **Python, Pygame, Socket TCP, Minimax/Alpha-Beta ou la théorie des
  graphes** : ces parties sont développées selon les bonnes pratiques d'ingénierie (architecture
  modulaire, typage, tests Pytest), sans prétendre qu'un Skill a été utilisé.
- Les Skills web n'ont **jamais** introduit de technologie web dans le projet : Pygame reste le seul
  moteur graphique, Pytest le seul outillage de test.
