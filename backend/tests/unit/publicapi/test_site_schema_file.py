"""`tests/schema/public-site-v1.json` is the contract of the site routes; it must match the models."""

from __future__ import annotations

import json
import os
from pathlib import Path

import jsonschema_rs

from tests._support.site_schema import generate

FILE = Path(__file__).resolve().parents[2] / "schema" / "public-site-v1.json"


def test_the_contract_file_matches_the_models() -> None:
    wanted = json.dumps(generate(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        FILE.write_text(wanted)
    assert FILE.read_text() == wanted


def test_every_schema_is_valid_and_refuses_unknown_properties() -> None:
    for name, schema in json.loads(FILE.read_text()).items():
        jsonschema_rs.validator_for(schema)
        if name != "categories":
            assert schema.get("additionalProperties") is False, name
