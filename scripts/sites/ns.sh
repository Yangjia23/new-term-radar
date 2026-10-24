#!/bin/sh
# Prints the domain when its Cloudflare NS pair is the one asked for: ns.sh <domain> <ns1> <ns2>
#   cat cands.txt | xargs -P 16 -I{} scripts/sites/ns.sh {} grant audrey
# Keep the concurrency low: at -P 64 lookups fail silently (see docs/competitor-sites.md).
ns=$(dig +short +time=5 +tries=3 NS "$1" @1.1.1.1 | tr '\n' ' ')
case "$ns" in *"$2.ns.cloudflare"*"$3.ns.cloudflare"*|*"$3.ns.cloudflare"*"$2.ns.cloudflare"*) echo "$1";; esac
