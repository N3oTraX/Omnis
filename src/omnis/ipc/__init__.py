"""
Omnis IPC - Inter-Process Communication.

Provides secure communication between UI (user context)
and Engine (root context) processes via Unix sockets.
"""

from omnis.ipc.exceptions import (
    IPCConnectionError,
    IPCError,
    IPCErrorCode,
    IPCProtocolError,
    IPCSecurityError,
    IPCTimeoutError,
    IPCValidationError,
)
from omnis.ipc.protocol import (
    PROTOCOL_VERSION,
    Command,
    Event,
    IPCMessage,
    MessageType,
    ResponseStatus,
)
from omnis.ipc.security import (
    ALLOWED_COMMANDS,
    IPCSecurityValidator,
    ValidationResult,
    create_default_validator,
)
from omnis.ipc.transport import DEFAULT_SOCKET_PATH, UnixSocketTransport

__all__ = [
    # Protocol
    "PROTOCOL_VERSION",
    "Command",
    "Event",
    "IPCMessage",
    "MessageType",
    "ResponseStatus",
    # Transport
    "DEFAULT_SOCKET_PATH",
    "UnixSocketTransport",
    # Security
    "ALLOWED_COMMANDS",
    "IPCSecurityValidator",
    "ValidationResult",
    "create_default_validator",
    # Exceptions
    "IPCError",
    "IPCErrorCode",
    "IPCConnectionError",
    "IPCProtocolError",
    "IPCSecurityError",
    "IPCTimeoutError",
    "IPCValidationError",
]
