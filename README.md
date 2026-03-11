# sofascore-api-stats

Le code historique du depot repose sur `requests` et des endpoints SofaScore qui renvoient souvent `403` aujourd'hui.

Pour recuperer les donnees du championnat marocain, utilise le script dedie [botola_pro.py](/Users/kotbrabhi/Desktop/Projets/draft/botola_pro.py).

## Installation

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

## Usage

```bash
python3 botola_pro.py
```

Le script ecrit par defaut un fichier JSON dans `data/botola-pro.json` contenant:

- les metadonnees du tournoi
- la saison courante
- le classement
- tous les matchs termines de la saison
- les incidents de match
- un sous-ensemble de statistiques collectives par match, filtre via [options.py](/Users/kotbrabhi/Desktop/Projets/draft/options.py)
- les lineups et statistiques individuelles des joueurs pour chaque match

Pour sortir un autre fichier:

```bash
python3 botola_pro.py --output exports/botola-pro.json
```

Pour sortir aussi une base SQLite:

```bash
python3 botola_pro.py --sqlite-output data/botola-pro.db
```

Pour ne pas recuperer les stats detaillees de chaque match:

```bash
python3 botola_pro.py --without-stats
```

Pour ne recuperer qu'un echantillon de matchs:

```bash
python3 botola_pro.py --limit 5
```

Pour garder les matchs mais sans stats joueurs:

```bash
python3 botola_pro.py --without-player-stats
```

## Schema SQLite

Si tu passes `--sqlite-output`, le script cree une base avec ces tables:

- `tournament_info`
- `standings`
- `matches`
- `match_team_statistics`
- `match_incidents`
- `player_appearances`
- `player_match_statistics`

Exemples utiles:

```sql
SELECT match_id, home_team_name, away_team_name, home_score, away_score
FROM matches
ORDER BY start_timestamp DESC;
```

```sql
SELECT pa.player_name, pms.stat_name, pms.stat_value
FROM player_match_statistics pms
JOIN player_appearances pa
  ON pa.match_id = pms.match_id
 AND pa.player_id = pms.player_id
WHERE pms.match_id = 14232831
ORDER BY pa.player_name, pms.stat_name;
```

```sql
SELECT player_name, stat_value AS goals
FROM player_match_statistics
JOIN player_appearances USING (match_id, player_id)
WHERE stat_name = 'goals' AND stat_value != '0'
ORDER BY CAST(stat_value AS INTEGER) DESC, player_name;
```

## Identifiant du championnat marocain

Le script cible la Botola Pro de SofaScore avec l'identifiant `uniqueTournamentId=937`, correspondant a la page publique:

- [Botola Pro sur SofaScore](https://www.sofascore.com/football/tournament/morocco/botola-pro/937)
