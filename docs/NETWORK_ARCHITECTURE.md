# Architecture réseau

Le mode multijoueur relie deux ordinateurs du même réseau local via un serveur TCP
autoritaire. Aucun client ne décide de l'état : le serveur valide chaque intention puis
diffuse l'état complet. L'interface ne fait que refléter les messages reçus.

```
┌──────────────┐   TCP/NDJSON    ┌──────────────────────────┐   TCP/NDJSON   ┌──────────────┐
│ Client hôte  │ ◀────────────▶ │ GameServer + GameSession │ ◀────────────▶ │ Client invité│
│  Pygame      │                 │  (autorité des règles)   │                │  Pygame      │
└──────────────┘                 └──────────────────────────┘                └──────────────┘
```

L'hôte démarre un serveur embarqué puis s'y connecte comme un client ordinaire
(`127.0.0.1`) : les deux joueurs suivent exactement le même chemin de code.

## Fichiers

| Fichier | Rôle |
| --- | --- |
| `multiplayer/protocol.py` | Encodage NDJSON, décodeur tolérant aux fragments et aux lignes invalides, limites de taille. |
| `multiplayer/session.py` | `GameSession` : rôles, démarrage, validation des coups, revanche, abandons. Aucune socket. |
| `multiplayer/discovery.py` | Découverte UDP locale des hôtes (port, occupation, état), avec repli par adresse directe. |
| `multiplayer/server.py` | `GameServer` : acceptation des connexions, threads de lecture, diffusion, arrêt propre. |
| `multiplayer/client.py` | `GameClient` : connexion, réception continue, envoi sérialisé. |
| `multiplayer/network_manager.py` | Façade UI : hébergement/découverte/connexion, file de messages, roster, rôle local. |
| `modes/multiplayer.py` | `NetworkController` : miroir de l'état serveur, clics, envoi de coups, resynchronisation. |
| `interface/screens/network_setup.py` | Écran Héberger / Rejoindre et salon de choix des camps. |

## Protocole

- Transport : TCP, messages **JSON sur une ligne** (NDJSON), UTF-8, terminés par `\n`.
- Découverte : requête/réponse UDP locale sur le port `50506` ; la réponse annonce le port
  TCP, le nombre de joueurs et l'état (partie lancée ou non). Les serveurs complets ou déjà
  lancés sont ignorés. La requête est diffusée sur `255.255.255.255`, la boucle locale et
  le broadcast `/24` de chaque interface, pendant quatre secondes ; l'invité ouvre ensuite
  sa connexion TCP habituelle. Un mode **Connexion directe (IP:port)** sert de repli quand
  la diffusion est bloquée, et l'hôte affiche son adresse dans le salon.
- Taille maximale d'une ligne : 65 536 octets ; tampon incomplet maximal : 1 Mio.
- Une ligne illisible est signalée (`malformed_message`) puis ignorée : le serveur ne
  ferme pas la connexion. Un flux qui dépasse le tampon maximal est coupé
  (`protocol_error`).
- Version : `PROTOCOL_VERSION = 1`, annoncée dans `WELCOME`.

### Messages serveur → client

| Type | Contenu | Quand |
| --- | --- | --- |
| `WELCOME` | `protocol`, `player_id`, `game_id` | À la connexion. |
| `JOIN_GAME` | `players`, `available_roles`, `started`, `game_id`, `max_players` | À chaque arrivée, choix de rôle ou départ. |
| `ROLE_CONFIRMED` | `role`, `player_id` | Le camp demandé est accepté. |
| `GAME_START` | `state`, `ply`, `turn`, `players`, `seed`, `rules`, `config` | Les deux camps sont prêts, ou revanche. |
| `GAME_STATE` | `state`, `ply`, `turn`, `status`, `move` | Après chaque coup accepté. |
| `MOVE_ACCEPTED` | `move`, `ply` | Accusé destiné à l'auteur du coup. |
| `MOVE_REJECTED` | `code`, `reason`, `ply` | Coup refusé, destiné à l'auteur. |
| `GAME_OVER` | `status`, `ply`, `detail` | Fin de partie. |
| `PLAYER_DISCONNECTED` | `player_id`, `reason`, `started` | Un joueur a quitté. |
| `ERROR` | `code`, `message`, éventuellement `available_roles` | Refus explicite. |
| `PONG` | — | Réponse à `PING`. |

### Messages client → serveur

| Type | Contenu | Contrôles serveur |
| --- | --- | --- |
| `SELECT_ROLE` | `role` (`police`/`thief`) | Joueur connu, partie non commencée, camp libre. |
| `MOVE` | `move` (dict `Move`), `ply` | Tour du joueur, `ply` courant, légalité complète. |
| `CREATE_GAME` | `seed` optionnel | Partie terminée ou interrompue, deux camps prêts. |
| `PING` | — | Répond `PONG`. |

### Codes d'erreur

`server_full`, `protocol_error`, `malformed_message`, `unknown_message`, `server_error`,
`unknown_player`, `invalid_role`, `role_conflict`, `game_started`, `roles_missing`,
`not_started`, `abandoned`, `no_role`, `not_your_turn`, `stale_move`, `malformed_move`,
`illegal_move`, `game_running`.

## Autorité et validation

`GameSession.apply_move` applique, dans cet ordre :

1. partie démarrée et non abandonnée ;
2. joueur connu et rôle choisi ;
3. `state.turn == role` du joueur ;
4. `ply` client égal au `ply` serveur (`stale_move` sinon) ;
5. désérialisation du `Move` ;
6. appartenance à `legal_moves(graph, state, rules, ply)` ;
7. application au `GameManager`, puis diffusion de l'état complet.

Conséquences : un client modifié ne peut ni jouer hors tour, ni jouer un coup illégal, ni
sauter un demi-coup. Le client recalcule néanmoins la légalité localement pour l'affichage
et pour détecter une désynchronisation (`_resync`).

## Déroulement d'une partie

```
Hôte                       Serveur                        Invité
 │  WELCOME/JOIN_GAME ──────▶│                               │
 │                          │◀────────── WELCOME/JOIN_GAME  │
 │  SELECT_ROLE(police) ────▶│                               │
 │◀── ROLE_CONFIRMED ───────│─── JOIN_GAME ────────────────▶│
 │                          │◀────────── SELECT_ROLE(thief) │
 │◀──────── GAME_START ─────│──── GAME_START ──────────────▶│
 │                          │◀────────── MOVE (ply=0)       │
 │◀──────── GAME_STATE ─────│──── MOVE_ACCEPTED + STATE ───▶│
 │  MOVE (ply=1) ──────────▶│                               │
 │◀── MOVE_ACCEPTED+STATE ──│────────── GAME_STATE ────────▶│
```

- Le **voleur commence** ; les camps sont tirés au choix des joueurs, pas au hasard.
- Dès que les deux camps sont choisis, le serveur démarre sans intervention de l'hôte.
- À la fin, l'un des deux joueurs peut lancer une **revanche** (`CREATE_GAME`) : les rôles
  sont conservés et la graine est incrémentée.
- Si un joueur se déconnecte en cours de partie, l'autre reçoit
  `PLAYER_DISCONNECTED` : la partie passe en « connexion perdue », le bouton Rejouer est
  désactivé et le retour au menu ferme la connexion. Le serveur réinitialise alors la
  session pour qu'un nouveau joueur puisse rejoindre.

## Threads et boucle graphique

- Serveur : un thread d'acceptation + un thread de lecture par pair ; les écritures sont
  protégées par un verrou par pair.
- Découverte : un thread UDP côté hôte répond aux recherches locales ; si le port `50506`
  est occupé, l'hébergement continue avec un avertissement et la connexion directe reste
  disponible. Le bouton Rejoindre effectue la recherche hors de la boucle graphique,
  permet une nouvelle tentative et s'annule au retour au menu sans conserver une connexion
  tardive. La connexion directe utilise le même mécanisme de thread.
- Client : un thread de réception ; chaque message est déposé dans une `Queue`.
- Pygame ne lit jamais une socket : `NetworkManager.poll()` vide la file à chaque frame.
- Aucun calcul de règles n'a lieu dans un thread réseau côté client : seuls la
  désérialisation et le dépôt en file y ont lieu.
- Générations de connexion : chaque `GameClient` porte un numéro de génération ; les
  callbacks d'un ancien client sont ignorés, ce qui évite les courses lors d'une
  reconnexion.

## Robustesse

- Troisième connexion : `ERROR server_full` puis fermeture.
- Ligne JSON invalide : `ERROR malformed_message`, connexion conservée.
- Ligne > 64 Kio : rejetée ; tampon > 1 Mio sans fin de ligne : `protocol_error` + fermeture.
- Message fragmenté : reconstruit par `MessageDecoder`.
- Coup en double ou périmé : `stale_move` / `not_your_turn`.
- Fermeture locale : `GameClient.close()` arrête proprement le thread ; `GameServer.stop()`
  ferme les pairs et joint le thread d'acceptation.

## Tests

`tests/test_network.py` couvre :

- protocole : aller-retour, message trop gros, flux fragmenté, lignes invalides, tampon saturé ;
- session : deux joueurs maximum, conflit de rôle, validation complète des coups
  (`not_started`, `not_your_turn`, `illegal_move`, `stale_move`, `malformed_move`),
  abandon + réintégration + revanche ;
- intégration TCP réelle sur `127.0.0.1:0` : attribution des joueurs, conflit de rôle,
  partie complète sur deux demi-coups, coup hors tour, `stale_move`, troisième joueur
  refusé, entrée fragmentée/illisible, déconnexion signalée, revanche refusée en cours de
  partie ; découverte UDP de l'hôte (filtrage des parties pleines/lancées), hébergement
  malgré un port de découverte occupé, analyse de l'adresse directe, connexion directe
  depuis l'écran et annulation de recherche.

`tests/test_modes.py` couvre le miroir client (`NetworkController`) : application d'un état
serveur, envoi d'un coup police avec `ply`, rejet, resynchronisation sur trou de `ply`,
abandon.

## Test manuel sur deux machines

1. Machine A : lancer l'application → **Multijoueur** → **Héberger** ; noter l'adresse
   `IP:port` affichée dans le salon.
2. Autoriser Python dans le pare-feu Windows (réseau privé) sur les deux machines.
3. Machine B : **Multijoueur** → **Rejoindre** ; l'hôte est détecté automatiquement. En cas
   d'échec, saisir l'adresse de l'hôte dans **Connexion directe (IP:port)**.
4. Choisir un camp chacun (les camps identiques sont refusés) : la partie démarre.
5. Pour un serveur autonome, utiliser des clients compatibles avec le protocole TCP ; la
   recherche automatique ne détecte que les hôtes lancés depuis l'application.

## Limites assumées

- Pas d'authentification ni de chiffrement : le mode est prévu pour un réseau local de
  confiance. Ne pas exposer le port sur Internet.
- Découverte : un port UDP unique pour toutes les instances ; avec plusieurs hôtes sur le
  même réseau, le premier serveur joignable répond (les parties pleines sont ignorées).
  Utiliser la connexion directe pour viser un hôte précis.
- Une seule partie par serveur, deux joueurs, pas de reconnexion automatique en cours de
  partie (le joueur restant revient au menu pour réhéberger).
