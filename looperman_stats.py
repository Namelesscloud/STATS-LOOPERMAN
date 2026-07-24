import argparse
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_URL = "https://www.looperman.com/users/profile/4055719"
DEFAULT_OUTPUT_FILE = "stats.json"
DEFAULT_REFRESH_SECONDS = 1800


def parse_args():
    parser = argparse.ArgumentParser(
        description="Collecte les statistiques Looperman et écrit un fichier JSON localement."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="URL du profil Looperman à scraper"
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_FILE,
        help="Nom du fichier JSON de sortie"
    )
    parser.add_argument(
        "--refresh-seconds",
        type=int,
        default=DEFAULT_REFRESH_SECONDS,
        help="Intervalle de rafraîchissement en secondes"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Récupère les statistiques une fois puis quitte"
    )
    return parser.parse_args()


def clean_number(value):
    try:
        return int(
            value
            .replace(",", "")
            .replace(" ", "")
            .strip()
        )
    except ValueError:
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


def read_previous_stats(output_file):
    if not output_file.exists():
        return None

    try:
        with open(output_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def get_delta(new_value, old_value):
    if old_value is None:
        return 0
    return new_value - old_value


def compute_hash(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


MAX_HISTORY_ENTRIES = 50


def get_looperman_stats(url, output_file, refresh_seconds):
    previous_data = read_previous_stats(output_file)
    history = previous_data.get("history", []) if previous_data else []
    previous_hash = previous_data.get("content_hash") if previous_data else None

    now = datetime.now()

    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()

    content_hash = compute_hash(response.text)
    hash_changed = previous_hash is not None and content_hash != previous_hash

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

    previous_loop_stats = previous_data.get("loop_stats", {}) if previous_data else {}
    old_uploads = previous_loop_stats.get("uploads")
    old_downloads = previous_loop_stats.get("downloads")
    old_favourites = previous_loop_stats.get("favourites_in")
    old_comments = previous_loop_stats.get("comments_in")

    delta = {
        "uploads": get_delta(uploads, old_uploads),
        "downloads": get_delta(downloads, old_downloads),
        "favourites_in": get_delta(favourites, old_favourites),
        "comments_in": get_delta(comments, old_comments),
    }

    snapshot = {
        "source": url,
        "output": str(output_file),
        "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at_display": now.strftime("%d/%m/%Y à %H:%M:%S"),
        "content_hash": content_hash,
        "hash_changed": hash_changed,
        "loop_stats": {
            "uploads": uploads,
            "downloads": downloads,
            "favourites_in": favourites,
            "comments_in": comments,
        },
        "delta": delta,
    }

    history.append(snapshot)
    history = history[-MAX_HISTORY_ENTRIES:]

    return {
        "source": url,
        "output": str(output_file),
        "updated_at": snapshot["updated_at"],
        "updated_at_display": snapshot["updated_at_display"],
        "refresh_seconds": refresh_seconds,
        "content_hash": content_hash,
        "hash_changed": hash_changed,
        "loop_stats": snapshot["loop_stats"],
        "uploads": uploads,
        "downloads": downloads,
        "favourites_in": favourites,
        "comments_in": comments,
        "delta": delta,
        "history": history,
    }


def save_stats(data, output_file):
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print("--------------------------------")
    print("Stats mises à jour :", data["updated_at_display"])
    print("Fichier écrit ici :", output_file)
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
    args = parse_args()
    output_file = BASE_DIR / args.output

    print("Looperman Live Dashboard lancé.")
    print("URL :", args.url)
    print("Actualisation toutes les", args.refresh_seconds, "secondes")
    print("Fichier de sortie :", output_file)
    print("Dossier :", BASE_DIR)

    if args.once:
        data = get_looperman_stats(args.url, output_file, args.refresh_seconds)
        save_stats(data, output_file)
        return

    while True:
        try:
            data = get_looperman_stats(args.url, output_file, args.refresh_seconds)
            save_stats(data, output_file)
        except Exception as e:
            print("--------------------------------")
            print("Erreur pendant la récupération :", e)
        time.sleep(args.refresh_seconds)


if __name__ == "__main__":
    main()
