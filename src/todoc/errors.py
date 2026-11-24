"""Stable exit codes and operation errors.

Exit code map (part of the CLI contract, constitution §8.2):
  0  success
  1  operation error (generic)
  2  usage error
  3  validation error
  4  access denied
  5  conflict (expected_hash mismatch / overwrite)
  6  incomplete generation
"""

from __future__ import annotations

EXIT_SUCCESS = 0
EXIT_OPERATION = 1
EXIT_USAGE = 2
EXIT_VALIDATION = 3
EXIT_ACCESS = 4
EXIT_CONFLICT = 5
EXIT_INCOMPLETE = 6


class TodocError(Exception):
    """Operation error with a stable exit code and machine-readable code."""

    def __init__(self, message: str, exit_code: int = EXIT_OPERATION, code: str = "operation.error") -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code
        self.code = code


class ValidationError(TodocError):
    def __init__(self, message: str, code: str = "validation.error") -> None:
        super().__init__(message, EXIT_VALIDATION, code)


class AccessError(TodocError):
    def __init__(self, message: str, code: str = "access.denied") -> None:
        super().__init__(message, EXIT_ACCESS, code)


class ConflictError(TodocError):
    def __init__(self, message: str, code: str = "conflict") -> None:
        super().__init__(message, EXIT_CONFLICT, code)


class IncompleteError(TodocError):
    def __init__(self, message: str, code: str = "generation.incomplete") -> None:
        super().__init__(message, EXIT_INCOMPLETE, code)
