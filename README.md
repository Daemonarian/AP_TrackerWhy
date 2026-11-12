# Universal Tracker - Why Addon (`tracker_why.apworld`)

An addon `.apworld` for [Universal Tracker](https://github.com/FarisTheAncient/Archipelago/releases?q=Tracker) that adds the `/why` command to diagnose out-of-logic locations.

## Usage

While connected to a room in Universal Tracker, run:

```text
/why <location_name>
```

Supports exact names, case-insensitive substrings, and fuzzy matching. The solver determines the minimal set(s) of additional progression items required to bring the target location into logic, identifying strict bottlenecks as well as alternative `OR` paths.

## Installation

1. Download `tracker_why.apworld` from the latest release (or zip the `tracker_why/` folder into `tracker_why.apworld`).
2. Place `tracker_why.apworld` into your Archipelago `custom_worlds/` folder alongside `tracker.apworld`.