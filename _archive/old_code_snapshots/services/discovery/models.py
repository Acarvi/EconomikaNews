from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class DiscoveryCandidate:
    url: str
    score: float
    reposts: int
    likes: int
    user: str
    source: str
    id: str
    type: str
    is_video: bool
    media_url: Optional[str]
    thumbnail: Optional[str]
    description: str
    score_source: str = "unknown"
    timestamp: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class XAccount:
    screen_name: str
    followers_hint: Optional[int] = None
