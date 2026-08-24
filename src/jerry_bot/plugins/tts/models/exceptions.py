"""Exceptions for tts"""

class TTSError(RuntimeError):
    """Base error class for TTS errors"""
    pass

class TTSGenerationError(TTSError):
    """Raised when generation of speech fails"""
    pass
    
class TTSServerConnectionError(TTSError):
    """Raised when the service socket connection fails"""
    pass
    
class TTSVoiceError(TTSError):
    """Base class for exceptions related to the voice client"""
    pass
    
class TTSVoiceInUseError(TTSVoiceError):
    """Raised when a voice client is already in use in a guild"""
    pass
    
class TTSVoiceConnectionError(TTSVoiceError):
    """Raised when a voice client cannot connect to discord"""
    pass

