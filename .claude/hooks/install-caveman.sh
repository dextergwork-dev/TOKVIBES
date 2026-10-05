#!/bin/bash
set -u
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
command -v caveman >/dev/null 2>&1 || npm install -g @caveman-ai/cli >/dev/null 2>&1
[ -x /root/.caveman/bin/caveman-proxy ] || caveman setup --install >/dev/null 2>&1
npx -y skills add JuliusBrussee/caveman -g >/dev/null 2>&1
exit 0
