import assert from 'node:assert/strict';
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';
import { BUNDLE_FILE, BUNDLED_BY, SKILLS_DIR, compareVersions, installSkills } from '../index.js';

let base;
let source;
let novaHome;

const writeSkill = (name, body) => {
    mkdirSync(join(source, name, 'scripts'), { recursive: true });
    writeFileSync(join(source, name, 'SKILL.md'), `---\nname: ${name}\ndescription: Reads files.\n---\n${body}`);
    writeFileSync(join(source, name, 'scripts', 'read.py'), 'print(1)\n');
};
const install = (version) => installSkills(novaHome, { sourceDir: source, version });
const marker = (name) => JSON.parse(readFileSync(join(novaHome, 'skills', name, BUNDLE_FILE), 'utf8'));
const skillFile = () => join(novaHome, 'skills', 'sample-docs', 'SKILL.md');

beforeEach(() => {
    base = mkdtempSync(join(tmpdir(), 'nova-skills-install-'));
    source = join(base, 'source');
    novaHome = join(base, '.nova-ai');
    mkdirSync(source, { recursive: true });
    writeSkill('sample-docs', 'v1');
});

afterEach(() => rmSync(base, { recursive: true, force: true }));

describe('installSkills', () => {
    it('installs a skill as a bundled one and leaves a current one alone', async () => {
        assert.deepEqual(await install('1.0.0'), ['sample-docs']);
        assert.equal(readFileSync(join(novaHome, 'skills', 'sample-docs', 'scripts', 'read.py'), 'utf8'), 'print(1)\n');
        assert.equal(marker('sample-docs').bundledBy, BUNDLED_BY);
        assert.equal(marker('sample-docs').version, '1.0.0');
        assert.match(marker('sample-docs').hash, /^[0-9a-f]{64}$/);
        assert.deepEqual(await install('1.0.0'), []);
    });

    it('updates to a newer version, repairs an edited copy, and never downgrades', async () => {
        await install('1.0.0');
        writeSkill('sample-docs', 'v2');
        assert.deepEqual(await install('1.1.0'), ['sample-docs']);
        assert.match(readFileSync(skillFile(), 'utf8'), /v2/);

        chmodSync(skillFile(), 0o644);
        writeFileSync(skillFile(), 'edited');
        assert.deepEqual(await install('1.1.0'), ['sample-docs']);
        assert.match(readFileSync(skillFile(), 'utf8'), /v2/);

        // An app carrying an older package leaves the newer copy alone.
        writeSkill('sample-docs', 'v1');
        assert.deepEqual(await install('1.0.0'), []);
        assert.match(readFileSync(skillFile(), 'utf8'), /v2/);
    });

    it('takes over a copy the VS Code extension installed', async () => {
        const old = join(novaHome, 'skills', 'sample-docs');
        mkdirSync(old, { recursive: true });
        writeFileSync(join(old, 'SKILL.md'), 'old');
        writeFileSync(join(old, BUNDLE_FILE), JSON.stringify({ bundledBy: 'Nova AI for VS Code', version: '1.0.24', hash: 'x' }));
        assert.deepEqual(await install('0.1.0'), ['sample-docs']);
        assert.equal(marker('sample-docs').bundledBy, BUNDLED_BY);
    });

    it('never touches a skill folder of the same name that is not ours', async () => {
        const own = join(novaHome, 'skills', 'sample-docs');
        mkdirSync(own, { recursive: true });
        writeFileSync(join(own, 'SKILL.md'), 'mine');
        assert.deepEqual(await install('1.0.0'), []);
        assert.equal(readFileSync(join(own, 'SKILL.md'), 'utf8'), 'mine');
        assert.equal(existsSync(join(own, BUNDLE_FILE)), false);
    });

    it('is not fooled by Python caches the scripts leave behind', async () => {
        await install('1.0.0');
        const cache = join(novaHome, 'skills', 'sample-docs', 'scripts', '__pycache__');
        mkdirSync(cache, { recursive: true });
        writeFileSync(join(cache, 'read.cpython-314.pyc'), 'x');
        assert.deepEqual(await install('1.0.0'), []);
    });

    it('removes a retired skill of ours but not one of the user', async () => {
        const old = join(novaHome, 'skills', 'nova-documents');
        mkdirSync(old, { recursive: true });
        writeFileSync(join(old, 'SKILL.md'), 'old');
        writeFileSync(join(old, BUNDLE_FILE), JSON.stringify({ bundledBy: 'Nova AI for VS Code', version: '1.0.0', hash: 'x' }));
        await install('1.1.0');
        assert.equal(existsSync(old), false);

        mkdirSync(old, { recursive: true });
        writeFileSync(join(old, 'SKILL.md'), 'mine');
        await install('1.1.0');
        assert.equal(existsSync(join(old, 'SKILL.md')), true);
    });

    it('ships a skill per document format, each with a reader, the environment helper and how-tos', async () => {
        assert.deepEqual((await installSkills(novaHome)).sort(), ['nova-docx', 'nova-pdf', 'nova-pptx', 'nova-xlsx']);
        const scripts = {
            'nova-docx': ['docx_text.py', 'docx_review.py', 'docx_review_edit.py', 'docx_diff.py', 'office_meta.py', 'textdiff.py'],
            'nova-xlsx': ['xlsx_dump.py', 'xlsx_comments.py', 'xlsx_threads_edit.py', 'xlsx_diff.py', 'office_meta.py', 'textdiff.py'],
            'nova-pptx': ['pptx_text.py', 'pptx_comments.py', 'pptx_comments_edit.py', 'pptx_diff.py', 'office_meta.py', 'textdiff.py'],
            'nova-pdf': ['pdf_text.py', 'pdf_review.py', 'pdf_annots_edit.py', 'pdf_diff.py', 'textdiff.py'],
        };
        const copy = (skill, file) => readFileSync(join(SKILLS_DIR, skill, 'scripts', file), 'utf8');
        for (const [name, files] of Object.entries(scripts)) {
            for (const file of ['SKILL.md', 'scripts/ensure_env.py', 'references/create.md', 'references/edit.md', 'references/review.md', ...files.map((script) => `scripts/${script}`)]) {
                assert.ok(existsSync(join(novaHome, 'skills', name, file)), `${name}/${file}`);
            }
            // Skills are self-contained, so shared helpers are copied into each: the copies must not drift.
            for (const shared of ['ensure_env.py', 'textdiff.py', 'office_meta.py']) {
                if (existsSync(join(SKILLS_DIR, name, 'scripts', shared))) {
                    assert.equal(copy(name, shared), copy('nova-xlsx', shared), `${name}/${shared}`);
                }
            }
            const description = /^description: (.+)$/m.exec(readFileSync(join(SKILLS_DIR, name, 'SKILL.md'), 'utf8'))?.[1] ?? '';
            assert.ok(description.length > 0 && description.length <= 200, `${name} description`);
        }
    });
});

it('compareVersions orders releases and prereleases', () => {
    assert.equal(compareVersions('1.2.0', '1.10.0'), -1);
    assert.equal(compareVersions('1.0.0', '1.0.0-alpha.3'), 1);
    assert.equal(compareVersions('1.0.0-alpha.10', '1.0.0-alpha.9'), 1);
    assert.equal(compareVersions('1.0.0', '1.0.0'), 0);
});

it('loads in a CommonJS bundle, where import.meta is empty', async () => {
    const { buildSync } = await import('esbuild');
    const out = join(mkdtempSync(join(tmpdir(), 'nova-skills-cjs-')), 'bundle.cjs');
    buildSync({ entryPoints: [fileURLToPath(new URL('../index.js', import.meta.url))], bundle: true, platform: 'node', format: 'cjs', outfile: out, logLevel: 'silent' });
    const { createRequire } = await import('node:module');
    const bundled = createRequire(import.meta.url)(out);
    assert.equal(bundled.SKILLS_DIR, undefined);
    await assert.rejects(bundled.installSkills(join(tmpdir(), 'unused')), /needs sourceDir and version/);
});
