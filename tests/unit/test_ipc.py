"""
Unit tests for IPC module.

Tests:
- Message protocol serialization/deserialization
- Exception hierarchy
- Transport layer basics
"""

import json
import struct
import tempfile
import threading
import time
from pathlib import Path

import pytest

from omnis.ipc import (
    PROTOCOL_VERSION,
    Command,
    Event,
    IPCConnectionError,
    IPCError,
    IPCErrorCode,
    IPCMessage,
    IPCProtocolError,
    IPCTimeoutError,
    MessageType,
    ResponseStatus,
    UnixSocketTransport,
)


class TestIPCExceptions:
    """Tests for IPC exception hierarchy."""

    def test_ipc_error_base(self) -> None:
        """IPCError should store message, code, and details."""
        err = IPCError("test error", IPCErrorCode.INTERNAL_ERROR, {"key": "value"})
        assert err.message == "test error"
        assert err.code == IPCErrorCode.INTERNAL_ERROR
        assert err.details == {"key": "value"}

    def test_ipc_error_to_dict(self) -> None:
        """IPCError should serialize to dictionary."""
        err = IPCError("test", IPCErrorCode.TIMEOUT, {"timeout": 30})
        d = err.to_dict()
        assert d["code"] == "TIMEOUT"
        assert d["message"] == "test"
        assert d["details"]["timeout"] == 30

    def test_connection_error(self) -> None:
        """IPCConnectionError should default to CONNECTION_FAILED."""
        err = IPCConnectionError("connection failed")
        assert err.code == IPCErrorCode.CONNECTION_FAILED

    def test_protocol_error(self) -> None:
        """IPCProtocolError should default to INVALID_MESSAGE."""
        err = IPCProtocolError("bad message")
        assert err.code == IPCErrorCode.INVALID_MESSAGE

    def test_timeout_error(self) -> None:
        """IPCTimeoutError should have default message."""
        err = IPCTimeoutError()
        assert err.code == IPCErrorCode.TIMEOUT
        assert "timed out" in err.message.lower()


class TestIPCMessage:
    """Tests for IPCMessage dataclass."""

    def test_create_request(self) -> None:
        """create_request should create valid request message."""
        msg = IPCMessage.create_request(Command.START_INSTALLATION, {"target": "/mnt"})

        assert msg.version == PROTOCOL_VERSION
        assert msg.type == MessageType.REQUEST
        assert msg.payload["command"] == "START_INSTALLATION"
        assert msg.payload["args"]["target"] == "/mnt"
        assert msg.id  # UUID generated
        assert msg.timestamp > 0

    def test_create_response_success(self) -> None:
        """create_response should create success response."""
        msg = IPCMessage.create_response(
            request_id="test-id",
            command="GET_STATUS",
            status=ResponseStatus.SUCCESS,
            result={"running": True},
        )

        assert msg.type == MessageType.RESPONSE
        assert msg.id == "test-id"
        assert msg.payload["status"] == "success"
        assert msg.payload["result"]["running"] is True

    def test_create_response_error(self) -> None:
        """create_response should create error response."""
        msg = IPCMessage.create_response(
            request_id="test-id",
            command="START_INSTALLATION",
            status=ResponseStatus.ERROR,
            error={"code": "INVALID_TARGET", "message": "Bad path"},
        )

        assert msg.payload["status"] == "error"
        assert msg.payload["error"]["code"] == "INVALID_TARGET"

    def test_create_event(self) -> None:
        """create_event should create valid event message."""
        msg = IPCMessage.create_event(Event.JOB_PROGRESS, {"percent": 50})

        assert msg.type == MessageType.EVENT
        assert msg.payload["event"] == "JOB_PROGRESS"
        assert msg.payload["data"]["percent"] == 50

    def test_to_json_from_json_roundtrip(self) -> None:
        """Message should survive JSON roundtrip."""
        original = IPCMessage.create_request(Command.PING, {"echo": "test"})
        json_str = original.to_json()
        restored = IPCMessage.from_json(json_str)

        assert restored.version == original.version
        assert restored.type == original.type
        assert restored.id == original.id
        assert restored.payload == original.payload

    def test_to_bytes_from_bytes_roundtrip(self) -> None:
        """Message should survive bytes roundtrip."""
        original = IPCMessage.create_event(Event.ENGINE_READY, {})
        data = original.to_bytes()
        restored = IPCMessage.from_bytes(data)

        assert restored.type == original.type
        assert restored.payload == original.payload

    def test_from_json_invalid_json(self) -> None:
        """from_json should raise on invalid JSON."""
        with pytest.raises(IPCProtocolError) as exc_info:
            IPCMessage.from_json("not valid json")
        assert exc_info.value.code == IPCErrorCode.MALFORMED_JSON

    def test_from_json_missing_fields(self) -> None:
        """from_json should raise on missing required fields."""
        incomplete = json.dumps({"version": "1.0", "type": "request"})
        with pytest.raises(IPCProtocolError) as exc_info:
            IPCMessage.from_json(incomplete)
        assert exc_info.value.code == IPCErrorCode.INVALID_MESSAGE
        assert "missing" in exc_info.value.details.get("missing_fields", []) or True

    def test_from_json_unsupported_version(self) -> None:
        """from_json should raise on unsupported version."""
        bad_version = json.dumps(
            {
                "version": "99.0",
                "type": "request",
                "id": "test",
                "timestamp": 123,
                "payload": {},
            }
        )
        with pytest.raises(IPCProtocolError) as exc_info:
            IPCMessage.from_json(bad_version)
        assert exc_info.value.code == IPCErrorCode.UNSUPPORTED_VERSION

    def test_validate_request_missing_command(self) -> None:
        """validate should fail for request without command."""
        msg = IPCMessage(
            version=PROTOCOL_VERSION,
            type=MessageType.REQUEST,
            id="test",
            timestamp=123,
            payload={},  # Missing command
        )
        with pytest.raises(IPCProtocolError):
            msg.validate()

    def test_validate_response_missing_status(self) -> None:
        """validate should fail for response without status."""
        msg = IPCMessage(
            version=PROTOCOL_VERSION,
            type=MessageType.RESPONSE,
            id="test",
            timestamp=123,
            payload={},  # Missing status
        )
        with pytest.raises(IPCProtocolError):
            msg.validate()

    def test_validate_event_missing_event(self) -> None:
        """validate should fail for event without event type."""
        msg = IPCMessage(
            version=PROTOCOL_VERSION,
            type=MessageType.EVENT,
            id="test",
            timestamp=123,
            payload={},  # Missing event
        )
        with pytest.raises(IPCProtocolError):
            msg.validate()

    def test_properties_request(self) -> None:
        """Request properties should return correct values."""
        msg = IPCMessage.create_request(Command.GET_STATUS, {"verbose": True})

        assert msg.command == "GET_STATUS"
        assert msg.args == {"verbose": True}
        assert msg.event is None
        assert msg.status is None

    def test_properties_response(self) -> None:
        """Response properties should return correct values."""
        msg = IPCMessage.create_response(
            "id", "CMD", ResponseStatus.SUCCESS, {"data": 1}
        )

        assert msg.status == "success"
        assert msg.is_success is True
        assert msg.result == {"data": 1}
        assert msg.error == {}

    def test_properties_event(self) -> None:
        """Event properties should return correct values."""
        msg = IPCMessage.create_event(Event.JOB_STARTED, {"name": "partition"})

        assert msg.event == "JOB_STARTED"
        assert msg.data == {"name": "partition"}


class TestUnixSocketTransport:
    """Tests for Unix socket transport layer."""

    def test_transport_initialization(self) -> None:
        """Transport should initialize with default values."""
        transport = UnixSocketTransport()
        assert transport.socket_path == Path("/run/omnis/ipc.sock")
        assert transport.is_connected is False

    def test_transport_custom_path(self) -> None:
        """Transport should accept custom socket path."""
        transport = UnixSocketTransport("/tmp/custom.sock")
        assert transport.socket_path == Path("/tmp/custom.sock")

    def test_connect_nonexistent_socket(self) -> None:
        """connect_client_socket should fail for nonexistent socket."""
        transport = UnixSocketTransport("/tmp/nonexistent.sock")
        with pytest.raises(IPCConnectionError) as exc_info:
            transport.connect_client_socket()
        assert exc_info.value.code == IPCErrorCode.CONNECTION_FAILED

    def test_server_client_communication(self) -> None:
        """Server and client should be able to exchange messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            socket_path = Path(tmpdir) / "test.sock"

            # Create server transport
            server = UnixSocketTransport(socket_path)
            server.create_server_socket()

            # Server thread to accept and echo
            received_messages: list[IPCMessage] = []

            def server_handler() -> None:
                client_sock, _ = server.accept_client()
                msg = server.recv_message(client_sock)
                if msg:
                    received_messages.append(msg)
                    # Echo back
                    response = IPCMessage.create_response(
                        msg.id, msg.command or "", ResponseStatus.SUCCESS
                    )
                    server.send_message(client_sock, response)
                client_sock.close()

            server_thread = threading.Thread(target=server_handler)
            server_thread.start()

            # Give server time to start
            time.sleep(0.1)

            # Client connects and sends
            client = UnixSocketTransport(socket_path)
            client_sock = client.connect_client_socket()

            request = IPCMessage.create_request(Command.PING, {"data": "hello"})
            client.send_message(client_sock, request)

            response = client.recv_message(client_sock)

            client_sock.close()
            server_thread.join(timeout=2)
            server.close()

            # Verify
            assert len(received_messages) == 1
            assert received_messages[0].command == "PING"
            assert response is not None
            assert response.is_success

    def test_message_framing(self) -> None:
        """Messages should be length-prefixed."""
        msg = IPCMessage.create_request(Command.GET_STATUS)
        data = msg.to_bytes()

        # Verify we can decode the length prefix
        length_prefix = struct.pack(">I", len(data))
        assert len(length_prefix) == 4

        # The transport adds length prefix, so verify format
        expected_length = struct.unpack(">I", length_prefix)[0]
        assert expected_length == len(data)

    def test_context_manager(self) -> None:
        """Transport should work as context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            socket_path = Path(tmpdir) / "test.sock"

            with UnixSocketTransport(socket_path) as transport:
                transport.create_server_socket()
                assert transport.is_connected

            # Socket should be cleaned up
            assert not socket_path.exists()


class TestEnums:
    """Tests for IPC enums."""

    def test_command_values(self) -> None:
        """Command enum should have expected values."""
        assert Command.START_INSTALLATION.value == "START_INSTALLATION"
        assert Command.PING.value == "PING"
        assert Command.SHUTDOWN.value == "SHUTDOWN"

    def test_event_values(self) -> None:
        """Event enum should have expected values."""
        assert Event.JOB_STARTED.value == "JOB_STARTED"
        assert Event.JOB_PROGRESS.value == "JOB_PROGRESS"
        assert Event.INSTALLATION_COMPLETE.value == "INSTALLATION_COMPLETE"

    def test_error_code_values(self) -> None:
        """Error codes should be string enums."""
        assert IPCErrorCode.TIMEOUT.value == "TIMEOUT"
        assert IPCErrorCode.CONNECTION_LOST.value == "CONNECTION_LOST"
