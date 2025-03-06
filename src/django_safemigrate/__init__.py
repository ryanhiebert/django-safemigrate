from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum


class When(Enum):
    ALWAYS = "always"
    BEFORE_DEPLOY = "before_deploy"
    AFTER_DEPLOY = "after_deploy"


@dataclass
class Safe:
    when: When
    delay: timedelta | None = None

    @classmethod
    def always(cls):
        return cls(when=When.ALWAYS)

    @classmethod
    def before_deploy(cls):
        return cls(when=When.BEFORE_DEPLOY)

    @classmethod
    def after_deploy(cls, *, delay: timedelta = None):
        return cls(when=When.AFTER_DEPLOY, delay=delay)
