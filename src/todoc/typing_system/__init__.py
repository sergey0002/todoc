"""Type descriptors and profile resolution (declarative JSON only)."""

from todoc.typing_system.descriptors import TypeRegistry
from todoc.typing_system.resolver import RESERVED_DIR_TYPES, glob_match, resolve_type

__all__ = ["TypeRegistry", "RESERVED_DIR_TYPES", "glob_match", "resolve_type"]
