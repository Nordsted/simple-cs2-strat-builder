# Strategy seed files

Each map has its own JSON file in this folder.

## Structure

```json
{
  "mapSlug": "mirage",
  "mapName": "Mirage",
  "strategies": [
    {
      "side": "T",
      "name": "Strategy name",
      "description": "What the strat does.",
      "creator": "System",
      "bindings": {
        "1": "say_team Example call"
      }
    }
  ]
}
```

## Why this helps maintenance

- Add or edit strats for a single map without touching backend code.
- Keep Mirage, Inferno, Ancient, and future maps isolated in separate files.
- Seed data stays readable and versionable in git.

These files are loaded into SQLite automatically on first startup when the database is empty.
