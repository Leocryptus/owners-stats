#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Owners stats builder — вторая команда Лео, летняя лига REST ROFL (дивизион ниже Akatsuki).
Тянет все сыгранные игры Owners из публичного API mtgame.ru,
агрегирует статистику по игрокам (ключ = person id, стабилен между играми),
считает командные цифры, проценты, плюс-минус → data.json для дашборда.

Запуск:  python3 build.py
Новую игру добавлять не нужно вручную — как только матч станет 'closed' в турнире,
он подхватится сам. Близнец ~/brain/akatsuki/build.py (турнир REST EASY).
"""
from __future__ import annotations
import json, sys, os, subprocess, urllib.request, ssl, datetime
from collections import defaultdict

PHOTO_DIR = "assets/players"

API = "https://mtgame.ru/api/v1"
TOURNAMENT_ID = 4025        # REST ROFL (летняя лига, дивизион ниже)
AK_TEAM_ID = 10697          # Owners’
AK_TT_ID = 30796            # tournament_team_id
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def get(path: str):
    url = f"{API}/{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "Mozilla/5.0 akatsuki-stats"})
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        return json.loads(r.read().decode("utf-8"))


def pct(made, att):
    return round(made / att * 100, 1) if att else 0.0


def fetch_photo(uid: int, url: str) -> str | None:
    """Скачать фото игрока в assets/players/<uid>.jpg (квадрат 400), кэш. Вернуть локальный путь или None."""
    if not url:
        return None
    os.makedirs(PHOTO_DIR, exist_ok=True)
    out = f"{PHOTO_DIR}/{uid}.jpg"
    rel = f"{PHOTO_DIR}/{uid}.jpg"
    if os.path.exists(out):
        return rel
    raw = f"{PHOTO_DIR}/_{uid}.raw"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=40, context=CTX).read()
        with open(raw, "wb") as f:
            f.write(data)
        subprocess.run(["sips", "-s", "format", "jpeg", raw, "--out", out], capture_output=True)
        r = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", out], capture_output=True, text=True)
        w = h = 0
        for line in r.stdout.splitlines():
            if "pixelWidth" in line: w = int(line.split(":")[1])
            if "pixelHeight" in line: h = int(line.split(":")[1])
        if w and h:
            subprocess.run(["sips", "-c", str(min(w, h)), str(min(w, h)), out], capture_output=True)
        subprocess.run(["sips", "-Z", "400", out], capture_output=True)
        os.remove(raw)
        return rel
    except Exception:
        if os.path.exists(raw):
            os.remove(raw)
        return None


def main():
    games = get(f"tournament/{TOURNAMENT_ID}/games/")
    ak_games = []
    for g in games:
        ids = {(g.get("team") or {}).get("id"), (g.get("competitor_team") or {}).get("id"),
               g.get("tournament_team_id"), g.get("competitor_tournament_team_id")}
        if AK_TEAM_ID in ids or AK_TT_ID in ids:
            if g.get("status") == "closed":
                ak_games.append(g)

    ak_games.sort(key=lambda x: x.get("datetime") or "")

    players = {}          # user_id -> aggregate
    game_records = []     # per game summary
    team = {
        "games": 0, "wins": 0, "losses": 0,
        "pts_for": 0, "pts_against": 0,
        "two_m": 0, "two_a": 0, "three_m": 0, "three_a": 0, "ft_m": 0, "ft_a": 0,
        "reb": 0, "oreb": 0, "dreb": 0, "ast": 0, "stl": 0, "blk": 0, "tov": 0, "pf": 0,
    }

    for g in ak_games:
        gid = g["id"]
        card = get(f"tournament_basketball_game/{gid}/")
        ustat = {s["game_user_id"]: s for s in get(f"tournament_basketball_game/{gid}/user_statistic/")}
        tstat = get(f"tournament_basketball_game/{gid}/team_statistic/")
        roster = get(f"tournament_game/{gid}/users/")

        ak_is_team = (card.get("team") or {}).get("id") == AK_TEAM_ID
        side = "team" if ak_is_team else "competitor_team"
        opp_side = "competitor_team" if ak_is_team else "team"

        ak_score = card["team_score"] if ak_is_team else card["competitor_team_score"]
        opp_score = card["competitor_team_score"] if ak_is_team else card["team_score"]
        opp_name = (card.get("competitor_team_name")
                    or (card.get("competitor_team") or {}).get("name")) if ak_is_team \
            else (card.get("team") or {}).get("name")

        # quarters (Akatsuki orientation)
        sbp = card.get("score_by_period") or {}
        qi = 0 if ak_is_team else 1
        quarters = []
        for k in sorted(sbp.keys(), key=lambda x: int(x)):
            pair = sbp[k]
            quarters.append([pair[qi], pair[1 - qi]])

        tt = tstat[side]
        win = ak_score > opp_score

        team["games"] += 1
        team["wins"] += int(win)
        team["losses"] += int(not win)
        team["pts_for"] += ak_score
        team["pts_against"] += opp_score
        for a, b in [("two_m", "two_points_made"), ("two_a", "two_point_attempts"),
                     ("three_m", "three_points_made"), ("three_a", "three_point_attempts"),
                     ("ft_m", "free_throws_made"), ("ft_a", "free_throw_attempts"),
                     ("reb", "rebounds"), ("oreb", "offensive_rebounds"), ("dreb", "defensive_rebounds"),
                     ("ast", "assists"), ("stl", "steals"), ("blk", "blocks"),
                     ("tov", "turnovers"), ("pf", "personal_fouls")]:
            team[a] += int(tt.get(b) or 0)

        # players
        game_players = []
        for u in roster:
            tu = u.get("team_user") or {}
            if tu.get("team_id") != AK_TEAM_ID:
                continue
            uid = ((tu.get("user") or {}).get("id"))
            person = tu.get("user") or {}
            ln = person.get("last_name") or ""
            fn = person.get("first_name") or ""
            num = u.get("number")
            st = ustat.get(u["id"], {})
            row = {
                "num": num, "name": f"{ln} {fn}".strip(),
                "pts": st.get("points", 0) or 0,
                "two_m": st.get("two_points_made", 0) or 0, "two_a": st.get("two_point_attempts", 0) or 0,
                "three_m": st.get("three_points_made", 0) or 0, "three_a": st.get("three_point_attempts", 0) or 0,
                "ft_m": st.get("free_throws_made", 0) or 0, "ft_a": st.get("free_throw_attempts", 0) or 0,
                "reb": st.get("rebounds", 0) or 0, "oreb": st.get("offensive_rebounds", 0) or 0,
                "dreb": st.get("defensive_rebounds", 0) or 0,
                "ast": st.get("assists", 0) or 0, "stl": st.get("steals", 0) or 0,
                "blk": st.get("blocks", 0) or 0, "tov": st.get("turnovers", 0) or 0,
                "pf": st.get("personal_fouls", 0) or 0,
                "pm": st.get("plus_minus", 0) or 0,
                "eff": st.get("player_efficiency", 0) or 0,
            }
            game_players.append(row)

            # aggregate
            p = players.setdefault(uid, {
                "name": row["name"], "num": num, "gp": 0,
                "pts": 0, "two_m": 0, "two_a": 0, "three_m": 0, "three_a": 0, "ft_m": 0, "ft_a": 0,
                "reb": 0, "oreb": 0, "dreb": 0, "ast": 0, "stl": 0, "blk": 0, "tov": 0, "pf": 0,
                "pm": 0, "log": [], "photo_url": (person.get("photo") or {}).get("path"),
            })
            if not p.get("photo_url"):
                p["photo_url"] = (person.get("photo") or {}).get("path")
            p["name"] = row["name"] or p["name"]
            if num is not None:
                p["num"] = num
            p["gp"] += 1
            for kk in ["pts", "two_m", "two_a", "three_m", "three_a", "ft_m", "ft_a",
                       "reb", "oreb", "dreb", "ast", "stl", "blk", "tov", "pf", "pm"]:
                p[kk] += row[kk]
            p["log"].append({
                "gid": gid, "date": (card.get("datetime") or "")[:10], "opp": opp_name,
                "win": win, "pts": row["pts"], "reb": row["reb"], "ast": row["ast"],
                "stl": row["stl"], "blk": row["blk"], "pm": row["pm"],
                "two_m": row["two_m"], "two_a": row["two_a"],
                "three_m": row["three_m"], "three_a": row["three_a"],
                "ft_m": row["ft_m"], "ft_a": row["ft_a"], "tov": row["tov"], "pf": row["pf"],
            })

        game_players.sort(key=lambda r: -r["pts"])
        game_records.append({
            "gid": gid, "date": (card.get("datetime") or "")[:10], "opp": opp_name,
            "ak_score": ak_score, "opp_score": opp_score, "win": win,
            "diff": ak_score - opp_score, "quarters": quarters,
            "team": {
                "pts": ak_score,
                "two_m": int(tt.get("two_points_made") or 0), "two_a": int(tt.get("two_point_attempts") or 0),
                "three_m": int(tt.get("three_points_made") or 0), "three_a": int(tt.get("three_point_attempts") or 0),
                "ft_m": int(tt.get("free_throws_made") or 0), "ft_a": int(tt.get("free_throw_attempts") or 0),
                "reb": int(tt.get("rebounds") or 0), "oreb": int(tt.get("offensive_rebounds") or 0),
                "dreb": int(tt.get("defensive_rebounds") or 0),
                "ast": int(tt.get("assists") or 0), "stl": int(tt.get("steals") or 0),
                "blk": int(tt.get("blocks") or 0), "tov": int(tt.get("turnovers") or 0),
                "pf": int(tt.get("personal_fouls") or 0),
            },
            "players": game_players,
        })

    # finalize player aggregates
    plist = []
    for uid, p in players.items():
        gp = p["gp"]
        plist.append({
            "id": uid, "name": p["name"], "num": p["num"], "gp": gp,
            "photo": fetch_photo(uid, p.get("photo_url")),
            "pts": p["pts"], "reb": p["reb"], "oreb": p["oreb"], "dreb": p["dreb"],
            "ast": p["ast"], "stl": p["stl"], "blk": p["blk"], "tov": p["tov"], "pf": p["pf"],
            "pm": p["pm"],
            "ppg": round(p["pts"] / gp, 1) if gp else 0,
            "rpg": round(p["reb"] / gp, 1) if gp else 0,
            "apg": round(p["ast"] / gp, 1) if gp else 0,
            "spg": round(p["stl"] / gp, 1) if gp else 0,
            "bpg": round(p["blk"] / gp, 1) if gp else 0,
            "two_m": p["two_m"], "two_a": p["two_a"], "two_pct": pct(p["two_m"], p["two_a"]),
            "three_m": p["three_m"], "three_a": p["three_a"], "three_pct": pct(p["three_m"], p["three_a"]),
            "ft_m": p["ft_m"], "ft_a": p["ft_a"], "ft_pct": pct(p["ft_m"], p["ft_a"]),
            "log": sorted(p["log"], key=lambda x: x["date"]),
        })
    plist.sort(key=lambda x: -x["ppg"])

    # upcoming games
    upcoming = []
    for g in games:
        ids = {(g.get("team") or {}).get("id"), (g.get("competitor_team") or {}).get("id"),
               g.get("tournament_team_id"), g.get("competitor_tournament_team_id")}
        if (AK_TEAM_ID in ids or AK_TT_ID in ids) and g.get("status") != "closed":
            ak_is_team = (g.get("team") or {}).get("id") == AK_TEAM_ID
            opp = (g.get("competitor_team_name") or (g.get("competitor_team") or {}).get("name")) if ak_is_team \
                else (g.get("team") or {}).get("name")
            upcoming.append({"gid": g["id"], "date": (g.get("datetime") or "")[:10], "opp": opp})

    team_out = {
        **team,
        "two_pct": pct(team["two_m"], team["two_a"]),
        "three_pct": pct(team["three_m"], team["three_a"]),
        "ft_pct": pct(team["ft_m"], team["ft_a"]),
        "ppg": round(team["pts_for"] / team["games"], 1) if team["games"] else 0,
        "papg": round(team["pts_against"] / team["games"], 1) if team["games"] else 0,
        "diff": team["pts_for"] - team["pts_against"],
    }

    data = {
        "team_name": "OWNERS",
        "tournament": "REST ROFL",
        "generated": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
        "team": team_out,
        "players": plist,
        "games": game_records,
        "upcoming": upcoming,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    with open("data.js", "w", encoding="utf-8") as f:
        f.write("window.AK_DATA=")
        json.dump(data, f, ensure_ascii=False)
        f.write(";")
    print(f"OK: {team['games']} games, {len(plist)} players, {len(upcoming)} upcoming -> data.json + data.js")
    print(f"Record: {team['wins']}-{team['losses']} | PF {team['pts_for']} PA {team['pts_against']}")


if __name__ == "__main__":
    main()
