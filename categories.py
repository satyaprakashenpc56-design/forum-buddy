"""Topic name -> category classification."""
from typing import Optional
import config


def classify(topic_name: Optional[str]) -> Optional[str]:
    if not topic_name:
        return None
    name = topic_name.lower()
    for category, keywords in config.CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in name:
                return category
    return None
