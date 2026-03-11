from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

import options as o

BOTOLA_PRO = {
    "name": "Botola Pro",
    "country": "Morocco",
    "slug": "botola-pro",
    "uniqueTournamentId": 937,
    "seasonLabel": "25/26",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recupere les standings et matchs termines de la Botola Pro depuis SofaScore."
    )
    parser.add_argument(
        "--output",
        default="data/botola-pro.json",
        help="Chemin du fichier JSON de sortie.",
    )
    parser.add_argument(
        "--sqlite-output",
        default=None,
        help="Chemin du fichier SQLite de sortie.",
    )
    parser.add_argument(
        "--without-stats",
        action="store_true",
        help="N'inclut ni les statistiques de match ni les statistiques joueurs.",
    )
    parser.add_argument(
        "--without-team-stats",
        action="store_true",
        help="N'inclut pas les statistiques collectives de match.",
    )
    parser.add_argument(
        "--without-player-stats",
        action="store_true",
        help="N'inclut pas les compositions et statistiques joueurs.",
    )
    parser.add_argument(
        "--without-incidents",
        action="store_true",
        help="N'inclut pas la timeline des incidents de match.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite le nombre de matchs exportes.",
    )
    return parser.parse_args()


def extract_team_statistics(stats_payload: dict[str, Any]) -> list[dict[str, Any]]:
    periods = stats_payload.get("statistics", [])
    if not periods:
        return []

    all_period = next((period for period in periods if period.get("period") == "ALL"), periods[0])
    filtered_items: list[dict[str, Any]] = []
    for group in all_period.get("groups", []):
        if group.get("groupName") not in o.groups:
            continue
        for item in group.get("statisticsItems", []):
            if item.get("name") in o.statisticsItems:
                filtered_items.append(item)
    return filtered_items


def map_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event["id"],
        "round": event.get("roundInfo", {}).get("round"),
        "startTimestamp": event.get("startTimestamp"),
        "status": event.get("status", {}),
        "homeTeam": event.get("homeTeam", {}),
        "awayTeam": event.get("awayTeam", {}),
        "homeScore": event.get("homeScore", {}),
        "awayScore": event.get("awayScore", {}),
        "winnerCode": event.get("winnerCode"),
        "slug": event.get("slug"),
    }


def map_player_entry(entry: dict[str, Any]) -> dict[str, Any]:
    player = entry.get("player", {})
    return {
        "player": {
            "id": player.get("id"),
            "name": player.get("name"),
            "slug": player.get("slug"),
            "shortName": player.get("shortName"),
            "position": player.get("position"),
            "jerseyNumber": player.get("jerseyNumber"),
            "height": player.get("height"),
            "dateOfBirthTimestamp": player.get("dateOfBirthTimestamp"),
            "country": player.get("country"),
            "proposedMarketValueRaw": player.get("proposedMarketValueRaw"),
        },
        "position": entry.get("position"),
        "shirtNumber": entry.get("shirtNumber"),
        "jerseyNumber": entry.get("jerseyNumber"),
        "substitute": entry.get("substitute"),
        "statistics": entry.get("statistics", {}),
    }


def map_lineup_side(side_data: dict[str, Any]) -> dict[str, Any]:
    players = side_data.get("players", [])
    return {
        "formation": side_data.get("formation"),
        "playerColor": side_data.get("playerColor"),
        "goalkeeperColor": side_data.get("goalkeeperColor"),
        "missingPlayers": side_data.get("missingPlayers", []),
        "starters": [map_player_entry(entry) for entry in players if not entry.get("substitute")],
        "substitutes": [map_player_entry(entry) for entry in players if entry.get("substitute")],
    }


async def get_lineups(api: Any, match_id: int) -> dict[str, Any]:
    data = await api._get(f"/event/{match_id}/lineups")
    return {
        "confirmed": data.get("confirmed"),
        "home": map_lineup_side(data.get("home", {})),
        "away": map_lineup_side(data.get("away", {})),
        "statisticalVersion": data.get("statisticalVersion"),
    }


async def build_match_payload(
    api: Any,
    event: dict[str, Any],
    include_team_stats: bool,
    include_player_stats: bool,
    include_incidents: bool,
) -> dict[str, Any]:
    from sofascore_wrapper.match import Match

    match_payload = map_event(event)
    match = Match(api, event["id"])

    if include_incidents:
        incidents = await match.incidents()
        match_payload["incidents"] = incidents.get("incidents", [])
        match_payload["incidentSummary"] = {
            "home": incidents.get("home", []),
            "away": incidents.get("away", []),
        }

    if include_team_stats:
        stats_payload = await match.stats()
        match_payload["teamStatistics"] = extract_team_statistics(stats_payload)

    if include_player_stats:
        match_payload["lineups"] = await get_lineups(api, event["id"])

    return match_payload


def map_standings(standings_payload: dict[str, Any]) -> list[dict[str, Any]]:
    standings = standings_payload.get("standings", [])
    if not standings:
        return []

    rows = standings[0].get("rows", [])
    result: list[dict[str, Any]] = []
    for row in rows:
        team = row.get("team", {})
        result.append(
            {
                "position": row.get("position"),
                "points": row.get("points"),
                "matches": row.get("matches"),
                "wins": row.get("wins"),
                "draws": row.get("draws"),
                "losses": row.get("losses"),
                "scoresFor": row.get("scoresFor"),
                "scoresAgainst": row.get("scoresAgainst"),
                "scoreDiffFormatted": row.get("scoreDiffFormatted"),
                "team": {
                    "id": team.get("id"),
                    "name": team.get("name"),
                    "slug": team.get("slug"),
                    "shortName": team.get("shortName"),
                    "teamColors": team.get("teamColors"),
                },
            }
        )
    return result


async def build_payload(
    include_team_stats: bool,
    include_player_stats: bool,
    include_incidents: bool,
    limit: int | None,
) -> dict[str, Any]:
    try:
        from sofascore_wrapper.api import SofascoreAPI
        from sofascore_wrapper.league import League
    except ImportError as exc:
        raise SystemExit(
            "Dependances manquantes. Installe d'abord: pip install -r requirements.txt "
            "puis python -m playwright install chromium"
        ) from exc

    api = SofascoreAPI()
    try:
        league = League(api, BOTOLA_PRO["uniqueTournamentId"])
        season = await league.current_season()
        if not season:
            raise RuntimeError("Impossible de recuperer la saison courante de la Botola Pro.")

        season_id = season["id"]
        current_round = await league.current_round(season_id)
        standings = await league.standings(season_id)

        finished_events: list[dict[str, Any]] = []
        for round_id in range(1, (current_round or 0) + 1):
            round_payload = await league.league_fixtures_per_round(season_id, round_id)
            for event in round_payload.get("events", []):
                if event.get("status", {}).get("code") != 100:
                    continue

                event_data = await build_match_payload(
                    api,
                    event,
                    include_team_stats=include_team_stats,
                    include_player_stats=include_player_stats,
                    include_incidents=include_incidents,
                )
                finished_events.append(event_data)
                if limit is not None and len(finished_events) >= limit:
                    return {
                        "tournament": BOTOLA_PRO,
                        "season": season,
                        "currentRound": current_round,
                        "standings": map_standings(standings),
                        "events": finished_events,
                    }

        return {
            "tournament": BOTOLA_PRO,
            "season": season,
            "currentRound": current_round,
            "standings": map_standings(standings),
            "events": finished_events,
        }
    finally:
        await api.close()


def write_output(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS tournament_info (
            unique_tournament_id INTEGER PRIMARY KEY,
            name TEXT,
            country TEXT,
            slug TEXT,
            season_id INTEGER,
            season_year TEXT,
            current_round INTEGER
        );

        CREATE TABLE IF NOT EXISTS standings (
            team_id INTEGER PRIMARY KEY,
            position INTEGER,
            points INTEGER,
            matches INTEGER,
            wins INTEGER,
            draws INTEGER,
            losses INTEGER,
            scores_for INTEGER,
            scores_against INTEGER,
            score_diff_formatted TEXT,
            team_name TEXT,
            team_slug TEXT,
            team_short_name TEXT,
            team_colors_json TEXT
        );

        CREATE TABLE IF NOT EXISTS matches (
            match_id INTEGER PRIMARY KEY,
            round INTEGER,
            start_timestamp INTEGER,
            status_code INTEGER,
            status_description TEXT,
            status_type TEXT,
            winner_code INTEGER,
            slug TEXT,
            home_team_id INTEGER,
            home_team_name TEXT,
            away_team_id INTEGER,
            away_team_name TEXT,
            home_score INTEGER,
            away_score INTEGER
        );

        CREATE TABLE IF NOT EXISTS match_team_statistics (
            match_id INTEGER,
            group_name TEXT,
            statistic_name TEXT,
            home_value TEXT,
            away_value TEXT,
            home_display_value TEXT,
            away_display_value TEXT,
            PRIMARY KEY (match_id, group_name, statistic_name),
            FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS match_incidents (
            match_id INTEGER,
            incident_order INTEGER,
            incident_type TEXT,
            time INTEGER,
            added_time INTEGER,
            home_score INTEGER,
            away_score INTEGER,
            is_live INTEGER,
            team_side TEXT,
            player_id INTEGER,
            player_name TEXT,
            assist_1_id INTEGER,
            assist_1_name TEXT,
            assist_2_id INTEGER,
            assist_2_name TEXT,
            text TEXT,
            raw_json TEXT,
            PRIMARY KEY (match_id, incident_order),
            FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS player_appearances (
            match_id INTEGER,
            player_id INTEGER,
            team_side TEXT,
            squad_role TEXT,
            team_id INTEGER,
            player_name TEXT,
            player_slug TEXT,
            player_short_name TEXT,
            player_position TEXT,
            jersey_number TEXT,
            shirt_number INTEGER,
            height INTEGER,
            date_of_birth_timestamp INTEGER,
            country_json TEXT,
            market_value_json TEXT,
            statistics_json TEXT,
            PRIMARY KEY (match_id, player_id),
            FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS player_match_statistics (
            match_id INTEGER,
            player_id INTEGER,
            team_side TEXT,
            stat_name TEXT,
            stat_value TEXT,
            PRIMARY KEY (match_id, player_id, stat_name),
            FOREIGN KEY (match_id, player_id) REFERENCES player_appearances(match_id, player_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_matches_home_team ON matches(home_team_id);
        CREATE INDEX IF NOT EXISTS idx_matches_away_team ON matches(away_team_id);
        CREATE INDEX IF NOT EXISTS idx_incidents_player ON match_incidents(player_id);
        CREATE INDEX IF NOT EXISTS idx_player_appearances_player ON player_appearances(player_id);
        CREATE INDEX IF NOT EXISTS idx_player_stats_name ON player_match_statistics(stat_name);
        """
    )


def write_sqlite(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        ensure_schema(connection)

        tournament = payload.get("tournament", {})
        season = payload.get("season", {})
        connection.execute("DELETE FROM tournament_info")
        connection.execute("DELETE FROM standings")
        connection.execute("DELETE FROM matches")

        connection.execute(
            """
            INSERT INTO tournament_info (
                unique_tournament_id, name, country, slug, season_id, season_year, current_round
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tournament.get("uniqueTournamentId"),
                tournament.get("name"),
                tournament.get("country"),
                tournament.get("slug"),
                season.get("id"),
                season.get("year"),
                payload.get("currentRound"),
            ),
        )

        for row in payload.get("standings", []):
            team = row.get("team", {})
            connection.execute(
                """
                INSERT INTO standings (
                    team_id, position, points, matches, wins, draws, losses, scores_for,
                    scores_against, score_diff_formatted, team_name, team_slug,
                    team_short_name, team_colors_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team.get("id"),
                    row.get("position"),
                    row.get("points"),
                    row.get("matches"),
                    row.get("wins"),
                    row.get("draws"),
                    row.get("losses"),
                    row.get("scoresFor"),
                    row.get("scoresAgainst"),
                    row.get("scoreDiffFormatted"),
                    team.get("name"),
                    team.get("slug"),
                    team.get("shortName"),
                    json.dumps(team.get("teamColors"), ensure_ascii=False),
                ),
            )

        for event in payload.get("events", []):
            home_team = event.get("homeTeam", {})
            away_team = event.get("awayTeam", {})
            status = event.get("status", {})
            home_score = event.get("homeScore", {})
            away_score = event.get("awayScore", {})

            connection.execute(
                """
                INSERT INTO matches (
                    match_id, round, start_timestamp, status_code, status_description, status_type,
                    winner_code, slug, home_team_id, home_team_name, away_team_id, away_team_name,
                    home_score, away_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.get("id"),
                    event.get("round"),
                    event.get("startTimestamp"),
                    status.get("code"),
                    status.get("description"),
                    status.get("type"),
                    event.get("winnerCode"),
                    event.get("slug"),
                    home_team.get("id"),
                    home_team.get("name"),
                    away_team.get("id"),
                    away_team.get("name"),
                    home_score.get("current"),
                    away_score.get("current"),
                ),
            )

            for item in event.get("teamStatistics", []):
                connection.execute(
                    """
                    INSERT INTO match_team_statistics (
                        match_id, group_name, statistic_name, home_value, away_value,
                        home_display_value, away_display_value
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.get("id"),
                        item.get("groupName"),
                        item.get("name"),
                        str(item.get("home")) if item.get("home") is not None else None,
                        str(item.get("away")) if item.get("away") is not None else None,
                        item.get("homeValue"),
                        item.get("awayValue"),
                    ),
                )

            for order, incident in enumerate(event.get("incidents", []), start=1):
                player = incident.get("player", {})
                assist1 = incident.get("assist1", {})
                assist2 = incident.get("assist2", {})
                connection.execute(
                    """
                    INSERT INTO match_incidents (
                        match_id, incident_order, incident_type, time, added_time, home_score, away_score,
                        is_live, team_side, player_id, player_name, assist_1_id, assist_1_name,
                        assist_2_id, assist_2_name, text, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.get("id"),
                        order,
                        incident.get("incidentType"),
                        incident.get("time"),
                        incident.get("addedTime"),
                        incident.get("homeScore"),
                        incident.get("awayScore"),
                        1 if incident.get("isLive") else 0,
                        incident.get("teamSide"),
                        player.get("id"),
                        player.get("name"),
                        assist1.get("id"),
                        assist1.get("name"),
                        assist2.get("id"),
                        assist2.get("name"),
                        incident.get("text"),
                        json.dumps(incident, ensure_ascii=False),
                    ),
                )

            lineups = event.get("lineups", {})
            for team_side in ("home", "away"):
                lineup_side = lineups.get(team_side, {})
                for squad_role in ("starters", "substitutes"):
                    for player_entry in lineup_side.get(squad_role, []):
                        player = player_entry.get("player", {})
                        statistics = player_entry.get("statistics", {})
                        connection.execute(
                            """
                            INSERT INTO player_appearances (
                                match_id, player_id, team_side, squad_role, team_id, player_name, player_slug,
                                player_short_name, player_position, jersey_number, shirt_number, height,
                                date_of_birth_timestamp, country_json, market_value_json, statistics_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                event.get("id"),
                                player.get("id"),
                                team_side,
                                squad_role,
                                home_team.get("id") if team_side == "home" else away_team.get("id"),
                                player.get("name"),
                                player.get("slug"),
                                player.get("shortName"),
                                player.get("position"),
                                player_entry.get("jerseyNumber"),
                                player_entry.get("shirtNumber"),
                                player.get("height"),
                                player.get("dateOfBirthTimestamp"),
                                json.dumps(player.get("country"), ensure_ascii=False),
                                json.dumps(player.get("proposedMarketValueRaw"), ensure_ascii=False),
                                json.dumps(statistics, ensure_ascii=False),
                            ),
                        )

                        for stat_name, stat_value in statistics.items():
                            connection.execute(
                                """
                                INSERT INTO player_match_statistics (
                                    match_id, player_id, team_side, stat_name, stat_value
                                ) VALUES (?, ?, ?, ?, ?)
                                """,
                                (
                                    event.get("id"),
                                    player.get("id"),
                                    team_side,
                                    stat_name,
                                    json.dumps(stat_value, ensure_ascii=False)
                                    if isinstance(stat_value, (dict, list))
                                    else str(stat_value),
                                ),
                            )

        connection.commit()
    finally:
        connection.close()


async def main() -> None:
    args = parse_args()
    include_team_stats = not (args.without_stats or args.without_team_stats)
    include_player_stats = not (args.without_stats or args.without_player_stats)
    include_incidents = not args.without_incidents

    payload = await build_payload(
        include_team_stats=include_team_stats,
        include_player_stats=include_player_stats,
        include_incidents=include_incidents,
        limit=args.limit,
    )
    output_path = Path(args.output)
    write_output(output_path, payload)
    if args.sqlite_output:
        sqlite_path = Path(args.sqlite_output)
        write_sqlite(sqlite_path, payload)
        print(f"SQLite ecrit dans {sqlite_path}")
    print(f"JSON ecrit dans {output_path}")
    print(f"Saison: {payload['season'].get('year')} | Matchs termines: {len(payload['events'])}")


if __name__ == "__main__":
    asyncio.run(main())
