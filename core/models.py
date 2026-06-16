"""The single in-memory representation of a logged game.

Both the impressions form and the markdown parser produce/consume GameEntry;
the markdown renderer is the only thing that turns one back into text.
"""
from dataclasses import dataclass, field

from . import config

DEFAULT_FEEDBACK_EMOJI = "👍👎"


@dataclass
class GameEntry:
    title: str = ""
    store_url: str = ""
    playtime: str = ""                 # already formatted, e.g. "45 minutes" / "1.8 hours"
    will_purchase: str = ""
    tags: str = ""                     # raw "Type" string, e.g. "action,horror"
    description: str = ""              # 🕹️ Description body
    feedback: str = ""                # 👍👎 Feedback body
    feedback_emoji: str = DEFAULT_FEEDBACK_EMOJI
    screenshots: list = field(default_factory=list)  # full-size filenames (basenames)
    appid: int = None                  # the played (demo) appid, for screenshots

    @property
    def anchor(self):
        return config.title_anchor(self.title)

    @property
    def slug(self):
        return config.game_slug(self.title)
