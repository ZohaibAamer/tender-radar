"""Company profiles are data, not code: validated YAML in profiles/.

The JSON Schema in profiles/profile.schema.json is *generated* from this
model (scripts/generate_profile_schema.py), so documentation cannot drift
from validation.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from tender_radar import config


class CompanyProfile(BaseModel):
    """What a bidding company looks like, for matching against tenders."""

    name: str = Field(description="Profile identifier, matches the file name.")
    description: str = Field(default="", description="One line on who this company is.")
    countries: list[str] = Field(
        description="ISO 3166-1 alpha-2 buyer countries the company can serve."
    )
    cpv_divisions: list[str] = Field(
        description="2-digit CPV divisions of interest, e.g. '72' for IT services."
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Case-insensitive terms boosting a tender's relevance.",
    )
    employees: int | None = Field(default=None, ge=1, description="Headcount, for context.")
    min_value: float | None = Field(
        default=None, description="Ignore tenders disclosed below this value."
    )
    max_value: float | None = Field(
        default=None, description="Ignore tenders disclosed above this value."
    )
    currency: str = Field(default="GBP", description="Currency of min/max value bounds.")


def load_profile(name: str, profiles_dir: Path | None = None) -> CompanyProfile:
    directory = profiles_dir or config.PROFILES_DIR
    path = directory / f"{name}.yaml"
    if not path.exists():
        available = sorted(p.stem for p in directory.glob("*.yaml"))
        raise FileNotFoundError(
            f"no profile named '{name}'. Available profiles: {', '.join(available) or 'none'}"
        )
    return CompanyProfile.model_validate(yaml.safe_load(path.read_text()))


def list_profiles(profiles_dir: Path | None = None) -> list[str]:
    directory = profiles_dir or config.PROFILES_DIR
    return sorted(p.stem for p in directory.glob("*.yaml"))
