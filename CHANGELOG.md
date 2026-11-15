# Changelog

All notable changes to omarchy-contacts are documented here.

## [Unreleased]

### Fixed
- **CardDAV push lie: an existing contact was never updated** (#3). `sync_push` sent
  every vCard with `If-None-Match: *` (create-only) and counted the server's `412`
  refusal as success, so re-pushing an edited contact left the server stale while
  printing success. A `412` now triggers a real update PUT without the create-only
  header, and only `200`/`201`/`204` count as a push.
- **Quoted vCard parameter values were re-emitted unquoted** (#4). A value like
  `TYPE="a,b"` was written back as `TYPE=a;TYPE=b` and split into two parameters on the
  next parse. `serialize_property` now quotes any value containing `,` `;` `:` or
  whitespace, and `parse_line` keeps a quoted value as a single value.
- **`default_collection` was unreachable** (#5). `save_config` had no caller, so the
  default collection could never be persisted through the tool. Added a
  `default [name]` command that shows or sets (and saves) `default_collection`.

## [0.1.3] — 2026-10-28

### Fixed
- **The applied theme name came from a stale hook stamp** (#2). `applied_theme_name()`
  preferred the theme-set hook's stamp over Omarchy's authoritative
  `<state>/omarchy/current/theme.name`. Resolution is now: `current/theme.name` → colour
  match → hook stamp, with tests for the precedence.

## [0.1.2] — 2026-10-28

### Fixed
- **The theme-set hook stamped `active-theme` into a file nothing read** (#1, second half).
  The `theme` command now names the applied theme, preferring the hook's recorded value and
  falling back to matching the applied colours against the installed theme dirs, so the
  stamp is finally consumed. New unit + integration tests cover the recorded-wins,
  colour-match and JSON-`name` paths.

## [0.1.1] — 2026-10-28

### Fixed
- **The theme-set hook shipped under the bare basename `theme-set`** (#1), which
  omarchy-thunderbird / -keepassxc / -qutebrowser also use — `omarchy hook install` copies
  to the file's basename, so four plugins fought over
  `~/.config/omarchy/hooks/theme-set.d/theme-set` and only the last installed survived.
  Renamed to `hooks/contacts-theme-set`.

## [0.1.0] — 2026-10-11

### Added
- **Keyboard editor.** `omarchy-contacts tui` opens a curses UI that browses,
  searches and edits *any* property of a contact — standard or `X-` — with the
  list on the left and every property of the selected contact on the right.
- **vdir store.** One `.vcf` per contact under
  `~/.local/share/omarchy-contacts/<collection>/`, the layout `vdirsyncer` and
  Nextcloud use, so the store is portable.
- **CardDAV client.** `omarchy-contacts sync --pull|--push` discovers the address
  books under a configured Nextcloud server (principal → home-set → collections)
  and pulls or pushes vCards.
- **CLI.** `list`, `show`, `set`, `unset`, `add`, `rm`, `import`, `export`,
  `collections`, `theme`.
- **Theme-aware.** Colours come from the applied Omarchy theme's `colors.toml`,
  read live, so every theme works with no per-theme code.
- **Hyprland keybinding** — `Super+Shift+Alt+A` opens the editor.
- Full test harness: unit, regression, integration, e2e, shell and mutation
  kinds, all run from `make test` (or `tools/run_tests.sh`), plus policy as code.
