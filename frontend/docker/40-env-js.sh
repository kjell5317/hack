#!/bin/sh
# Writes runtime config for the SPA so one image works in every environment.
# Only put public values here: everything ends up in the browser.
set -eu
cat > /usr/share/nginx/html/env.js <<JS
window.__ENV__ = {
  SUPABASE_URL: "${SUPABASE_URL:-}",
  SUPABASE_PUBLISHABLE_KEY: "${SUPABASE_PUBLISHABLE_KEY:-}"
}
JS
