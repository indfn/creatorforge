"""Shared fixtures for JSON Schema validation tests.

Provides:
    schema_dir       — Path to the schemas/ directory
    all_schemas      — dict mapping filename → loaded JSON schema dict
    validator_for    — function that returns a jsonschema validator for a given schema filename
"""

import json
from pathlib import Path

import pytest

# Root of the project (two levels up from tests/test_schemas/)
SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


@pytest.fixture(scope="session")
def schema_dir() -> Path:
    """Path to the schemas/ directory."""
    return SCHEMA_DIR


@pytest.fixture(scope="session")
def all_schemas(schema_dir: Path) -> dict[str, dict]:
    """Load all 17 JSON Schema files into {filename: schema_dict}."""
    schemas = {}
    for fpath in sorted(schema_dir.glob("*.schema.json")):
        with open(fpath) as f:
            schemas[fpath.name] = json.load(f)
    assert len(schemas) == 17, f"Expected 17 schemas, got {len(schemas)}"
    return schemas


@pytest.fixture(scope="function")
def validator_for(all_schemas: dict[str, dict]):
    """Return a function that validates data against a named schema.

    Usage:
        validator = validator_for("quota-budget.schema.json")
        validator({"budgets": ...})  # raises ValidationError on failure
    """
    from jsonschema import validate

    def _validate(schema_name: str, data: dict) -> None:
        schema = all_schemas.get(schema_name)
        if schema is None:
            raise ValueError(f"Unknown schema: {schema_name}")
        validate(instance=data, schema=schema)

    return _validate
