# family-health-archive

![family-health-archive cover](assets/cover.svg)

[![License: AGPL-3.0-or-later](https://img.shields.io/badge/license-AGPL--3.0--or--later-1f6f5f.svg)](LICENSE)
[![OpenClaw Skills](https://img.shields.io/badge/OpenClaw-2%20skills-2f8f6b.svg)](skills/README.md)
[![Local First](https://img.shields.io/badge/Local-First-e8f5ef.svg)](#overview)

OpenClaw skills for local-first family health archiving and analysis.

GitHub is the source repository. Recommended installation should happen through a skill platform; manual copy into the OpenClaw `skills` directory remains available as a fallback.

## Included Skills

### `health-archive-manager`

Write-side skill for:

- initializing the archive
- creating or matching people
- checking upload quality
- blocking duplicates
- writing `documents` and `observations`

Entry:

- `skills/health-archive-manager/SKILL.md`

### `health-archive-assistant`

Read-side skill for:

- querying archived records
- generating analysis JSON
- building patient context
- generating summary results
- preparing chart specs

Entry:

- `skills/health-archive-assistant/SKILL.md`

## Install

Recommended:

- install from a skill platform

Fallback:

- copy the skill folder into the OpenClaw `skills` directory

OpenClaw loads skills from `<workspace>/skills` and `~/.openclaw/skills`.

Recommended order:

1. install `health-archive-manager`
2. install `health-archive-assistant`

Manual copy should result in:

```text
<workspace>/skills/health-archive-manager/SKILL.md
<workspace>/skills/health-archive-assistant/SKILL.md
```

Platform-specific install commands can be listed here when the skills are published.

## Repository Layout

```text
.
├─ skills/
│  ├─ health-archive-manager/
│  │  └─ SKILL.md
│  └─ health-archive-assistant/
│     └─ SKILL.md
├─ assets/
└─ DISCLAIMER.md
```

The repository root is for source code and documentation. OpenClaw installs the individual skill folders under `skills/`.

## Data Layout

Recommended data root:

- macOS / Linux: `~/.family-health-data/`
- Windows: `%USERPROFILE%\\.family-health-data\\`

```text
<data_root>/
  archive.db
  files/
```

- `archive.db`: structured archive data
- `files/`: original images, screenshots, PDFs, and other source files

## Skill Model

- `health-archive-manager` handles archive writes
- `health-archive-assistant` handles archive reads and analysis
- both skills share one local data root
- source files remain local

## Status

Implemented:

- local SQLite plus files archive
- people, documents, and observations schema
- archive result contract
- duplicate detection
- person matching and archive initialization
- analysis, context, summary, and chart-spec layers

## References

- `skills/README.md`
- `skills/health-archive-manager/references/schema.md`
- `skills/health-archive-manager/references/medical-archive-result.md`
- `skills/health-archive-manager/references/model-output-guidelines.md`
- `skills/health-archive-assistant/references/medical-analysis-result.md`
- `skills/health-archive-assistant/references/patient-context-result.md`
- `skills/health-archive-assistant/references/medical-summary-result.md`
- `skills/health-archive-assistant/references/display-guidelines.md`
- `skills/health-archive-assistant/references/chart-spec.md`

## License

`AGPL-3.0-or-later`

## Privacy And Security

This project is local-first, not risk-free.

See `DISCLAIMER.md` for the threat model and operational cautions.
