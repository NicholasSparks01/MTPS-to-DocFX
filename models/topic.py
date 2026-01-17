from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TopicMetadata:
    # Identity
    help_id: str                 # MSDN.sdk-api-build/...
    uid: str                     # MSDN.sdk-api-build.foo.bar
    title: str

    # Localization & product
    locale: str = "en-us"
    topic_version: Optional[str] = None

    # Docs metadata
    canonical_url: Optional[str] = None
    toc_parent: Optional[str] = None
    toc_order: Optional[int] = None

    # Search
    keywords: List[str] = field(default_factory=list)

    # Dates
    ms_date: Optional[str] = None
