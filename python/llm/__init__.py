"""
LLM-assisted strategy discovery utilities and sample strategies.

This package contains lightweight abstractions that describe the artifacts an
LLM must produce (metadata, configs, code) alongside human-readable examples.
"""

from .metadata import (
    BacktestSpec,
    DataSpec,
    ParameterSpec,
    StrategyManifest,
    StrategyMetadata,
    StrategyPackage,
)

__all__ = [
    "BacktestSpec",
    "DataSpec",
    "ParameterSpec",
    "StrategyManifest",
    "StrategyMetadata",
    "StrategyPackage",
]

