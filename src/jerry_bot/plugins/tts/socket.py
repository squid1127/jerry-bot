"""Socket client for interacting with the TTS service."""

import asyncio
from logging import Logger
from pathlib import Path

from .models.exceptions import TTSGenerationError, TTSServerConnectionError
from .models.request import TTSRequest, TTSResponse



class TTSSocketClient:
    """Socket client for interacting with the TTS service."""

    def __init__(self, socket: Path, logger: Logger, max_concurrent_requests: int = 5):
        """Initialize the TTS socket client.

        Args:
            socket (Path): The path to the TTS socket.
        """
        self._socket = socket
        self._writer: asyncio.StreamWriter | None = None
        self._logger = logger
        self._pending: dict[str, asyncio.Future[TTSResponse]] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._read_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._is_disconnecting = False

    async def connect(self) -> None:
        """Connect to the TTS socket."""
        if self._writer is not None:
            self._logger.warning("Already connected to TTS socket.")
            return

        if not self._socket.exists():
            raise FileNotFoundError(f"TTS socket not found at {self._socket}")

        reader, writer = await asyncio.open_unix_connection(self._socket)
        self._writer = writer
        self._is_disconnecting = False
        self._read_task = asyncio.create_task(self._read_loop(reader))

    async def disconnect(self) -> None:
        """Disconnect from the TTS socket."""
        self._is_disconnecting = True

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None

        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None

        self._fail_pending_requests("Disconnected from TTS socket.")

    async def generate_tts(self, request: TTSRequest) -> TTSResponse:
        """Send a TTS request and receive a response.

        Args:
            request (TTSRequest): The TTS request to send.

        """
        async with self._semaphore:
            future = asyncio.Future[TTSResponse]()
            self._pending[request.uuid] = future
            await self._send_request(request)
            response = await future
            if response and response.status != "success":
                self._logger.error(f"TTS generation failed: {response.message}")
                raise TTSGenerationError(f"TTS generation failed: {response.message}")
        return response

    async def _send_request(self, request: TTSRequest) -> None:
        """Send a TTS request to the socket."""
        try:
            self.writer.write(request.to_json_bytes() + b"\n")
            await self.writer.drain()
        except OSError as e:
            self._logger.error(f"Failed to send request over TTS socket: {e}")
            self._writer = None
            raise TTSServerConnectionError(f"Failed to send request: {e}") from e

    async def _read_loop(self, reader: asyncio.StreamReader) -> None:
        """
        Read loop for processing incoming TTS responses from the socket.
        """
        response = None
        try:
            while line := await reader.readline():
                try:
                    response = TTSResponse.from_json_bytes(line)
                    self._logger.info(f"Received TTS response: {response}")

                    if response.uuid in self._pending:
                        future = self._pending.pop(response.uuid)
                        if not future.done():
                            future.set_result(response)
                    else:
                        self._logger.warning(
                            f"Received TTS response with unknown UUID: {response.uuid}"
                        )
                except ValueError as e:
                    self._logger.error(f"Failed to parse TTS response: {e}")
                except KeyError:
                    self._logger.error(
                        f"Received TTS response with unknown UUID: {response.uuid if response else 'unknown'}"
                    )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._logger.error(f"Error in TTS socket read loop: {e}")
        finally:
            self._logger.warning("TTS socket connection closed.")
            self._writer = None
            self._fail_pending_requests("TTS socket connection closed.")

            if not self._is_disconnecting:
                self._trigger_reconnect()

    def _fail_pending_requests(self, reason: str) -> None:
        """Fail all pending requests with a connection error."""
        pending = list(self._pending.items())
        self._pending.clear()
        for _, future in pending:
            if not future.done():
                future.set_exception(TTSServerConnectionError(reason))

    def _trigger_reconnect(self) -> None:
        """Trigger background reconnection if not already reconnecting."""
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Background loop to attempt reconnection to the TTS socket."""
        delay = 1.0
        max_delay = 30.0
        self._logger.info("Starting TTS socket reconnection loop...")

        while not self._is_disconnecting:
            try:
                self._logger.info(
                    f"Attempting to reconnect to TTS socket at {self._socket}..."
                )
                await self.connect()
                self._logger.info("Successfully reconnected to TTS socket.")
                break
            except Exception as e:
                self._logger.warning(
                    f"Reconnection attempt failed: {e}. Retrying in {delay:.1f} seconds..."
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)

    @property
    def socket(self) -> Path:
        """Get the path to the TTS socket.

        Returns:
            Path: The path to the TTS socket.
        """
        return self._socket

    @property
    def writer(self) -> asyncio.StreamWriter:
        """Get the stream writer for the socket.

        Returns:
            asyncio.StreamWriter: The stream writer for the socket, or None if not connected.
        """
        if self._writer is None:
            raise TTSServerConnectionError(
                "Socket client is not connected. Try calling 'connect()' first."
            )
        return self._writer

    @property
    def is_connected(self) -> bool:
        """Check if the socket client is connected.

        Returns:
            bool: True if connected, False otherwise.
        """
        return self._writer is not None
