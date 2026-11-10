"""Department classifications for organizational data isolation."""

from enum import StrEnum


class Department(StrEnum):
    """Departments within ACME Enterprise."""

    GENERAL = "general"
    HR = "hr"
    FINANCE = "finance"
    ENGINEERING = "engineering"
    LEGAL = "legal"
    OPERATIONS = "operations"
    SECURITY = "security"
    IT = "it"
    SUPPORT = "support"

    @classmethod
    def from_str(cls, value: str) -> "Department":
        normalized = value.strip().lower()
        for dept in cls:
            if dept.value == normalized:
                return dept
        return cls.GENERAL
