"""Operational science-observatory runtime owned by the workbench.

Declarative discovery protocols and frozen query compilations remain external,
versioned data inputs. Importing this package performs no network access and has
no canonical-data side effects.
"""

from .source_contracts import ScienceContractBundle, ScienceContractError, load_science_contract_bundle

__all__ = [
    "ScienceContractBundle",
    "ScienceContractError",
    "load_science_contract_bundle",
]
