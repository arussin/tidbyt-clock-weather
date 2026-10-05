"""Read the original packaged material palette on explicit request."""

from functools import lru_cache
from importlib.resources import files
import json


@lru_cache(maxsize=1)
def resources():
    return json.loads(
        files(__package__).joinpath("assets/lighting.json").read_text(encoding="utf-8")
    )
