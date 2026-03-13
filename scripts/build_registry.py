#!/usr/bin/env python3
"""
Build registry.json from all skills/*/metadata.json files.
Run from the repository root:
    python3 scripts/build_registry.py
"""

import json
import os
import glob
from datetime import date


def build():
    skills = []
    for meta_path in sorted(glob.glob("skills/*/metadata.json")):
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)

        skill_dir = os.path.dirname(meta_path)
        file_count = sum(
            1
            for _, _, files in os.walk(skill_dir)
            for fname in files
            if fname != "metadata.json" and not fname.startswith(".")
        )

        meta["path"] = skill_dir
        meta["fileCount"] = file_count
        skills.append(meta)

    registry = {
        "version": "1.0.0",
        "lastUpdated": date.today().isoformat(),
        "skillCount": len(skills),
        "skills": skills,
    }

    with open("registry.json", "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

    print(f"[build_registry] Generated registry.json with {len(skills)} skills")
    return registry


if __name__ == "__main__":
    build()
