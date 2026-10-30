#!/bin/sh
# Runs the app as PUID:PGID (Unraid: 99:100) and makes sure /data belongs to that user.
set -e
if [ "$(id -u)" = "0" ]; then
    chown -R "${PUID}:${PGID}" "${DROPPER_DATA:-${PURPLERAIN_DATA:-/data}}"
    exec setpriv --reuid="${PUID}" --regid="${PGID}" --clear-groups "$@"
fi
exec "$@"
