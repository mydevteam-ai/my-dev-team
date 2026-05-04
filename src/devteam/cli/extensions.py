from collections.abc import Callable
from dataclasses import dataclass, field
from devteam import settings
from devteam.extensions import ConsoleLogger, CrewExtension, HumanInTheLoop


@dataclass(frozen=True)
class ExtensionSpec:
    factory: Callable[[], CrewExtension]
    enabled: Callable[[], bool] = field(default=lambda: True)


_EXTENSIONS: list[ExtensionSpec] = [
    ExtensionSpec(ConsoleLogger, enabled=lambda: settings.console),
    ExtensionSpec(HumanInTheLoop),
]


def build_extensions() -> list[CrewExtension]:
    return [spec.factory() for spec in _EXTENSIONS if spec.enabled()]
