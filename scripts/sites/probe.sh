#!/bin/sh
# Prints the IDs a site's public config gives away (Google OAuth project, GA, Clarity, Plausible)
# and the hash of its favicon.svg:
#   cat live.txt | xargs -P 64 -n 1 scripts/sites/probe.sh
r=$(curl -s -m 8 -A "Mozilla/5.0" "https://$1/api/config/public" 2>/dev/null | head -c 3000)
case "$r" in *app_name*)
  icon=$(curl -s -m 8 -A "Mozilla/5.0" "https://$1/favicon.svg" | shasum -a 256 | cut -c1-16)
  echo "$1 favicon.svg:$icon $(echo "$r" | grep -o -E '"(app_name|google_client_id|google_analytics_id|clarity_project_id|plausible[a-z_]*)":"[^"]*"' | tr '\n' ' ')";; esac
