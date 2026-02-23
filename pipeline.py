#!/usr/bin/env python3
from __future__ import annotations

import datetime
from pathlib import Path
import yaml


def load_config(path: str = "config.yaml") -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"!!! config.yaml not found, using empty config")
        return {}
    except yaml.YAMLError as exc:
        print(f"!!! error parsing config.yaml: {exc}")
        return {}


def main() -> None:
    print(">>> pipeline.py started (stage: config only)")
    out_dir = Path("out")
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = load_config()
    print(f">>> config loaded, sections: {list(cfg.keys())}")

    status_file = out_dir / "status.txt"
    now = datetime.datetime.utcnow().isoformat()
    status_file.write_text(f"Last run: {now}Z\n", encoding="utf-8")

    print(f">>> wrote {status_file}")
    print(">>> pipeline.py finished")


if __name__ == "__main__":
    main()


