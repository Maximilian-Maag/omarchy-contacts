# Changelog

All notable changes to omarchy-contacts are documented here.

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
