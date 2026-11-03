"""Regenerate profiles/profile.schema.json from the CompanyProfile model.

Run after changing tender_radar.profiles.CompanyProfile; CI could diff this
to catch drift, but the point is simpler: the schema is generated, never
hand-edited.
"""

from __future__ import annotations

import json
from pathlib import Path

from tender_radar.profiles import CompanyProfile

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "profiles" / "profile.schema.json"


def main() -> None:
    schema = CompanyProfile.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "Tender Radar company profile"
    OUT.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
