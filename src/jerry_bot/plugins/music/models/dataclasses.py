"""Dataclasses for the music plugin."""

from dataclasses import dataclass


@dataclass
class TrackMetadata:
    """Metadata for a music track. (For metadata extraction purposes)"""
    title: str
    artists: list[str]
    album: str
    length_seconds: float