"""Proccess and convert discord.attachment files into a consistent format for providers"""

import discord
import logging
import magic  # python-magic for MIME type detection

# Internal imports
from .constants import ConfigFileDefaults
from .ai_types import AIQuery, QueryAttachment

logger = logging.getLogger("jerry.JerryGemini.files")

class FileProcessor:
    """
    Processes and converts discord.attachment files into a consistent format for providers.
    """
    
    @staticmethod
    def _get_mime_type(data: bytes) -> str | None:
        """
        Detects the MIME type of a file from its raw byte data using python-magic.

        Args:
            data (bytes): The raw byte data of the file.

        Returns:
            str | None: The detected MIME type as a string (e.g., 'image/png'),
                        or None if detection fails.
        """
        try:
            # The 'mime=True' argument tells python-magic to return the MIME type string.
            mime_type = magic.from_buffer(data, mime=True)
            return mime_type
        except Exception as e:
            logger.warning(f"Could not detect MIME type using python-magic: {e}")
            return None

    @staticmethod
    async def process_files(query: AIQuery, attachments: list[discord.Attachment]) -> None:
        """
        Process the provided attachments and add them to the query.

        Args:
            query (AIQuery): The AI query object to which the processed files will be added.
            attachments (list[discord.Attachment]): List of discord attachments to process.
        """
        for attachment in attachments:
            # if attachment.size > ConfigFileDefaults.MAX_FILE_SIZE.value:
            #     continue  # Skip files that are too large

            if not isinstance(attachment, discord.Attachment):
                logger.debug(f"Skipping non-attachment file: {attachment}")
                continue  # Skip non-attachment files

            file_content = await attachment.read()
            if not file_content:
                logger.debug(f"Skipping empty file: {attachment.filename}")
                continue
            
            # Detect the MIME type of the file
            mime_type = FileProcessor._get_mime_type(file_content)
            if not mime_type:
                mime_type = attachment.content_type or None

            logger.info(f"Processing file: {attachment.filename} ({attachment.size} bytes) | {mime_type or 'unknown'} | {attachment.url} | {attachment.id}")

            # Create a QueryAttachment object and add it to the query
            query_attachment = QueryAttachment(
                attachment_id=attachment.id,
                url=attachment.url,
                filename=attachment.filename,
                content_type=mime_type,
                raw_data=file_content,
            )
            query.attachments.append(query_attachment)
