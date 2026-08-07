import csv
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template

from notifier import DEFAULT_COUNTRY_CODE, load_dotenv, superduperscraper

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_FILE = DATA_DIR / "history.csv"


def build_models(include_new_models: bool = False):
    refurb_models = [
        ("64", "903905", False),
        ("256", "903906", False),
        ("512", "903907", False),
        ("512", "1202542", True),
        ("1024", "1202547", True),
    ]

    new_models = [
        ("512", "946113", True),
        ("1024", "946114", True),
        ("256", "595604", False),
    ]

    models = refurb_models + (new_models if include_new_models else [])
    return [
        type("SteamDeckModel", (), {"version": version, "package_id": package_id, "is_oled": is_oled, "is_new": False})()
        for version, package_id, is_oled in models
    ]


def _get_country_code() -> str:
    return os.getenv("COUNTRY_CODE", DEFAULT_COUNTRY_CODE)


def _get_csv_dir() -> str:
    return os.getenv("CSV_DIR", str(BASE_DIR / "csv-logs"))


def _availability_path(package_id: str, country_code: str) -> Path:
    return BASE_DIR / f"{package_id}_{country_code}.txt"


def _read_availability(package_id: str, country_code: str) -> str:
    path = _availability_path(package_id, country_code)
    if path.exists():
        return path.read_text(encoding="utf-8").strip() or "unknown"
    return "unknown"


def append_history_record(record: dict, history_file: Path | None = None) -> None:
    history_file = history_file or HISTORY_FILE
    history_file.parent.mkdir(parents=True, exist_ok=True)
    write_header = not history_file.exists() or history_file.stat().st_size == 0
    with history_file.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "package_id", "version", "display_type", "available"])
        if write_header:
            writer.writeheader()
        writer.writerow(record)


def read_history_rows(history_file: Path | None = None):
    history_file = history_file or HISTORY_FILE
    if not history_file.exists():
        return []

    with history_file.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def run_status_check(country_code: str | None = None):
    load_dotenv()
    country_code = country_code or _get_country_code()
    csv_dir = _get_csv_dir()
    os.makedirs(csv_dir, exist_ok=True)

    smtp_config = {
        "host": "",
        "port": 587,
        "user": "",
        "password": "",
        "from": "",
        "to": "",
        "use_tls": True,
    }

    results = []
    for model in build_models(include_new_models=False):
        superduperscraper(model, csv_dir, country_code, smtp_config, role_ids=None)
        availability = _read_availability(model.package_id, country_code)
        display_type = "OLED" if model.is_oled else "LCD"
        results.append(
            {
                "version": model.version,
                "package_id": model.package_id,
                "display_type": display_type,
                "available": availability,
                "checked_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            }
        )

        append_history_record(
            {
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "package_id": model.package_id,
                "version": model.version,
                "display_type": display_type,
                "available": availability,
            }
        )

    return {
        "country_code": country_code,
        "checked_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "results": results,
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/api/refresh")
def api_refresh():
    return jsonify(run_status_check())


@app.get("/api/history")
def api_history():
    return jsonify(read_history_rows())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
