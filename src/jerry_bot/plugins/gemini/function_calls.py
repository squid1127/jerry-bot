"""Function call base class for Gemini interactions."""

from typing import Any, Dict, Optional
from abc import ABC, abstractmethod

from .models.gemini import FunctionCallParam, MessagePart

class GeminiFunctionCall(ABC):
    """Abstract base class representing a Gemini function call."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the function."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return the description of the function."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """Return the parameters schema of the function."""
        pass

    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> list[MessagePart]:
        """Execute the function with the given arguments.

        Args:
            arguments (Dict[str, Any]): The arguments for the function call.

        Returns:
            list[MessagePart]: Responses, which can be sent to user or returned to the model.
        """
        pass