# omarchy-contacts

An [Omarchy](https://omarchy.org/) plugin that is a keyboard-driven address book:
a local store of vCards with a curses editor for every property of a person, and a
CardDAV client that syncs a Nextcloud address book.

## What it does

- **Keyboard editor** — `omarchy-contacts tui` browses, searches and edits a
  contact, and lets you add or remove *any* property (standard, structured, or
  `X-`) without a mouse.
- **Portable store** — one `.vcf` per contact under
  `~/.local/share/omarchy-contacts/<collection>/`, the same layout `vdirsyncer`
  and Nextcloud use.
- **CardDAV sync** — `omarchy-contacts sync --pull` / `--push` discovers the
  address books under a configured server and moves vCards both ways.
- **Theme-aware** — the UI is coloured from the *applied* Omarchy theme
  (`~/.local/state/omarchy/current/theme/colors.toml`), so all themes work with
  no per-theme code.
- **Keybinding** — `Super+Shift+Alt+A` opens the editor in a floating terminal.

## Requirements

- Omarchy, Python 3 (system interpreter). Nothing else — no pip packages.

## Installation

```bash
omarchy plugin add https://github.com/Maximilian-Maag/omarchy-contacts.git --enable
bash ~/.config/omarchy/plugins/Maximilian-Maag.contacts/install.sh
```

Or from a clone: `bash install.sh`.

## Usage

```bash
omarchy-contacts tui                       # the keyboard editor
omarchy-contacts add --fn "Ada Lovelace" --email ada@example.org
omarchy-contacts list --query ada          # search name/email/phone/org
omarchy-contacts show ada                  # every property
omarchy-contacts set ada ORG "Analytical Engines"
omarchy-contacts unset ada NOTE
omarchy-contacts rm ada
omarchy-contacts export ada > ada.vcf
omarchy-contacts import backup.vcf
omarchy-contacts theme --json              # the applied palette
omarchy-contacts --collection work list    # act on another collection
```

### Editing keys (TUI)

`j`/`k` move, `Enter` opens a contact, `e` sets a property, `a` adds one, `x`
removes one, `n` makes a new contact, `d` deletes, `/` filters, `q` quits.

## Nextcloud (CardDAV)

Add a server to `~/.config/omarchy-contacts/contacts.json`:

```json
{
  "default_collection": "personal",
  "servers": [
    {
      "name": "nextcloud",
      "url": "https://cloud.example.org/remote.php/dav",
      "username": "you",
      "password_env": "NEXTCLOUD_APP_PASSWORD"
    }
  ]
}
```

Then `omarchy-contacts sync --pull` (or `--push`). The password is read from
`password_env`, or a `password_file` you keep out of the config, never from the
config in plain text.

## Testing

```bash
make test      # policy -> unit -> regression -> integration -> e2e -> shell -> mutation
make check     # policy + unit + regression
```

## Licence

MIT.
