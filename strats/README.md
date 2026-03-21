# Strategy seed files

Each map keeps its canonical ordered strategy list in its own JSON file.

## Supported schema

```json
{
  "mapSlug": "mirage",
  "mapName": "Mirage",
  "strategies": [
    {
      "side": "T",
      "name": "Mid control",
      "description": "Take mid and split connector.",
      "message": "smoke window and take connector",
      "creator": "System",
      "meta": {
        "pace": "default",
        "utility": ["smoke", "flash"]
      }
    }
  ]
}
```

## Rules

- `mapSlug`, `mapName`, and `strategies` are required at the file level.
- Every strategy must include `side`, `name`, `description`, and `message`.
- `creator` is optional and defaults in the application when omitted.
- `meta` is optional and must be a JSON object when present.
- `message` is the only persisted team-chat payload. Do not add `bindings`, slot numbers, or any slot-specific keys.
- Strategy order is meaningful. The UI filters by map + side, then auto-fills numpad slots 1-9 from the first nine strategies in that ordered list.

## Why this format is canonical

- It keeps persistence message-first instead of slot-first.
- It makes ordered strategies reusable across the slim list UI and the picker dialog.
- It keeps metadata attached to strategies without coupling the file format to numpad slots.

These files are loaded into SQLite automatically on first startup when the database is empty.
