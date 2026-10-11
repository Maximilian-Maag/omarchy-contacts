-- Hyprland keybindings added by omarchy-contacts.
-- Sourced from hyprland.lua by install.sh (require("hypr.contacts-bindings")).
--
-- Super+Shift+Alt+A opens the keyboard editor in a floating terminal. The
-- org.omarchy.* app-id makes Omarchy auto-float the window.

hl.unbind("SUPER + SHIFT + ALT + A")
o.bind("SUPER + SHIFT + ALT + A", "Contacts",
       "xdg-terminal-exec --app-id=org.omarchy.contacts --title='Contacts' -- omarchy-contacts tui")
