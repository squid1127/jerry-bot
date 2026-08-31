"""Exceptions for tts"""

class TTSError(RuntimeError):
    """Base error class for TTS errors"""

class TTSRunnerError(TTSError):
    """Raised when the TTS runner fails"""

class TTSRunnerTimeoutError(TTSRunnerError):
    """Raised when the TTS runner times out"""

class TTSGenerationError(TTSError):
    """Raised when generation of speech fails"""
    
class TTSServerConnectionError(TTSError):
    """Raised when the service socket connection fails"""
    
class TTSVoiceError(TTSError):
    """Base class for exceptions related to the voice client"""
    
class TTSVoiceInUseError(TTSVoiceError):
    """Raised when a voice client is already in use in a guild"""
    
class TTSVoiceConnectionError(TTSVoiceError):
    """Raised when a voice client cannot connect to discord"""

