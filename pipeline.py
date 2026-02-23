#!/usr/bin/env python3

from __future__ import annotations

import datetime
from pathlib import Path


def main() -> None:
    print(">>> pipeline.py started (minimal)")
    out_dir = Path("out")
    out_dir.mkdir(parents=True, exist_ok=True)

    status_file = out_dir / "status.txt"
    now = datetime.datetime.utcnow().isoformat()
    status_file.write_text(f"Last run: {now}Z\n", encoding="utf-8")

    print(f">>> wrote {status_file}")
    print(">>> pipeline.py finished")


if __name__ == "__main__":
    main()

