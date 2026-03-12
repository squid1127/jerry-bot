"""Message rendering module for the Gemini plugin, responsible for converting Message objects into string formats suitable for model processing or logging.
"""
from ..models import Message, UserMessage, ModelMessage, SystemMessage, ExceptionMessage
from typing import Union, ClassVar

class MessageRenderer:
    """Renderer for converting Message objects into string formats for model processing or logging."""
    
    MESSAGE_FLAGS: ClassVar[dict[type, str]] = {
        UserMessage: "[USER]",
        ModelMessage: "[MODEL]",
        SystemMessage: "[SYSTEM]",
        ExceptionMessage: "[SYSTEM => EXCEPTION]",
    }
    MESSAGE_SEPARATOR: ClassVar[str] = "\n[END]\n"
    
    def render_many(self, messages: list[Message]) -> str:
        """Render a list of Message objects into a single string format."""
        return self.MESSAGE_SEPARATOR.join(self.render(message) for message in messages)

    def render(self, message: Message) -> str:
        """Render a Message object to a string format."""
        if isinstance(message, UserMessage):
            return self._render_user_message(message)
        elif isinstance(message, ModelMessage):
            return self._render_model_message(message)
        elif isinstance(message, SystemMessage):
            return self._render_system_message(message)
        elif isinstance(message, ExceptionMessage):
            return self._render_exception_message(message)
        else:
            raise ValueError(f"Unsupported message type for rendering: {type(message)}")
        
    def _render_user_message(self, message: UserMessage) -> str:
        """Render a UserMessage to a string format."""

        header = self.MESSAGE_FLAGS[UserMessage] 
        if message.user:
            header += f" => {message.user.name} ({message.user.mention})\n"
        else:
            header += "\n"
            
        content = message.content if message.content else ""
        
        # Prevent accidental injection of flags in user content by escaping them and adding a warning if they are present
        for flag in list(self.MESSAGE_FLAGS.values()) + [self.MESSAGE_SEPARATOR]:
            if flag in content:
                content = content.replace(flag, f"[Fake {flag}]")
                header += "[WARNING: User message content contained potential injection of a message flag. The flag has been removed from the content to prevent issues.]\n"
                
        if message.attachments:
            header += f"[{len(message.attachments)} attachment(s) included but not rendered due to current limitations]\n"
        
        return header + content
        
    def _render_model_message(self, message: ModelMessage) -> str:
        """Render a ModelMessage to a string format."""
        # Models break for some reason if we include the [MODEL] flag, so we will omit it for now.
        # The class type and model role kind of conflict with the [MODEL] flag, which appears to be the root issue
        # content = self.MESSAGE_FLAGS[ModelMessage] + "\n"
        content = ""
        content += message.content if message.content else ""
        return content.strip()

    def _render_system_message(self, message: SystemMessage) -> str:
        """Render a SystemMessage to a string format."""
        content = self.MESSAGE_FLAGS[SystemMessage] + "\n"
        content += message.content
        return content

    def _render_exception_message(self, message: ExceptionMessage) -> str:
        """Render an ExceptionMessage to a string format."""
        content = self.MESSAGE_FLAGS[ExceptionMessage] + "\n"
        content += message.content
        return content