#!/bin/sh
# Runs as root so it can fix ownership of the bind-mounted /data volume to
# match PUID/PGID (Unraid default: 99/100, "nobody:users"), then drops
# privileges to that user before exec'ing the real process. If the image is
# somehow started as a non-root user already, it just execs directly.
set -e

PUID="${PUID:-99}"
PGID="${PGID:-100}"

if [ "$(id -u)" = "0" ]; then
    groupmod -o -g "$PGID" odo 2>/dev/null || groupadd -o -g "$PGID" odo
    usermod -o -u "$PUID" -g "$PGID" odo 2>/dev/null || useradd -o -u "$PUID" -g "$PGID" -d /app -s /sbin/nologin odo

    mkdir -p /data/photos /data/thumbnails
    chown -R "$PUID:$PGID" /data

    # `su`'s handling of extra positional args after the username varies by
    # implementation, so the command is joined into a single string instead
    # of relying on that -- reliable everywhere, and fine here since none of
    # our launch args (see Dockerfile CMD) contain spaces needing escaping.
    exec su -s /bin/sh -c "$*" odo
fi

exec "$@"
