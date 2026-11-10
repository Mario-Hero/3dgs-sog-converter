"""3DGS -> SOG converter package."""

from .core import (  # noqa: F401
    Cancelled,
    ConversionError,
    Job,
    Options,
    Report,
    Result,
    cli_version,
    collect_inputs,
    find_cli,
    plan_jobs,
    run_conversion,
)

__version__ = "1.0.0"
