from flask import Flask, jsonify, send_from_directory
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
import requests
import json
import time

BASE_DIR = Path(__file__).resolve().parent
URL = "https://www.looperman.com/users/profile/4055719"
STATS_FILE = BASE_DIR / "stats.json"
HISTORY_FILE = BASE_DIR / "history.json"
CACHE_SECONDS = 120      # scrape max toutes les 2 minutes
HISTORY_MAX_POINTS = 60  # nombre de points gardés pour le graphique

app = Flask(__name__)
cache = {"data": None, "time": 0}


# ---------- Utilitaires ----------

def clean_number(value):
    try:
        return int(value.replace(",", "").replace(" ", "").strip())
    except Exception:
        return 0


def extract_section(lines, section_name):
    if section_name not in lines:
        return {}
    start = lines.index(section_name)
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].endswith("Stats") and lines[i] != section_name:
            end = i
            break
    section_lines = lines[start + 1:end]
    stats = {}
    for i in range(len(section_lines) - 1):
        value, label = section_lines[i], section_lines[i + 1]
        if value.replace(",", "").replace(" ", "").isdigit():
            key = label.lower().replace(" ", "_").replace("-", "_").replace("/", "_")
            stats[key] = clean_number(value)
    return stats


def read_json(path, default):
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ---------- Historique ----------

def update_history(current_stats):
    history = read_json(HISTORY_FILE, [])

    point = {
        "time": datetime.now().strftime("%H:%M"),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "downloads": current_stats["downloads"],
        "favourites_in": current_stats["favourites_in"],
        "comments_in": current_stats["comments_in"],
        "uploads": current_stats["uploads"],
    }

    # On n'ajoute pas de doublon si rien n'a bougé
    if history and history[-1]["downloads"] == point["downloads"] \
            and history[-1]["favourites_in"] == point["favourites_in"] \
            and history[-1]["comments_in"] == point["comments_in"] \
            and history[-1]["uploads"] == point["uploads"]:
        return history

    history.append(point)
    history = history[-HISTORY_MAX_POINTS:]
    write_json(HISTORY_FILE, history)
    return history


# ---------- Scraping ----------

def scrape():
    previous = read_json(STATS_FILE, None)
    old = previous.get("loop_stats", {}) if previous else {}

    response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]
    loop_stats = extract_section(lines, "Loop Stats")

    current = {
        "uploads": loop_stats.get("uploads", 0),
        "downloads": loop_stats.get("downloads", 0),
        "favourites_in": loop_stats.get("favourites_in", 0),
        "comments_in": loop_stats.get("comments_in", 0),
    }

    history = update_history(current)

    data = {
        "source": URL,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at_display": datetime.now().strftime("%d/%m/%Y à %H:%M:%S"),
        "refresh_seconds": CACHE_SECONDS,
        "loop_stats": current,
        "delta": {k: current[k] - old.get(k, current[k]) for k in current},
        "history": history,
    }

    write_json(STATS_FILE, data)
    print(f"[{data['updated_at_display']}] Scrape OK -> {current}")
    return data


# ---------- Routes ----------

@app.route("/stats")
def stats():
    now = time.time()
    if cache["data"] is None or (now - cache["time"]) > CACHE_SECONDS:
        try:
            cache["data"] = scrape()
            cache["time"] = now
        except Exception as e:
            print("Erreur scraping :", e)
            if cache["data"] is None:
                previous = read_json(STATS_FILE, None)
                if previous:
                    previous["history"] = read_json(HISTORY_FILE, [])
                    cache["data"] = previous
                else:
                    return jsonify({"error": str(e)}), 500
    return jsonify(cache["data"])


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


if __name__ == "__main__":
    print("Dashboard : http://localhost:8000")
    app.run(host="127.0.0.1", port=8000)
