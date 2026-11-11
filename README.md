# Nova AI skills

The skills every Nova AI app ships, and the installer that keeps them up to date.

| Skill | For |
|---|---|
| `nova-docx` | Word documents: read, create, edit, comments, tracked changes, diffs |
| `nova-xlsx` | Excel workbooks: data, formulas, charts, notes and comments, diffs |
| `nova-pptx` | PowerPoint decks: slides, charts, speaker notes, comments, diffs |
| `nova-pdf` | PDFs: text, merge, split, forms, annotations, diffs, new PDFs |
| `nova-browser` | The user's own browser through the Nova AI extension (optional, see below) |

The document scripts need Python 3. `scripts/ensure_env.py` installs the libraries they
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

The installer also works where this package is bundled or compiled into one executable
(a VS Code extension, Nova AI Desktop's sidecar): it then installs the copies in
`embedded.js`, which `npm run embed` writes and packing refreshes.

### Optional skills: nova-browser

`nova-browser` is only useful while the Nova AI Browser host is registered, so it is not
installed by default. An app installs it while it has the browser switched on, and removes it
when it switches it off:

```js
import { installSkills, removeSkills } from '@datalabrotterdam/nova-ai-skills';

await installSkills(novaHome, { include: ['nova-browser'] }); // browser on
await removeSkills(novaHome, ['nova-browser']);               // browser off, no host left
```

An app that does not ask for it leaves a copy another app installed alone. Its script runs the
host wrapper the apps register (`~/.nova-ai/browser/bin/nova-ai-browser-host`), whether that runs
Node or an app that carries the host, such as Nova AI Desktop.

## Releasing

Conventional commits on `main` (stable) and `alpha` (prerelease) are released to
npm by semantic-release. A change to a skill is a `feat:` or `fix:` like any other,
so the apps pick it up with their next dependency update.

## License

Copyright 2026 DataLab Rotterdam. The skills and the installer are licensed under
the [Apache License 2.0](LICENSE) and are free for public use: anyone may use,
copy, change and share them, also commercially and outside Nova AI, as long as
the license and the [NOTICE](NOTICE) are kept. Each skill carries its own
`LICENSE.txt` and `NOTICE`, so an installed copy stays licensed on its own.
