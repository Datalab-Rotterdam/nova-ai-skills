import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { embedded } from './embedded.js';

/*
 * The skills in skills/<name>/, installed into <novaHome>/skills as bundled skills
 * (NOVA_HOME.md, "Bundled skills"): read-only, marked with .nova-bundled.json, and
 * reinstalled when this package is newer or the installed copy was edited. Every Nova
 * app carries this package and calls installSkills at start-up; the newest one wins.
 * A skill folder without our marker is the user's own and is never touched.
 *
 * Optional skills (OPTIONAL_SKILLS) are only installed for an app that asks for them, such as
 * nova-browser while the app has Nova AI Browser switched on, and removed with removeSkills.
 */

export const BUNDLE_FILE = '.nova-bundled.json';
export const BUNDLED_BY = 'Nova AI Skills';
// A bundler that turns this into CommonJS (esbuild for a VS Code extension) leaves import.meta empty,
// and an app compiled into one executable (Bun) has no skills/ or package.json on disk. Then the
// copies in embedded.js (scripts/embed.mjs) are installed.
const base = typeof import.meta.url === 'string' ? import.meta.url : undefined;
/** The skills folder of this package; undefined when bundled. */
export const SKILLS_DIR = base && fileURLToPath(new URL('./skills/', base));

function ownVersion() {
    try {
        return base && JSON.parse(readFileSync(new URL('./package.json', base), 'utf8')).version;
    } catch {
        return undefined;
    }
}
/** This package's version. */
export const VERSION = ownVersion() ?? embedded.version;

/** Skills only installed for apps that ask for them (`include`), such as nova-browser. */
export const OPTIONAL_SKILLS = ['nova-browser'];

/** Apps that installed these skills before this package existed; their copies are taken over. */
const FORMER_OWNERS = ['Nova AI for VS Code', 'Nova AI Browser'];
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

/** The skills in a folder: each with its files and a way to read them. */
async function skillsFromFolder(dir) {
    const skills = [];
    for (const entry of await fs.readdir(dir, { withFileTypes: true }).catch(() => [])) {
        const from = path.join(dir, entry.name);
        if (!entry.isDirectory() || !(await fs.stat(path.join(from, 'SKILL.md')).catch(() => undefined))) continue;
        const files = (await listFiles(from)).map((file) => ({ file, read: () => fs.readFile(path.join(from, ...file.split('/'))) }));
        skills.push({ name: entry.name, files });
    }
    return skills;
}

/** The skills in embedded.js. */
function embeddedSkills() {
    const skills = new Map();
    for (const [name, content] of Object.entries(embedded.files)) {
        const [skill, ...rest] = name.split('/');
        const data = typeof content === 'string' ? Buffer.from(content, 'utf8') : Buffer.from(content.base64, 'base64');
        if (!skills.has(skill)) skills.set(skill, []);
        skills.get(skill).push({ file: rest.join('/'), read: async () => data });
    }
    return [...skills].filter(([, files]) => files.some(({ file }) => file === 'SKILL.md')).map(([name, files]) => ({ name, files }));
}

/**
 * Removes a skill folder. Former owners locked their folders too (the browser host made them
 * 0555), and a folder's entries cannot be removed while it is read-only: unlock them first.
 */
async function removeFolder(folder) {
    const unlock = async (dir) => {
        await fs.chmod(dir, 0o755).catch(() => undefined);
        for (const entry of await fs.readdir(dir, { withFileTypes: true }).catch(() => [])) {
            if (entry.isDirectory()) await unlock(path.join(dir, entry.name));
        }
    };
    await unlock(folder);
    await fs.rm(folder, { recursive: true, force: true });
}

async function copySkill(skill, to) {
    await removeFolder(to);
    for (const { file, read } of skill.files) {
        const target = path.join(to, ...file.split('/'));
        await fs.mkdir(path.dirname(target), { recursive: true });
        await fs.writeFile(target, await read());
        // Read-only, scripts runnable (Python scripts and nova-browser's launchers).
        await fs.chmod(target, file.startsWith('scripts/') ? 0o555 : 0o444).catch(() => undefined);
    }
}

/**
 * Installs or updates the skills under `<novaHome>/skills`. Returns the names it (re)installed.
 * A copy installed by a newer version is left alone, as is one of this version that nobody edited.
 * Optional skills are installed only when `include` names them; a copy that is there already is
 * left as it is otherwise (another app may use it). `sourceDir` and `version` are for tests and
 * for apps that ship the skills folder themselves.
 */
export async function installSkills(novaHome, { sourceDir, version = VERSION, include = [] } = {}) {
    const folder = sourceDir ?? (SKILLS_DIR && existsSync(SKILLS_DIR) ? SKILLS_DIR : undefined);
    const skills = folder ? await skillsFromFolder(folder) : embeddedSkills();
    const installed = [];
    for (const name of RETIRED_SKILLS) {
        const old = path.join(novaHome, 'skills', name);
        if (ours(await readMarker(old))) await removeFolder(old);
    }
    for (const skill of skills) {
        if (OPTIONAL_SKILLS.includes(skill.name) && !include.includes(skill.name)) continue;
        const to = path.join(novaHome, 'skills', skill.name);
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
        await copySkill(skill, to);
        const hash = await hashSkill(to);
        await fs.writeFile(path.join(to, BUNDLE_FILE), `${JSON.stringify({ bundledBy: BUNDLED_BY, version, hash }, null, 2)}\n`, { mode: 0o444 });
        installed.push(skill.name);
    }
    return installed;
}

/**
 * Removes skills this package (or a former owner) installed, such as nova-browser when the app
 * switches Nova AI Browser off. A folder without our marker is never touched. Returns the names removed.
 */
export async function removeSkills(novaHome, names) {
    const removed = [];
    for (const name of names) {
        const folder = path.join(novaHome, 'skills', name);
        if (!ours(await readMarker(folder))) continue;
        await removeFolder(folder);
        removed.push(name);
    }
    return removed;
}
