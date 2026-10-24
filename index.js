import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

/*
 * The skills in skills/<name>/, installed into <novaHome>/skills as bundled skills
 * (NOVA_HOME.md, "Bundled skills"): read-only, marked with .nova-bundled.json, and
 * reinstalled when this package is newer or the installed copy was edited. Every Nova
 * app carries this package and calls installSkills at start-up; the newest one wins.
 * A skill folder without our marker is the user's own and is never touched.
 */

export const BUNDLE_FILE = '.nova-bundled.json';
export const BUNDLED_BY = 'Nova AI Skills';
/** The skills folder of this package. */
export const SKILLS_DIR = fileURLToPath(new URL('./skills/', import.meta.url));
export const VERSION = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')).version;

/** Apps that installed these skills before this package existed; their copies are taken over. */
const FORMER_OWNERS = ['Nova AI for VS Code'];
/** Skills an earlier version shipped under another name; removed when they are ours. */
const RETIRED_SKILLS = ['nova-documents'];

/** Every file below a folder, relative with `/` separators, sorted; the marker file and Python caches are left out. */
async function listFiles(root, folder = '') {
    const entries = await fs.readdir(path.join(root, folder), { withFileTypes: true }).catch(() => []);
    const files = [];
    for (const entry of entries) {
        const relative = folder ? `${folder}/${entry.name}` : entry.name;
        if (entry.isDirectory()) {
            // Python writes __pycache__ next to scripts it imports: not part of the skill.
            if (entry.name !== '__pycache__') files.push(...await listFiles(root, relative));
        } else if (entry.isFile() && entry.name !== BUNDLE_FILE) {
            files.push(relative);
        }
    }
    return files.sort();
}

/** SHA-256 over the names and contents of a skill's files. */
export async function hashSkill(root) {
    const hash = createHash('sha256');
    for (const file of await listFiles(root)) {
        hash.update(`${file}\0`);
        hash.update(await fs.readFile(path.join(root, file)));
        hash.update('\0');
    }
    return hash.digest('hex');
}

async function readMarker(folder) {
    try {
        return JSON.parse(await fs.readFile(path.join(folder, BUNDLE_FILE), 'utf8'));
    } catch {
        return undefined;
    }
}

const ours = (marker) => marker?.bundledBy === BUNDLED_BY || FORMER_OWNERS.includes(marker?.bundledBy);

/** Compares two semver versions; a prerelease sorts before its release. */
export function compareVersions(a, b) {
    const [coreA, preA] = String(a).split('-', 2);
    const [coreB, preB] = String(b).split('-', 2);
    const partsA = coreA.split('.').map(Number);
    const partsB = coreB.split('.').map(Number);
    for (let i = 0; i < 3; i++) {
        const diff = (partsA[i] || 0) - (partsB[i] || 0);
        if (diff) return Math.sign(diff);
    }
    if (preA === preB) return 0;
    if (preA === undefined) return 1;
    if (preB === undefined) return -1;
    // ponytail: numeric-aware string compare, not the full semver prerelease rules; fine for alpha.N / beta.N.
    return Math.sign(preA.localeCompare(preB, 'en', { numeric: true }));
}

async function copySkill(from, to) {
    await fs.rm(to, { recursive: true, force: true });
    for (const file of await listFiles(from)) {
        const target = path.join(to, ...file.split('/'));
        await fs.mkdir(path.dirname(target), { recursive: true });
        await fs.copyFile(path.join(from, ...file.split('/')), target);
        await fs.chmod(target, file.endsWith('.py') ? 0o555 : 0o444).catch(() => undefined);
    }
}

/**
 * Installs or updates the skills under `<novaHome>/skills`. Returns the names it (re)installed.
 * A copy installed by a newer version is left alone, as is one of this version that nobody edited.
 * `sourceDir` and `version` are for tests.
 */
export async function installSkills(novaHome, { sourceDir = SKILLS_DIR, version = VERSION } = {}) {
    const installed = [];
    for (const name of RETIRED_SKILLS) {
        const old = path.join(novaHome, 'skills', name);
        if (ours(await readMarker(old))) await fs.rm(old, { recursive: true, force: true });
    }
    const sources = await fs.readdir(sourceDir, { withFileTypes: true }).catch(() => []);
    for (const source of sources) {
        const from = path.join(sourceDir, source.name);
        if (!source.isDirectory() || !(await fs.stat(path.join(from, 'SKILL.md')).catch(() => undefined))) continue;
        const to = path.join(novaHome, 'skills', source.name);
        if (await fs.stat(to).catch(() => undefined)) {
            const marker = await readMarker(to);
            if (!ours(marker)) continue;
            if (marker.bundledBy === BUNDLED_BY) {
                const order = compareVersions(marker.version, version);
                const edited = (await hashSkill(to)) !== marker.hash;
                // A newer copy is updated by the app that carries the newer package.
                if (order > 0 || (order === 0 && !edited)) continue;
            }
        }
        await copySkill(from, to);
        const hash = await hashSkill(to);
        await fs.writeFile(path.join(to, BUNDLE_FILE), `${JSON.stringify({ bundledBy: BUNDLED_BY, version, hash }, null, 2)}\n`, { mode: 0o444 });
        installed.push(source.name);
    }
    return installed;
}
