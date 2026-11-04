#!/bin/sh
set -eu

server_bin="${FEAR_SERVER_BIN:-FEAR/fearserver.bin}"
case "$server_bin" in
    /*) ;;
    *) server_bin="/server/$server_bin" ;;
esac
if [ ! -x "$server_bin" ]; then
    echo "Brak pliku wykonywalnego serwera: $server_bin" >&2
    echo "Przygotuj Linux Dedicated Server w ./server/FEAR; zobacz README.md." >&2
    exit 1
fi
cd "$(dirname "$server_bin")"
server_name="$(basename "$server_bin")"
export LD_LIBRARY_PATH="$PWD${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "./$server_name" "$@"
