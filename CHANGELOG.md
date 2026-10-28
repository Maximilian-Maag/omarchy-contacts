# Changelog

All notable changes to omarchy-contacts are documented here.

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
