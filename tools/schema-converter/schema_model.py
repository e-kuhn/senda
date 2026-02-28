"""Internal and export type models for AUTOSAR XSD schema."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto


# --- Export Model (consumer-facing, used by generators) ---


class PrimitiveSupertype(Enum):
    STRING = auto()
    INTEGER = auto()
    FLOAT = auto()
    BOOLEAN = auto()
    INTEGER_ENUM_UNION = auto()


@dataclass
class ExportMember:
    name: str | None
    types: list[str]
    is_reference: bool = False
    is_ordered: bool = False
    min_occurs: int | None = None  # None = optional (0)
    max_occurs: int | None = None  # None = unbounded
    is_identity: bool = False
    doc: str | None = None
    instance_ref_role: str | None = None  # "context", "target", or None
    xml_element_name: str | None = None
    inner_ref_tag: str | None = None  # Pattern B: inner REF element XML tag name


@dataclass
class ExportPrimitive:
    name: str
    supertype: PrimitiveSupertype = PrimitiveSupertype.STRING
    pattern: str | None = None
    values: list[str] = field(default_factory=list)
    doc: str | None = None
    xml_name: str | None = None


@dataclass
class ExportEnum:
    name: str
    values: list[str]
    is_subtypes_enum: bool = False
    doc: str | None = None
    value_docs: list[str | None] = field(default_factory=list)
    xml_name: str | None = None


@dataclass
class ExportComposite:
    name: str
    members: list[ExportMember] = field(default_factory=list)
    identifiers: list[str] = field(default_factory=list)
    is_ordered: bool = False
    has_unnamed_string_member: bool = False
    is_abstract: bool = False
    inherits_from: list[str] = field(default_factory=list)
    doc: str | None = None
    is_instance_ref: bool = False
    xml_name: str | None = None


@dataclass
class ExportSchema:
    release_version: str = "R00-00"
    autosar_version: str = "0.0.0"
    xsd_filename: str = ""
    primitives: list[ExportPrimitive] = field(default_factory=list)
    enums: list[ExportEnum] = field(default_factory=list)
    composites: list[ExportComposite] = field(default_factory=list)
    root_type: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# --- Internal Model (used during parsing, mirrors XSD structure) ---


@dataclass
class InternalMember:
    name: str | None
    doc: str | None = None
    xml_element_name: str | None = None  # Original XML element name for role detection
    xml_types: list[str] = field(default_factory=list)
    type_names: list[str] = field(default_factory=list)
    xml_sub_types: str | None = None
    is_ordered: bool = False
    is_reference: bool = False
    inner_ref_tag: str | None = None
    stereotypes: list[str] = field(default_factory=list)
    min_occurs: int | None = None
    max_occurs: int | None = None


@dataclass
class InternalType:
    name: str
    xml_name: str
    namespace: str
    doc: str | None = None
    is_abstract: bool = False
    stereotypes: list[str] = field(default_factory=list)


@dataclass
class InternalComplexType(InternalType):
    members: list[InternalMember] = field(default_factory=list)
    inherits_from: list[str] = field(default_factory=list)


@dataclass
class InternalPrimitiveType(InternalType):
    pass


@dataclass
class InternalAlias(InternalType):
    target: str | None = None
    pattern: str | None = None


@dataclass
class InternalEnumeration(InternalType):
    values: list[str] = field(default_factory=list)
    value_docs: list[str | None] = field(default_factory=list)


@dataclass
class InternalSubTypesEnum(InternalType):
    types: list[str] = field(default_factory=list)


@dataclass
class InternalSchema:
    autosar_version: str = "0.0.0"
    release_version: str = "R00-00"
    xsd_filename: str = ""
    types: dict[str, InternalType] = field(default_factory=dict)
    sub_types: dict[str, InternalSubTypesEnum] = field(default_factory=dict)
    root: InternalMember | None = None
