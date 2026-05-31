#!/usr/bin/env bash
# Finalize gstack: ensure Playwright Chromium works, then re-run ./setup.
exec > "$HOME/Documents/miraheze-local/gstack-retry-output.log" 2>&1
export PATH="/c/Program Files/nodejs:/c/Users/danny/.bun/bin:$PATH"
cd "$HOME/.claude/skills/gstack" || { echo "cd failed"; exit 1; }

launch_test() {
  node -e "const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();await b.close();console.log('CHROMIUM_OK');})().catch(e=>{console.error('CHROMIUM_FAIL:'+e.message);process.exit(1);})"
}

echo "=== test 1: does Chromium already launch? ==="
if launch_test; then
  echo "Chromium works after first install."
else
  echo "=== Chromium not launchable yet; retrying install ==="
  # Pure-Node playwright CLI is more reliable on Windows than bunx for this step.
  node node_modules/playwright-core/cli.js install chromium \
    || npx --yes playwright install chromium \
    || bunx playwright install chromium
  echo "=== test 2: launch after reinstall ==="
  launch_test || echo "STILL_FAILING"
fi

echo "=== re-running ./setup --no-prefix to finalize linking ==="
./setup --no-prefix
echo "=== FINAL SETUP EXIT=$? ==="
