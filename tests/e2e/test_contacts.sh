#!/bin/bash
# e2e: drive the shipped CLI through a full add → edit → export → import round
# trip against a throwaway store (never the user's address book).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLI="$ROOT/bin/omarchy-contacts"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

export XDG_DATA_HOME="$WORK/data"
export XDG_CONFIG_HOME="$WORK/cfg"
export XDG_STATE_HOME="$WORK/state"

fail() { echo "e2e: FAILED — $1" >&2; exit 1; }

UID_ADA="$("$CLI" add --fn 'Ada Lovelace' --email ada@example.org)"
[[ -n $UID_ADA ]] || fail "add produced no uid"

"$CLI" list | grep -q 'Ada Lovelace' || fail "list does not show the contact"

"$CLI" set "$UID_ADA" ORG 'Analytical Engines'
"$CLI" show "$UID_ADA" | grep -q 'ORG: Analytical Engines' || fail "set did not take"

"$CLI" export "$UID_ADA" > "$WORK/ada.vcf"
grep -q 'BEGIN:VCARD' "$WORK/ada.vcf" || fail "export wrote no vcard"

"$CLI" --collection work import "$WORK/ada.vcf" >/dev/null
WORK_COUNT="$("$CLI" --collection work list | grep -c 'Ada Lovelace')"
[[ $WORK_COUNT == "1" ]] || fail "import into another collection lost the contact (count=$WORK_COUNT)"

# the two collections are independent
HOME_COUNT="$("$CLI" list | grep -c 'Ada Lovelace')"
[[ $HOME_COUNT == "1" ]] || fail "collections are not isolated"

echo "e2e: ok — add/set/export/import round trip across two collections"
