# Nova AI skills

The skills every Nova AI app ships, and the installer that keeps them up to date.

| Skill | For |
|---|---|
| `nova-docx` | Word documents: read, create, edit, comments, tracked changes, diffs |
| `nova-xlsx` | Excel workbooks: data, formulas, charts, notes and comments, diffs |
| `nova-pptx` | PowerPoint decks: slides, charts, speaker notes, comments, diffs |
| `nova-pdf` | PDFs: text, merge, split, forms, annotations, diffs, new PDFs |

The scripts need Python 3. `scripts/ensure_env.py` installs the libraries they
use into Nova's own environment (`~/.nova-ai/python-env`), never the system
Python; that needs the internet the first time.

## Using it in a Nova app

```js
import { installSkills } from '@datalabrotterdam/nova-ai-skills';

// At start-up; novaHome is ~/.nova-ai unless NOVA_AI_HOME is set.
const installed = await installSkills(novaHome);
```

The skills are installed into `<novaHome>/skills` as *bundled* skills
(NOVA_HOME.md, "Bundled skills"): read-only, with a `.nova-bundled.json` marker
(`"bundledBy": "Nova AI Skills"`). Every app that carries this package runs the
same installer, so the newest package wins:

- A missing skill is installed.
- A copy from an older version, or one that was edited, is reinstalled.
- A copy from a newer version is left alone; the app with the newer package updates it.
- A folder without our marker is the user's and is never touched. Copies the
  VS Code extension installed before this package existed are taken over.
- Switching a skill off (`skills.disabled` in the settings) survives updates.

## Releasing

Conventional commits on `main` (stable) and `alpha` (prerelease) are released to
npm by semantic-release. A change to a skill is a `feat:` or `fix:` like any other,
so the apps pick it up with their next dependency update.
