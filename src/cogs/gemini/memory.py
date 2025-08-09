"""Memory management utilities for the JerryGemini"""

from typing import Any, Dict, List, Optional, Union

import core as squidcore

from .ai_types import AIResponse, AIQuery, AISource, MemoryHistoryItem
from .prompts import QueryToTextConverter


class MongoDBOptions:
    """MongoDB options/constants"""

    COLLECTION_NAME = "jerry.gemini.history"

    DOC_SCHEMA = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["chat_id", "source", "content"],
            "properties": {
                "chat_id": {
                    "bsonType": "string",
                    "description": "Unique identifier for the chat session",
                },
                "channel_id": {
                    "bsonType": "string",
                    "description": "Constant identifier for the channel",
                },
                "source": {
                    "bsonType": "string",
                    "description": "Source of the query or response",
                    "enum": AISource.values(),
                },
                "content": {
                    "bsonType": "array",
                    "items": {
                        "bsonType": "string",
                        "description": "Content of the query or response as parts",
                    },
                },
                "timestamp": {
                    "bsonType": "date",
                    "description": "Timestamp of the query or response",
                },
                "user_id": {
                    "bsonType": "string",
                    "description": "ID of the user who made the query",
                },
            },
        }
    }
    DOC_INDEX = [
        ("chat_id", 1),  # Index for efficient querying by chat_id
        ("channel_id", 1),  # Index for efficient querying by channel_id
    ]  # Index for efficient querying by source and timestamp


class MemoryManager:
    """Memory Manager for JerryGemini using Redis and MongoDB."""

    def __init__(self, memory: squidcore.Memory):
        self.memory = memory
        self.collection = None

    async def init(self):
        """Initialize the memory manager."""
        if self.memory.mongo_db is None:
            raise ValueError("MongoDB connection is not established.")
        
        if not MongoDBOptions.COLLECTION_NAME in await self.memory.mongo_db.list_collection_names():
            await self.memory.mongo_db.create_collection(
                MongoDBOptions.COLLECTION_NAME,
                validator=MongoDBOptions.DOC_SCHEMA,
                validationAction="error",
                validationLevel="strict",
            )
            self.collection = self.memory.mongo_db[MongoDBOptions.COLLECTION_NAME]
            await self.collection.create_index(
                MongoDBOptions.DOC_INDEX,
                name="chat_id_channel_id_index",
            )
        else:
            self.collection = self.memory.mongo_db[MongoDBOptions.COLLECTION_NAME]

    def convert_to_dict(
        self, object: Union[AIQuery, AIResponse], chat_id: str, channel_id: str = "0"
    ) -> Dict[str, Any]:
        """
        Convert an AIQuery or AIResponse object to a dictionary for storage.

        Args:
            object (Union[AIQuery, AIResponse]): The object to convert.

        Returns:
            Dict[str, Any]: The converted dictionary.
        """
        if isinstance(object, AIQuery):
            return {
                "chat_id": str(chat_id),
                "channel_id": str(channel_id),
                "source": object.source.value,
                "content": QueryToTextConverter.convert(object),
                "user_id": str(object.author.id) if object.author else "",
            }
        elif isinstance(object, AIResponse):
            return {
                "chat_id": str(chat_id),
                "channel_id": str(channel_id),
                "source": object.source.value,
                "content": QueryToTextConverter.convert_response(object),
            }
        else:
            raise TypeError("Unsupported type for conversion.")
        
    def convert_to_memory_item(self, data: Dict[str, Any]) -> MemoryHistoryItem:
        """
        Convert a dictionary back to a MemoryHistoryItem.

        Args:
            data (Dict[str, Any]): The dictionary to convert.

        Returns:
            MemoryHistoryItem: The converted memory item.
        """
        return MemoryHistoryItem(
            chat_id=data["chat_id"],
            channel_id=data.get("channel_id", "0"),
            source=AISource(data["source"]),
            content=data["content"],
            user_id=data.get("user_id", None),
            raw=data,
        )

    async def load_history(
        self, chat_id: str = None, channel_id: str = "0"
    ) -> List[Dict[str, Any]]:
        """
        Load the chat history for a given chat ID and channel ID.

        Args:
            chat_id (str): The unique identifier for the chat session.
            channel_id (str): The constant identifier for the channel.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries representing the chat history.
        """
        if chat_id:
            items = await self.collection.find(
                {"chat_id": str(chat_id)}
            ).to_list(length=None)
        else:
            items = await self.collection.find(
                {"channel_id": str(channel_id)}
            ).to_list(length=None)
            
        return [self.convert_to_memory_item(item) for item in items]
    
    async def save_history(
        self, object: Union[AIQuery, AIResponse], chat_id: str, channel_id: str = "0"
    ) -> None:
        """
        Save an AIQuery or AIResponse object to the memory.

        Args:
            object (Union[AIQuery, AIResponse]): The object to save.
            chat_id (str): The unique identifier for the chat session.
            channel_id (str): The constant identifier for the channel.
        """
        data = self.convert_to_dict(object, chat_id, channel_id)
        await self.collection.insert_one(data)
        
    async def clear_history(self, chat_id: str = None, channel_id: str = "0") -> None:
        """
        Clear the chat history for a given chat ID and channel ID.

        Args:
            chat_id (str): The unique identifier for the chat session.
            channel_id (str): The constant identifier for the channel.
        """
        if chat_id:
            await self.collection.delete_many({"chat_id": str(chat_id)})
        else:
            await self.collection.delete_many({"channel_id": str(channel_id)})