"""Data model and validation for ER diagram JSON documents.

The public JSON format intentionally uses the field names from the assignment,
while the Python model provides typed objects for the renderer and AI pipeline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


# region: Exceptions and enums
class SchemaError(ValueError):
    """Raised when an ER diagram document does not match the schema."""


class Cardinality(str, Enum):
    """Supported binary relationship cardinalities."""

    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"
    MANY_TO_ONE = "N:1"
    MANY_TO_MANY = "N:M"


class ParticipantCardinality(str, Enum):
    """Supported cardinalities for ternary relationship participants."""

    ONE = "1"
    MANY = "N"
# endregion

# region: Helper functions for schema validation
def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_mapping(value: Any, value_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaError(f"{value_name} must be an object")
    return value


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise SchemaError(f"{field_name} must be an array")
    return value
# endregion

# region: Attribute
@dataclass(frozen=True, slots=True)
class Attribute:
    """An entity attribute, including its ER-specific visual semantics."""

    name: str
    is_primary_key: bool = False
    is_multi_valued: bool = False
    composite: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, index: int = 0) -> Attribute:
        data = _require_mapping(data, f"attributes[{index}]")
        name = _require_non_empty_string(data.get("name"), f"attributes[{index}].name")

        is_primary_key = data.get("isPrimaryKey", False)
        if not isinstance(is_primary_key, bool):
            raise SchemaError(f"attributes[{index}].isPrimaryKey must be a boolean")

        is_multi_valued = data.get("isMultiValued", False)
        if not isinstance(is_multi_valued, bool):
            raise SchemaError(f"attributes[{index}].isMultiValued must be a boolean")

        raw_composite = data.get("composite", [])
        if raw_composite is None:
            raw_composite = []
        composite_values = _require_list(
            raw_composite, f"attributes[{index}].composite"
        )
        composite = tuple(
            _require_non_empty_string(value, f"attributes[{index}].composite[{part_index}]")
            for part_index, value in enumerate(composite_values)
        )
        if len(set(composite)) != len(composite):
            raise SchemaError(f"attributes[{index}].composite must not contain duplicates")
        if name in composite:
            raise SchemaError(
                f"attributes[{index}].composite cannot contain its own name"
            )

        return cls(
            name=name,
            is_primary_key=is_primary_key,
            is_multi_valued=is_multi_valued,
            composite=composite,
        )

    @property
    def is_composite(self) -> bool:
        """Whether this attribute has component attributes."""
        return bool(self.composite)

    def to_dict(self) -> dict[str, Any]:
        """Return the assignment-compatible JSON representation."""
        result: dict[str, Any] = {"name": self.name}
        if self.is_primary_key:
            result["isPrimaryKey"] = True
        if self.is_multi_valued:
            result["isMultiValued"] = True
        if self.composite:
            result["composite"] = list(self.composite)
        return result
# endregion

# region: Entity
@dataclass(frozen=True, slots=True)
class Entity:
    """An ER entity and its attributes."""

    name: str
    attributes: tuple[Attribute, ...] = ()

    def __post_init__(self) -> None:
        names = [attribute.name for attribute in self.attributes]
        if len(set(names)) != len(names):
            raise SchemaError(f"entity {self.name!r} has duplicate attribute names")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, index: int = 0) -> Entity:
        data = _require_mapping(data, f"entities[{index}]")
        name = _require_non_empty_string(data.get("name"), f"entities[{index}].name")
        raw_attributes = _require_list(
            data.get("attributes", []), f"entities[{index}].attributes"
        )
        attributes = tuple(
            Attribute.from_dict(attribute, index=attribute_index)
            for attribute_index, attribute in enumerate(raw_attributes)
        )
        return cls(name=name, attributes=attributes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "attributes": [attribute.to_dict() for attribute in self.attributes],
        }
# endregion

# region: Participant
@dataclass(frozen=True, slots=True)
class Participant:
    """An entity participating in a ternary relationship."""

    entity: str
    cardinality: ParticipantCardinality

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, index: int = 0) -> Participant:
        data = _require_mapping(data, f"participants[{index}]")
        entity = _require_non_empty_string(
            data.get("entity"), f"participants[{index}].entity"
        )
        raw_cardinality = _require_non_empty_string(
            data.get("cardinality"), f"participants[{index}].cardinality"
        ).upper()
        try:
            cardinality = ParticipantCardinality(raw_cardinality)
        except ValueError as error:
            raise SchemaError(
                f"participants[{index}].cardinality must be one of: 1, N"
            ) from error
        return cls(entity=entity, cardinality=cardinality)

    def to_dict(self) -> dict[str, str]:
        return {"entity": self.entity, "cardinality": self.cardinality.value}
# endregion

# region: Relationship
@dataclass(frozen=True, slots=True)
class Relationship:
    """A binary or ternary relationship between entities."""

    name: str
    entity1: str | None = None
    entity2: str | None = None
    cardinality: Cardinality | None = None
    participants: tuple[Participant, ...] = ()
    attributes: tuple[Attribute, ...] = ()
    relationship_type: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, index: int = 0) -> Relationship:
        data = _require_mapping(data, f"relationships[{index}]")
        name = _require_non_empty_string(
            data.get("name"), f"relationships[{index}].name"
        )
        raw_attributes = _require_list(
            data.get("attributes", []), f"relationships[{index}].attributes"
        )
        attributes = tuple(
            Attribute.from_dict(attribute, index=attribute_index)
            for attribute_index, attribute in enumerate(raw_attributes)
        )
        relationship_type = data.get("type")
        if relationship_type is not None:
            relationship_type = _require_non_empty_string(
                relationship_type, f"relationships[{index}].type"
            )

        raw_participants = data.get("participants")
        if raw_participants is not None:
            participants = tuple(
                Participant.from_dict(participant, index=participant_index)
                for participant_index, participant in enumerate(
                    _require_list(raw_participants, f"relationships[{index}].participants")
                )
            )
            if len(participants) < 3:
                raise SchemaError(
                    f"relationships[{index}].participants must contain at least "
                    "three participants"
                )
            return cls(
                name=name,
                participants=participants,
                attributes=attributes,
                relationship_type=relationship_type,
            )

        entity1 = _require_non_empty_string(
            data.get("entity1"), f"relationships[{index}].entity1"
        )
        entity2 = _require_non_empty_string(
            data.get("entity2"), f"relationships[{index}].entity2"
        )
        raw_cardinality = _require_non_empty_string(
            data.get("cardinality"), f"relationships[{index}].cardinality"
        ).upper().replace("M:N", "N:M")
        try:
            cardinality = Cardinality(raw_cardinality)
        except ValueError as error:
            supported = ", ".join(value.value for value in Cardinality)
            raise SchemaError(
                f"relationships[{index}].cardinality must be one of: {supported}"
            ) from error

        return cls(
            name=name,
            entity1=entity1,
            entity2=entity2,
            cardinality=cardinality,
            attributes=attributes,
            relationship_type=relationship_type,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"name": self.name}
        if self.participants:
            result["participants"] = [participant.to_dict() for participant in self.participants]
        else:
            result.update(
                {
                    "entity1": self.entity1,
                    "entity2": self.entity2,
                    "cardinality": self.cardinality.value if self.cardinality else None,
                }
            )
        if self.relationship_type:
            result["type"] = self.relationship_type
        if self.attributes:
            result["attributes"] = [attribute.to_dict() for attribute in self.attributes]
        return result

# endregion

# region: ERDiagram
@dataclass(frozen=True, slots=True)
class ERDiagram:
    """Validated ER diagram document used by the renderer."""

    entities: tuple[Entity, ...] = ()
    relationships: tuple[Relationship, ...] = ()

    def __post_init__(self) -> None:
        entity_names = [entity.name for entity in self.entities]
        if len(set(entity_names)) != len(entity_names):
            raise SchemaError("entities must have unique names")

        known_entities = set(entity_names)
        for relationship in self.relationships:
            related_entities = (
                [participant.entity for participant in relationship.participants]
                if relationship.participants
                else [relationship.entity1, relationship.entity2]
            )
            for entity in related_entities:
                if entity not in known_entities:
                    raise SchemaError(
                        f"relationship {relationship.name!r} references unknown entity "
                        f"{entity!r}"
                    )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ERDiagram:
        data = _require_mapping(data, "diagram")
        raw_entities = _require_list(data.get("entities", []), "entities")
        raw_relationships = _require_list(
            data.get("relationships", []), "relationships"
        )
        return cls(
            entities=tuple(
                Entity.from_dict(entity, index=index)
                for index, entity in enumerate(raw_entities)
            ),
            relationships=tuple(
                Relationship.from_dict(relationship, index=index)
                for index, relationship in enumerate(raw_relationships)
            ),
        )

    @classmethod
    def from_json(cls, text: str) -> ERDiagram:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise SchemaError(f"invalid JSON: {error.msg}") from error
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: str | Path) -> ERDiagram:
        source = Path(path)
        try:
            return cls.from_json(source.read_text(encoding="utf-8"))
        except OSError as error:
            raise SchemaError(f"could not read {source}: {error}") from error

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": [entity.to_dict() for entity in self.entities],
            "relationships": [
                relationship.to_dict() for relationship in self.relationships
            ],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_file(self, path: str | Path, *, indent: int = 2) -> None:
        Path(path).write_text(self.to_json(indent=indent) + "\n", encoding="utf-8")
# endregion

__all__ = [
    "Attribute",
    "Cardinality",
    "ERDiagram",
    "Entity",
    "Participant",
    "Relationship",
    "SchemaError",
]
