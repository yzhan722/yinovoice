"""Config package exports."""

from platform_core.config.instance import InstanceConfig, TemplateConfig
from platform_core.config.loader import InstanceRepository, load_instance, load_template

__all__ = [
    "InstanceConfig",
    "TemplateConfig",
    "InstanceRepository",
    "load_instance",
    "load_template",
]
