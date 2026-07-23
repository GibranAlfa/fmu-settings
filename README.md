# fmu-settings

[![ci](https://github.com/equinor/fmu-settings/actions/workflows/ci.yml/badge.svg)](https://github.com/equinor/fmu-settings/actions/workflows/ci.yml)
[![docs](https://github.com/equinor/fmu-settings/actions/workflows/docs.yml/badge.svg)](https://github.com/equinor/fmu-settings/actions/workflows/docs.yml)

**Documentation**: <a href="https://equinor.github.io/fmu-settings/" target="_blank">https://equinor.github.io/fmu-settings/</a>

**Source code**: <a href="https://github.com/equinor/fmu-settings/" target="_blank">https://github.com/equinor/fmu-settings/</a>

`fmu-settings` is the Python core library for reading, writing, and managing resources in `.fmu/` directories for FMU projects and user environments.

It owns the filesystem behavior around those resources: initialization, discovery, configuration models, resource managers, locking, cache handling, changelogs, restore behavior, and synchronization helpers.

## FMU Settings Architecture

FMU Settings is split across a few repositories:

```mermaid
flowchart LR
    CLI["fmu-settings-cli"]
    API["fmu-settings-api\nAPI and static-file host"]
    GUI["fmu-settings-gui\nReact source and packaged assets"]
    LIB["fmu-settings"]
    MODELS["fmu-datamodels"]

    CLI -->|starts one application process| API
    CLI -->|gets packaged assets| GUI
    CLI --> LIB
    GUI -->|browser API calls| API
    API --> LIB
    LIB --> MODELS
    API --> MODELS
```

- [`fmu-settings`](https://github.com/equinor/fmu-settings) is the core library for reading, writing, and managing `.fmu/` resources.
- [`fmu-datamodels`](https://github.com/equinor/fmu-datamodels) provides shared Pydantic domain models.
- [`fmu-settings-api`](https://github.com/equinor/fmu-settings-api) exposes `fmu-settings` through a FastAPI application layer and serves the packaged GUI assets.
- [`fmu-settings-gui`](https://github.com/equinor/fmu-settings-gui) provides the browser-based user interface and packages its static assets.
- [`fmu-settings-cli`](https://github.com/equinor/fmu-settings-cli) provides the user-facing command line interface, including commands that bootstrap local user state and launch the combined application.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the library architecture and a high-level ecosystem overview.

## Documentation

The published documentation is the best starting point for users:

- [Overview](https://equinor.github.io/fmu-settings/overview.html)
- [Getting started](https://equinor.github.io/fmu-settings/getting_started.html)
- [GUI user guide](https://equinor.github.io/fmu-settings/gui_user_guide.html)
- [Terminal commands](https://equinor.github.io/fmu-settings/terminal_commands.html)

Documentation sources live under `docs/src/`.

## Developing

Clone and install into a virtual environment.

```sh
git clone git@github.com:equinor/fmu-settings.git
cd fmu-settings
# Create or source virtual/Komodo env
pip install -U pip
pip install -e ".[dev]"
# Make a feature branch for your changes
git checkout -b some-feature-branch
```

Run the tests with:

```sh
pytest -n auto tests
```

Ensure your changes will pass the various linters before making a pull
request. It is expected that all code will be typed and validated with
mypy.

```sh
ruff check
ruff format --check
mypy src tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for more.

> [!NOTE]
> #### Trademark Notice and Disclaimer
> **Aspen RMS™** is a registered trademark of [Aspen Technology, Inc.](https://www.aspentech.com/en)
> (AspenTech). Use of RMS™ is governed by AspenTech's licensing terms and
> conditions. It is proprietary software and is neither open-source nor free. A
> valid license agreement with AspenTech is required for its use.
>
> **fmu-settings** is an independent project developed by Equinor and is neither
> produced by nor affiliated with AspenTech.
