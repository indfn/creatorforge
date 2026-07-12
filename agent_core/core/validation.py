"""
Schema validation gate — validates pipeline artifacts against JSON Schema contracts.
Used as a quality gate at every stage boundary.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import json
import jsonschema


SCHEMAS_DIR = Path(__file__).resolve().parent.parent.parent / "schemas"


@dataclass
class ValidationResult:
    success: bool
    errors: list[str] = field(default_factory=list)
    data: Any = None


def load_schema(schema_name: str) -> dict:
    """Load a JSON Schema file from schemas/ directory."""
    path = SCHEMAS_DIR / schema_name
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_name}")
    with open(path, "r") as f:
        return json.load(f)


def validate_output(data: Any, schema_name: str) -> ValidationResult:
    """
    Validate data against a named JSON Schema.

    Args:
        data: The artifact data to validate
        schema_name: Filename in schemas/ directory (e.g., "checkpoint.schema.json")

    Returns:
        ValidationResult with success flag and any validation errors
    """
    schema = load_schema(schema_name)
    try:
        jsonschema.validate(instance=data, schema=schema)
        return ValidationResult(success=True, data=data)
    except jsonschema.ValidationError as e:
        return ValidationResult(
            success=False,
            errors=[str(e)],
            data=data
        )


def validate_or_raise(data: Any, schema_name: str) -> Any:
    """Validate and return data, or raise ValueError on failure."""
    result = validate_output(data, schema_name)
    if not result.success:
        raise ValueError(f"Schema validation failed for {schema_name}: {'; '.join(result.errors)}")
    return data
