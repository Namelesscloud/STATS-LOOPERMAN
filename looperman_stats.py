import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

URL = "https://www.looperman.com/users/profile/4055719"
OUTPUT_FILE = BASE_DIR / "stats.json"

# Actualisation du scraping
# 30 = toutes les 30 secondes
# Tu peux mettre 15 si tu veux plus rapide, mais évite trop bas.
REFRESH_SECONDS = 300


def clean_number(value):
    try:
        return int(
            value
            .replace(",", "")
            .replace(" ", "")
            .strip()
        )
    except:
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
        value = section_lines[i]
        label = section_lines[i + 1]

        number_candidate = value.replace(",", "").replace(" ", "")

        if number_candidate.isdigit():
            key = (
                label.lower()
                .replace(" ", "_")
                .replace("-", "_")
                .replace("/", "_")
            )

            stats[key] = clean_number(value)

    return stats


def read_previous_stats():
    if not OUTPUT_FILE.exists():
        return None

    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None


def get_delta(new_value, old_value):
    if old_value is None:
        return 0

    return new_value - old_value


def get_looperman_stats():
    previous_data = read_previous_stats()

    response = requests.get(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    lines = [
        line.strip()
        for line in soup.get_text("\n").split("\n")
        if line.strip()
    ]

    loop_stats = extract_section(lines, "Loop Stats")

    uploads = loop_stats.get("uploads", 0)
    downloads = loop_stats.get("downloads", 0)
    favourites = loop_stats.get("favourites_in", 0)
    comments = loop_stats.get("comments_in", 0)

    previous_loop_stats = {}

    if previous_data:
        previous_loop_stats = previous_data.get("loop_stats", {})

    old_uploads = previous_loop_stats.get("uploads")
    old_downloads = previous_loop_stats.get("downloads")
    old_favourites = previous_loop_stats.get("favourites_in")
    old_comments = previous_loop_stats.get("comments_in")

    data = {
        "source": URL,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at_display": datetime.now().strftime("%d/%m/%Y à %H:%M:%S"),
        "refresh_seconds": REFRESH_SECONDS,
        "loop_stats": {
            "uploads": uploads,
            "downloads": downloads,
            "favourites_in": favourites,
            "comments_in": comments
        },
        "delta": {
            "uploads": get_delta(uploads, old_uploads),
            "downloads": get_delta(downloads, old_downloads),
            "favourites_in": get_delta(favourites, old_favourites),
            "comments_in": get_delta(comments, old_comments)
        }
    }

    return data


def save_stats(data):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print("--------------------------------")
    print("Stats mises à jour :", data["updated_at_display"])
    print("Fichier écrit ici :", OUTPUT_FILE)
    print("Uploads :", data["loop_stats"]["uploads"])
    print("Downloads :", data["loop_stats"]["downloads"])
    print("Favourites In :", data["loop_stats"]["favourites_in"])
    print("Comments In :", data["loop_stats"]["comments_in"])

    delta = data["delta"]

    if any(value != 0 for value in delta.values()):
        print("Changements détectés :", delta)
    else:
        print("Aucun changement détecté")


def main():
    print("Looperman Live Dashboard lancé.")
    print("URL :", URL)
    print("Actualisation toutes les", REFRESH_SECONDS, "secondes")
    print("Dossier :", BASE_DIR)

    while True:
        try:
            data = get_looperman_stats()
            save_stats(data)

        except Exception as e:
            print("--------------------------------")
            print("Erreur pendant la récupération :", e)

        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    main()
