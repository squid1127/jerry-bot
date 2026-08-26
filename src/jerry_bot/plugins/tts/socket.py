"""Socket client for interacting with the TTS service."""

from pathlib import Path
import asyncio
import json
from logging import Logger

from .models.request import TTSRequest, TTSResponse
from .models.exceptions import TTSGenerationError, TTSServerConnectionError

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
        self._read_task: asyncio.Task | None = None
        
    async def connect(self) -> None:
        """Connect to the TTS socket."""
        if not self._socket.exists():
            raise FileNotFoundError(f"TTS socket not found at {self._socket}")
        
        reader, writer = await asyncio.open_unix_connection(self._socket)
        self._writer = writer
        self._read_task = asyncio.create_task(self._read_loop(reader))
        
    async def disconnect(self) -> None:
        """Disconnect from the TTS socket."""
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
        """Send a TTS request to the socket.
        """
        
        self.writer.write(request.to_json_bytes() + b"\n")
        await self.writer.drain()
        
    async def _read_loop(self, reader: asyncio.StreamReader) -> None:
        """
        Read loop for processing incoming TTS responses from the socket.
        """
        
        response = None
        while (line := await reader.readline()):
            try:
                response = TTSResponse.from_json_bytes(line)
                self._logger.info(f"Received TTS response: {response}")
                
                if response.uuid in self._pending:
                    future = self._pending.pop(response.uuid)
                    if not future.done():
                        future.set_result(response)
                else:
                    self._logger.warning(f"Received TTS response with unknown UUID: {response.uuid}")
            except ValueError as e:
                self._logger.error(f"Failed to parse TTS response: {e}")
            except KeyError:
                self._logger.error(f"Received TTS response with unknown UUID: {response.uuid if response else 'unknown'}")
        

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
            raise TTSServerConnectionError("Socket client is not connected. Try calling 'connect()' first.")
        return self._writer