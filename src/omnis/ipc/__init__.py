"""
Omnis IPC - Inter-Process Communication.

Provides secure communication between UI (user context)
and Engine (root context) processes via Unix sockets.
"""

from omnis.ipc.client import (
    IPCClient,
    create_ui_client,
)
from omnis.ipc.dispatcher import (
    IPCDispatcher,
    create_default_dispatcher,
)
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
from omnis.ipc.server import (
    IPCServer,
    create_engine_server,
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
    # Dispatcher
    "IPCDispatcher",
    "create_default_dispatcher",
    # Server
    "IPCServer",
    "create_engine_server",
    # Client
    "IPCClient",
    "create_ui_client",
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
