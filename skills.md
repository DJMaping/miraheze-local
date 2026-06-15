# Skills

Available skills in this environment, invoked by typing `/<skill-name>` (or via the Skill tool).

## Project-specific

- **graphify** — Turn any input (code, docs, papers, images, videos) into a persistent knowledge graph with god nodes, community detection, and query/path/explain tools. Use for any question about the wiki's content, structure, or how articles interrelate (this project has a generated graph in `graphify-out/`).

## Research & writing

- **deep-research** — Fan-out web searches, fetch sources, adversarially verify claims, synthesise a cited report.
- **humanizer** — Remove signs of AI-generated writing (em-dash overuse, rule of three, filler, inflated symbolism). Based on Wikipedia's "Signs of AI writing" guide.
- **caveman** — Ultra-compressed communication mode; cuts token usage ~75%.
- **make-pdf** — Turn any markdown file into a publication-quality PDF.
- **document-generate** — Generate missing documentation for a feature, module, or whole project.
- **document-release** — Post-ship documentation update.

## Code review & quality

- **code-review** — Review the current diff for bugs and cleanups at a given effort level (low → ultra). `--comment` posts inline PR comments; `--fix` applies fixes.
- **simplify** — Quality-only review (reuse, simplification, efficiency, altitude) that applies fixes; does not hunt for bugs.
- **review** — Pre-landing PR review.
- **security-review** — Security review of pending changes on the current branch.
- **vibesec** — Write secure web applications; run a scan or audit.
- **health** — Code quality dashboard.
- **investigate** — Systematic debugging with root-cause investigation.
- **verify** — Run the app and observe behaviour to confirm a change works.
- **tdd** — Test-driven development with red-green-refactor loop.

## Planning

- **grill-me** — Interview relentlessly about a plan or design until shared understanding.
- **grill-with-docs** — Grill a plan against the existing domain model and update docs inline.
- **spec** — Turn vague intent into a precise, executable spec in five phases.
- **plan-ceo-review** / **plan-eng-review** / **plan-design-review** / **plan-devex-review** — Role-based plan reviews.

## Design & frontend

- **frontend-design** — Distinctive, production-grade frontend interfaces.
- **design-consultation** — Research the landscape and propose a complete design system.
- **design-review** — Designer's-eye QA: visual inconsistency, spacing, hierarchy, AI slop.
- **design-html** / **design-shotgun** — Finalise HTML/CSS or generate multiple AI design variants.
- **ui-ux-pro-max** — UI/UX design intelligence for web and mobile (styles, palettes, font pairings).
- **web-design-guidelines** — Review UI code against Web Interface Guidelines (accessibility, UX).

## Browser & QA

- **agent-browser** — Browser automation: navigate, fill forms, click, screenshot, scrape, test web/Electron apps.
- **browse** / **gstack** — Fast headless browser for QA and dogfooding.
- **qa** / **qa-only** — Systematic web-app QA (with or without fixes).
- **scrape** — Pull data from a web page.

## Workflow & ops

- **ship** — Detect base branch, run tests, review diff, bump version, update changelog, commit, push, create PR.
- **land-and-deploy** — Land and deploy workflow.
- **canary** — Post-deploy canary monitoring.
- **loop** — Run a prompt or slash command on a recurring interval.
- **schedule** — Create/manage scheduled cloud agents (cron routines).
- **retro** — Weekly engineering retrospective.
- **learn** — Manage project learnings.

## Discovery & config

- **find-skills** — Discover and install agent skills.
- **update-config** — Configure the Claude Code harness via settings.json (hooks, permissions, env vars).
- **keybindings-help** — Customise keyboard shortcuts.
- **init** — Initialise a new CLAUDE.md with codebase documentation.

> This is a curated subset. Many additional skills (gstack suite, iOS tooling, Azure/Foundry deployment, Figma/Spotify/Gmail integrations) are available; type `/` to browse the full list.
