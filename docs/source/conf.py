# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "Avantis Trader SDK"
copyright = "2025, Avantis Labs"
author = "Avantis Labs"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",  # Include documentation from docstrings
    "sphinx.ext.coverage",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",  # Add links to highlighted source code
    "sphinx_autodoc_typehints",  # Add this line
    "sphinx_markdown_builder",
]

autodoc_typehints = "description"
autodoc_typehints_format = "short"
autodoc_preserve_defaults = True

templates_path = ["_templates"]
exclude_patterns = ["utils.py", "config.py"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# Make docs with sphinx-apidoc -o docs/source avantis_trader_sdk/
# Then make html with make html in docs directory
