# AGENTS.md — Agent Guidelines for Wattpilot

This document provides context, architectural rules, engineering standards, and collaboration workflows for AI agents working in this repository. It reflects the guidance and preferences established by the project maintainer.

---

## 1. Project Overview & Architecture

Wattpilot is an intelligent water boiler controller designed to optimize photovoltaic (PV) auto-consumption. Instead of expensive variable-resistance hardware, it discretely controls multiple heating elements (typically 3 electrical resistances) in a hot water boiler based on:
- Solar surplus exported to the grid (interfacing with Fronius inverters).
- Forecast cloudiness / weather forecasts (OpenWeatherMap API).
- Configurable off-peak electricity schedule windows.
- Manual "force" heating mode with temperature hysteresis.

### Key Architecture Components
- **`wattpilot/`**: Core backend logic and actor system.
  - Built on **Pykka** actor model (`wattpilot/actor.py`, `wattpilot/wattpilot.py`).
  - Hardware abstraction using Abstract Base Classes (`wattpilot/device.py` for `Gpio` and `Sensor`).
  - State machine-driven control loop (`transitions` library).
  - Cascading INI configuration system (`wattpilot/settings.py`).
- **`frontend/`**: Web user interface built with **NiceGUI**.
  - Completely decoupled from `wattpilot/` backend (the backend has zero UI dependencies).
  - Interacts with actors through typed actor proxies (`frontend/service.py`).
  - Responsive, mobile-optimized dashboard and control pages.
  - Client-side cookie persistence and JSON-based i18n (English and French).
- **`test/`**: Unit and integration test suite using `pytest`.

---

## 2. Collaboration & Development Workflow

### Planning First (`/plan`)
- For new features, architectural migrations, or significant refactorings, **always create a clear, detailed plan** (e.g. Markdown plan artifact or dedicated plan file) before writing code.
- Align on design choices, dependencies, and file layout with the user before executing.

### Review Before Committing
- **Never commit changes automatically or unilaterally.**
- When work is done, present changes for user review (e.g., summarize pending changes, file diffs, and verification results).
- Wait for explicit user instructions (`commit`, `Create scoped commits`, etc.) before running git commit commands.

### Scoped Git Commits
- Create **scoped, atomic commits** where each commit represents a single logical change or concern.
- **Commit message format**: `<scope>: <Imperative summary>`
  - Examples:
    - `typing: Add type annotations and fix pre-commit issues`
    - `frontend: Move Change Mode card to dashboard`
    - `docker: Expose port 8080 and map port 80 in compose`
    - `ci: Migrate from Travis CI to GitHub Actions`
    - `wattpilot: Support temperature limit and hysteresis in force mode`
- **Amend commits** when fixing or refining a change that belongs to the immediate preceding commit rather than cluttering history with fixup commits.

### Hygiene & Zero-Cruft Policy
- Actively remove obsolete code, dead dependencies, deprecated configuration files, and stale documentation/TODOs when replacing systems (e.g. legacy Travis CI, Codecov, OpenAPI/Connexion/Flask were cleanly removed during the migration).

---

## 3. Environment, Tooling & CI/CD

- **Python Version**: Python 3.14 (Docker base image `python:3.14-trixie`). Do not upgrade to Python 3.15 until official Docker images are available.
- **Package Manager**: **`uv`**. Use `uv sync`, `uv add`, and `uv run`. Lockfile is `uv.lock`. Do not maintain loose `requirements.txt` files.
- **Devcontainer**:
  - Configured via `.devcontainer/devcontainer.json` and `.devcontainer/docker-compose.yml`.
  - Default shell is **`bash`** (`terminal.integrated.defaultProfile.linux: "bash"`), not `/bin/sh`.
  - Mounts `~/.gemini` into the container.
- **Linters & Type Checkers**:
  - **`ruff`**: Linting and code formatting (`ruff check --fix`, `ruff format`).
  - **`ty`**: Astral's static type checker (`ty check`).
  - **`pre-commit`**: Configured in `.pre-commit-config.yaml` with trailing whitespace, YAML/TOML validation, `ruff`, and `ty`. Pre-commit must always pass cleanly.
- **Continuous Integration**:
  - GitHub Actions (`.github/workflows/ci.yml`).
  - Runs pre-commit checks and pytest inside the Docker Compose development container.
- **Ports & Docker**:
  - Application listens on port `8080` internally.
  - Production `docker-compose.yml` maps port `80:8080`.
  - Development `docker-compose.development.yml` maps port `8088:8080`.

---

## 4. Python & Backend Coding Standards

### Type Annotations
- Strict static typing across all modules and tests.
- **Avoid `Any`** wherever possible.
- **NO `if TYPE_CHECKING:` workarounds**: All type annotations must be valid and resolvable at runtime without type-guard branching hacks.
- **Pykka Actor Proxies**: Always annotate actor proxies as `ActorProxy[T]` (e.g. `ActorProxy[WattPilotActor]`), never `Any`.

### Pykka Actor Interactions
- Remember that calling methods on actor proxies (`proxy.some_method()`) returns a **Future**.
- Query the result with `.get()` when retrieving data synchronously.
- **Avoid using `defer()`**: Calling `proxy.some_method.defer(...)` will stop the actor if the method raises an uncaught exception. Instead, invoke the proxy method directly (`proxy.some_method(...)`) or ensure the method handles exceptions internally.
- **Do not access actor fields directly via proxy**: Never access attributes or fields directly through an actor proxy (e.g. `proxy.field.get()`). Always create a dedicated getter method on the actor (e.g. `def get_field(self) -> ...`) and query it via the proxy (`proxy.get_field().get()`).

### Object-Oriented Design & Abstractions
- Prefer **Abstract Base Classes (`abc.ABC` with `@abstractmethod`)** over `typing.Protocol` (e.g. `Gpio` and `Sensor` base classes in `wattpilot/device.py`).
- Keep classes lean: do not add unused or redundant attributes (e.g. avoid adding unused `self.name` to sensor classes).
- **Private Methods**: Always use **double underscore (`__`)** for private methods (e.g. `__generate_period_svg`, `__init_ui`, `__apply_settings`).

---

## 5. Frontend & UI Guidelines (NiceGUI)

### Location & Isolation
- All UI code resides in **`frontend/`**.
- Keep backend (`wattpilot/`) free of NiceGUI imports and dependencies.

### Styling Rule (CRITICAL)
- **Avoid styling in Python files!**
  - Do NOT clutter `.py` files with excessive inline `.style(...)` calls or complex styling dictionaries.
  - All custom styling must live in **`frontend/static/style.css`**.
  - Use standard Tailwind utility classes (e.g. `w-full`, `gap-4`, flex/grid classes) for basic layout structure, but delegate visual and component decoration to CSS.
  - If a layout issue occurs (e.g. SVG not expanding), use Tailwind classes like `w-full` rather than adding inline CSS strings to Python.

### Mobile-First & Layout
- The UI must work on desktop but **must be optimized for mobile screens**.
- Use responsive grids (e.g. cards spanning 2 columns when wide enough, collapsing to 1 column on mobile).
- The "Change Mode" card is located at the bottom of the Dashboard page.

### Internationalization (i18n)
- Default language is **English (`en`)**, with full **French (`fr`)** translation.
- Translations are stored in JSON files: `frontend/locales/en.json` and `frontend/locales/fr.json`.
- Use **nested JSON keys** (e.g. `{"state": {"title": "State", "halt": "Halt"}}`), not flat concatenated keys.
- Always ensure translation key parity between language files (covered by unit tests in `test/test_settings.py`).
- Automatic language detection detects browser headers / cookie preference.
- Beware of translation text length: ensure French labels (e.g. "Forcer", "Corps de chauffe") do not cause awkward text wraps or overflow badges and buttons.

### Storage & User Preferences
- **No server-side storage for UI session preferences.** Avoid `app.storage.user` because it writes sessions on the server.
- Use **client-side cookies** (e.g. `wattpilot_lang`) to persist UI settings like language. Keep detection and persistence logic simple.

### Domain Terminology & UI Clarity
- Use domain-specific terminology:
  - Refer to electrical loads as **"Heating element"** ("Corps de chauffe" in French), not generic hardware terms like "GPIO".
- Visual representations must be intuitive:
  - Heating loads are displayed as 3 progressive bars filling up with distinct colors (e.g. green, orange, red) with proper spacing.
  - Cloudiness / weather forecast indicators should clearly represent cloud probability without misleading inverted solar graphics.
  - Avoid unnecessary decorative clutter (e.g. do not add meaningless status dots next to page titles, avoid redundant labels like "3 active" when the graphic already shows it).
- Add clear help text for potentially ambiguous inputs (e.g. help text for schedule "End time").
- Self-contained components: encapsulate component-specific rendering (such as SVG generation) directly inside the component class (e.g. `SchedulePeriodChart`).

---

## 6. Configuration & Domain Rules

### 3-Tier Cascading Configuration
Configuration is loaded in cascading order (later files override earlier ones):
1. `config.ini`: Base configuration defaults (version-controlled).
2. `config.ini.local`: Local hardware/installation settings (gitignored).
3. `config.ini.settings`: Runtime UI settings with highest priority (path configurable via `WATTPILOT_SETTINGS` environment variable).

### Schedule Window & Time Handling
- All schedule evaluation and UI display run in **local system time**, not UTC.
- **Midnight Wrap-Around**: Schedule windows must support wrapping past midnight (e.g. `schedule_start = 23` and `schedule_stop = 2` means a 3-hour period from 23:00 to 02:00). When `start == stop`, the window covers 0 hours (disabled).

### Temperature Thresholds & Hysteresis
- Three configurable temperatures:
  - `temperature_schedule`: Target temperature during scheduled off-peak window.
  - `temperature_solar`: Target temperature when heating with solar surplus.
  - `temperature_force`: Target temperature in manual Force mode.
- Range: **45.0°C to 65.0°C** in **0.5°C steps**.
- **Force Mode Hysteresis**: In Force mode, all loads stop once `temperature_force` is reached, and reactivate if temperature drops below `temperature_force - hysteresis`.

---

## 7. Testing & Verification

- **Running Tests**:
  ```bash
  pytest -v -s --cov=wattpilot --cov-report term test/
  ```
- **Running Linting & Type Checking**:
  ```bash
  pre-commit run --all-files
  ```
  Or individually:
  ```bash
  ruff check --fix .
  ruff format .
  ty check
  ```
- **Testing Policy**:
  - Core logic, actor interactions, temperature limits/hysteresis, configuration persistence, midnight wrap-arounds, and locale parity must have comprehensive unit test coverage.
  - Automated tests for UI rendering are not mandatory, but lightweight tests that verify backend service synchronization, state calculations, or setting persistence (e.g. `test/test_settings.py`) are encouraged.
