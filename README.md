# anki-auto

> Automation for Anki card creation and modifications.

[![CI](https://github.com/liav-hasson/anki-auto/actions/workflows/ci.yml/badge.svg)](https://github.com/liav-hasson/anki-auto/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

## Overview

**anki-auto** is a Python library and CLI tool that automates the creation and
modification of [Anki](https://apps.ankiweb.net/) flashcard decks — letting you
focus on learning, not card management.

## Features

- [ ] Auto-generate cards from plain text / Markdown
- [ ] Bulk-edit existing decks
- [ ] CLI interface

## Project layout

```
anki-auto/
├── src/
│   └── anki_auto/          # Library source code
│       └── __init__.py
├── tests/                   # pytest test suite
│   └── test_smoke.py
├── docs/                    # Documentation
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI
├── .gitignore
├── CHANGELOG.md
├── LICENSE
├── pyproject.toml           # Build & tool configuration
└── README.md
```

## Getting started

### Prerequisites

- Python 3.10+
- [pip](https://pip.pypa.io/)

### Installation (development)

```bash
# Clone the repo
git clone https://github.com/liav-hasson/anki-auto.git
cd anki-auto

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install the package in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Running tests

```bash
pytest
```

### Linting & type-checking

```bash
ruff check .        # lint
ruff format --check .  # format check
mypy                # type check
```

## Contributing

Pull requests are welcome! Please open an issue first to discuss what you would
like to change.

1. Fork the repo and create your feature branch (`git checkout -b feat/my-feature`)
2. Commit your changes (`git commit -m 'feat: add some feature'`)
3. Push to the branch (`git push origin feat/my-feature`)
4. Open a Pull Request

## License

Distributed under the [MIT License](LICENSE).
