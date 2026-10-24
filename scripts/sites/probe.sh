#!/bin/sh
# Prints the IDs a site's public config gives away (Google OAuth project, GA, Clarity, Plausible):
#   cat live.txt | xargs -P 64 -n 1 scripts/sites/probe.sh
r=$(curl -s -m 8 -A "Mozilla/5.0" "https://$1/api/config/public" 2>/dev/null | head -c 3000)
case "$r" in *app_name*) echo "$1 $(echo "$r" | grep -o -E '"(app_name|google_client_id|google_analytics_id|clarity_project_id|plausible[a-z_]*)":"[^"]*"' | tr '\n' ' ')";; esac
