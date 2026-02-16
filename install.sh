#!/bin/sh

if [ -d ".venv" ]; then
    echo "Virtual environment already exists. Skipping Virtual environment creation."
else
    python -m venv .venv
fi
 source .venv/Scripts/activate \
    && python -m pip install -e. \
    && python -m pip install -r requirements.txt \
    && python -m pip install -r requirements/requirements-dev.txt \
    && python -m pip install -r requirements/requirements-browser.txt \
    && python -m pip install -r requirements/requirements-help.txt \
    && python -m pip install -r requirements/requirements-playwright.txt