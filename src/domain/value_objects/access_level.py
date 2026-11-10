"""Classification access levels for documents."""

from enum import IntEnum


class AccessLevel(IntEnum):
    """Hierarchical document security classification levels."""

    PUBLIC = 10
    INTERNAL = 20
    CONFIDENTIAL = 30
    RESTRICTED = 40

    @classmethod
    def from_str(cls, value: str) -> "AccessLevel":
        normalized = value.strip().upper()
        mapping = {
            "PUBLIC": cls.PUBLIC,
            "INTERNAL": cls.INTERNAL,
            "CONFIDENTIAL": cls.CONFIDENTIAL,
            "RESTRICTED": cls.RESTRICTED,
        }
        if normalized not in mapping:
            raise ValueError(f"Invalid access level: {value}. Allowed: {list(mapping.keys())}")
        return mapping[normalized]

    @property
    def label(self) -> str:
        return self.name
