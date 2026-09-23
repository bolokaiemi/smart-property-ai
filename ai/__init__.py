"""Smart Property AI package.

This package contains the conversational assistant, language handling,
safety checks, prompt construction, inference, preprocessing, training,
evaluation, and model registry used by Smart Property AI.

The package initializer intentionally avoids importing the implementation
modules. This keeps ``import ai`` lightweight and prevents circular imports
while the remaining AI modules are initialized.
"""

from __future__ import annotations


__all__ = [
    "__author__",
    "__description__",
    "__version__",
]


__version__ = "1.0.0"

__author__ = "Ebi Emmerich-Adehor"

__description__ = (
    "Multilingual, privacy-aware property and tenancy assistant for "
    "Smart Property AI."
)