import requests
from bs4 import BeautifulSoup
import json
import shutil
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

URL         = "https://www.looperman.com/users/profile/4055719"
OUTPUT_FILE = BASE_DIR / "stats.json"
BACKUP_DIR  = BASE_DIR / "backups"


def clean_number(value: str) -> int:
    try:
        return int(value.replace(",", "").replace(" ", "").strip())
    except Exception:
        return 0


def extract_section(lines, section_name):
    if section_name not in lines:
        return {}
    start = lines.index(section_name)
    end   = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].endswith("Stats") and lines[i] != section_name:
            end = i
            break
    stats = {}
    section_lines = lines[start + 1 : end]
    for i in range(len(section_lines) - 1):
        value = section_lines[i]
        label = section_lines[i + 1]
        candidate = value.replace(",", "").replace(" ", "")
        if candidate.isdigit():
            key = label.lower().replace(" ", "_").replace("-", "_").replace("/", "_")
            stats[key] = clean_number(value)
    return stats


def read_previous_stats():
    if not OUTPUT_FILE.exists():
        return None
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def get_delta(new_value, old_value):
    return 0 if old_value is None else new_value - old_value


def save_backup(data):
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"stats_{timestamp}.json"
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    backups = sorted(BACKUP_DIR.glob("stats_*.json"), reverse=True)
    for old in backups[30:]:
        old.unlink()
        print(f"Ancienne sauvegarde supprimee : {old.name}")
    print(f"Backup cree : {backup_file.name}")


def update_history(data, previous_data):
    history = []
    if previous_data and "history" in previous_data:
        history = previous_data["history"]
    entry = {
        "time":          datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "uploads":       data["loop_stats"]["uploads"],
        "downloads":     data["loop_stats"]["downloads"],
        "favourites_in": data["loop_stats"]["favourites_in"],
        "comments_in":   data["loop_stats"]["comments_in"],
        "delta": {
            "uploads":       data["delta"]["uploads"],
            "downloads":     data["delta"]["downloads"],
            "favourites_in": data["delta"]["favourites_in"],
            "comments_in":   data["delta"]["comments_in"],
        }
    }
    history.append(entry)
    if len(history) > 100:
        history = history[-100:]
    data["history"] = history


def get_looperman_stats():
    previous_data = read_previous_stats()
    response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    soup  = BeautifulSoup(response.text, "html.parser")
    lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]
    loop_stats = extract_section(lines, "Loop Stats")
    uploads    = loop_stats.get("uploads",       0)
    downloads  = loop_stats.get("downloads",     0)
    favourites = loop_stats.get("favourites_in", 0)
    comments   = loop_stats.get("comments_in",   0)
    prev_loop  = (previous_data or {}).get("loop_stats", {})
    data = {
        "source":             URL,
        "updated_at":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at_display": datetime.now().strftime("%d/%m/%Y a %H:%M:%S"),
        "refresh_hours":      12,
        "loop_stats": {
            "uploads":       uploads,
            "downloads":     downloads,
            "favourites_in": favourites,
            "comments_in":   comments,
        },
        "delta": {
            "uploads":       get_delta(uploads,    prev_loop.get("uploads")),
            "downloads":     get_delta(downloads,  prev_loop.get("downloads")),
            "favourites_in": get_delta(favourites, prev_loop.get("favourites_in")),
            "comments_in":   get_delta(comments,   prev_loop.get("comments_in")),
        },
    }
    update_history(data, previous_data)
    return data


def save_stats(data):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print("-" * 40)
    print("Stats mises a jour :", data["updated_at_display"])
    print("Uploads       :", data["loop_stats"]["uploads"])
    print("Downloads     :", data["loop_stats"]["downloads"])
    print("Favourites In :", data["loop_stats"]["favourites_in"])
    print("Comments In   :", data["loop_stats"]["comments_in"])
    delta = data["delta"]
    if any(v != 0 for v in delta.values()):
        print("Changements   :", delta)
    else:
        print("Aucun changement detecte")
    save_backup(data)


def main():
    print("Looperman Stats - run unique (GitHub Actions)")
    print("URL :", URL)
    data = get_looperman_stats()
    save_stats(data)


if __name__ == "__main__":
    main()
