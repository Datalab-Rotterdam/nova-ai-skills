import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';
import { BUNDLE_FILE, BUNDLED_BY, SKILLS_DIR, VERSION, compareVersions, installSkills, removeSkills } from '../index.js';

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
        assert.deepEqual((await installSkills(novaHome)).sort(), ['nova-docx', 'nova-ms-outlook', 'nova-ms-teams', 'nova-pdf', 'nova-pptx', 'nova-xlsx']);
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

describe('nova-ms-outlook', () => {
    const script = () => join(SKILLS_DIR, 'nova-ms-outlook', 'scripts', 'outlook.py');
    // Every e-mail and event ends with this line (LANG is English below), so AI-made is always visible.
    const MADE = 'Made%20by%3A%20Nova%20AI%20%28Datalab%20Rotterdam%29';
    const MADE_TWICE = MADE.replaceAll('%', '%25');
    const python = process.platform === 'win32' ? 'python' : 'python3';
    // NOVA_OUTLOOK_SIMULATE fakes the installed Outlook; --print never opens anything. UTC0 is a
    // zone both POSIX and the Windows C runtime read as UTC; no __pycache__ in the skill folder.
    const env = (simulate) => ({ ...process.env, NOVA_OUTLOOK_SIMULATE: simulate, TZ: 'UTC0', PYTHONDONTWRITEBYTECODE: '1', LANG: 'en_US.UTF-8', LC_ALL: '', LC_MESSAGES: '' });
    const run = (simulate, ...args) => JSON.parse(execFileSync(python, [script(), ...args, '--print'], { encoding: 'utf8', env: env(simulate) }));
    const fail = (simulate, ...args) => spawnSync(python, [script(), ...args, '--print'], { encoding: 'utf8', env: env(simulate) });
    // Runs the script as if opening the target failed, to see the error and the web fallback.
    const unopenable = (simulate, ...args) => {
        const code = 'import sys; sys.path.insert(0, sys.argv[1]); import outlook\n'
            + 'outlook.open_target = lambda *a: (False, "OSError: no handler")\n'
            + 'sys.exit(outlook.main(sys.argv[2:]))';
        const out = spawnSync(python, ['-c', code, join(SKILLS_DIR, 'nova-ms-outlook', 'scripts'), ...args], { encoding: 'utf8', env: env(simulate) });
        return { status: out.status, ...JSON.parse(out.stdout) };
    };

    it('is installed by default, with its script and routes', async () => {
        assert.ok((await installSkills(novaHome)).includes('nova-ms-outlook'));
        for (const file of ['SKILL.md', 'scripts/outlook.py', 'references/routes.md', 'LICENSE.txt', 'NOTICE']) {
            assert.ok(existsSync(join(novaHome, 'skills', 'nova-ms-outlook', file)), file);
        }
        const description = /^description: (.+)$/m.exec(readFileSync(join(SKILLS_DIR, 'nova-ms-outlook', 'SKILL.md'), 'utf8'))?.[1] ?? '';
        assert.ok(description.length > 0 && description.length <= 200, 'nova-ms-outlook description');
    });

    it('falls back to Outlook on the web without a desktop Outlook', () => {
        const event = run('none', 'event', '--subject', 'Sync & plan', '--start', '2026-11-20 10:00', '--end', '2026-11-20 11:00');
        assert.equal(event.route, 'web');
        assert.equal(event.target, `https://outlook.office.com/calendar/deeplink/compose?subject=Sync%20%26%20plan&startdt=2026-11-20T10%3A00%3A00Z&enddt=2026-11-20T11%3A00%3A00Z&body=${MADE}`);
        assert.equal(run('none', 'mail', '--to', 'a@b.nl', '--account', 'personal').target, `https://outlook.live.com/mail/deeplink/compose?to=a%40b.nl&body=${MADE}`);
    });

    it('uses the launch route of the new Outlook for Windows, encoded twice', () => {
        const event = run('windows-new', 'event', '--subject', 'Sync & plan', '--start', '2026-11-20 10:00');
        assert.equal(event.route, 'app');
        assert.equal(event.target, `ms-outlook:launch:calendar%2Fdeeplink%2Fcompose%3Fsubject%3DSync%2520%2526%2520plan%26startdt%3D2026-11-20T10%253A00%253A00Z%26enddt%3D2026-11-20T11%253A00%253A00Z%26body%3D${MADE_TWICE}`);
        assert.equal(run('windows-new', 'open', 'calendar', '--view', 'day', '--date', '2026-11-20').target, 'ms-outlook:launch:calendar%2Fview%2Fday%2F2026%2F11%2F20');
    });

    it('uses mailto and .ics on the Mac and in classic Outlook', () => {
        assert.equal(run('mac', 'mail', '--subject', 'Hi').target, `mailto:?subject=Hi&body=${MADE}`);
        // events/new cannot carry the text with the "Made by" line: the Mac always gets an .ics.
        for (const route of ['auto', 'app']) {
            const mac = run('mac', 'event', '--subject', 'Sync', '--start', '2026-11-20 10:00', '--route', route);
            assert.equal(mac.route, 'ics', route);
            assert.match(mac.ics, /\r\nDESCRIPTION:Made by: Nova AI \(Datalab Rotterdam\)\r\n/);
        }
        const ics = run('mac', 'event', '--subject', 'Sync', '--start', '2026-11-20 10:00', '--location', 'H.4.12');
        assert.equal(ics.route, 'ics');
        assert.match(ics.ics, /LOCATION:H\.4\.12/);
        assert.equal(run('windows-classic', 'event', '--subject', 'Sync', '--start', '2026-11-20').route, 'ics');
        assert.equal(run('windows-classic', 'open', 'calendar', '--view', 'month').route, 'web');
        // In-person meetings with attendees go to the web form there: an .ics would not make the user the organizer.
        assert.equal(run('mac', 'event', '--subject', 'Sync', '--start', '2026-11-20 10:00', '--attendees', 'a@b.nl').route, 'web');
    });

    it('opens the Teams scheduling form for online and hybrid meetings', () => {
        const args = ['event', '--subject', 'Kick-off', '--start', '2026-11-20 10:00', '--attendees', 'a@b.nl, c@d.nl', '--location', 'H.4.12'];
        const web = run('none', ...args, '--meeting', 'hybrid');
        assert.equal(web.route, 'teams-web');
        assert.equal(web.target, `https://teams.microsoft.com/_#/l/meeting/new?subject=Kick-off&startTime=2026-11-20T10%3A00%3A00Z&endTime=2026-11-20T11%3A00%3A00Z&content=Location%3A%20H.4.12%3Cbr%3E%3Cbr%3E${MADE}&attendees=a@b.nl,c@d.nl`);
        const app = run('windows-new', ...args, '--meeting', 'online');
        assert.equal(app.route, 'teams-app');
        assert.ok(app.target.startsWith('msteams:/l/meeting/new?subject=Kick-off&'));
        assert.match(app.note, /Teams link/);
        // Online: the location stays out of the text, the "Made by" line is in; Teams on the Mac; Teams on the web without the app or with --route web.
        assert.match(app.target, new RegExp(`&content=${MADE}&attendees=`));
        // In the user's language, and never twice.
        assert.match(run('none', ...args, '--meeting', 'hybrid', '--lang', 'nl').target, /content=Locatie%3A%20H\.4\.12%3Cbr%3E%3Cbr%3EGemaakt%20door%3A%20Nova%20AI%20%28Datalab%20Rotterdam%29&/);
        assert.equal(run('none', 'mail', '--body', 'Hoi\n\nGemaakt door: Nova AI (Datalab Rotterdam)', '--lang', 'nl').target.match(/Gemaakt/g).length, 1);
        assert.equal(run('none', 'mail', '--lang', 'xx').footer, 'Made by: Nova AI (Datalab Rotterdam)');
        assert.equal(run('mac', ...args, '--meeting', 'online').route, 'teams-app');
        assert.equal(run('windows-classic', ...args, '--meeting', 'online').route, 'teams-web');
        assert.equal(run('windows-new', ...args, '--meeting', 'online', '--route', 'web').route, 'teams-web');
        const failed = fail('none', 'event', '--subject', 'Kick-off', '--start', '2026-11-20', '--all-day', '--meeting', 'online');
        assert.equal(failed.status, 1);
        assert.match(failed.stderr, /needs a start and end time/);
    });

    it('reports the Outlook it found and the routes it can use', () => {
        const mac = run('mac', 'detect');
        assert.equal(mac.outlook, 'mac');
        assert.match(mac.routes, /ics \(events\)/);
        assert.equal(mac.teams, 'app (msteams:)');
        const none = run('none', 'detect');
        assert.equal(none.outlook, 'none');
        assert.equal(none.routes, 'web only: Outlook on the web');
        assert.equal(none.teams, 'web (teams.microsoft.com)');
        assert.equal(run('windows-classic', 'detect').outlook, 'classic-windows');
    });

    it('drafts mail with every field, splitting and repeating addresses', () => {
        const fields = ['mail', '--to', 'a@b.nl, c@d.nl', '--to', 'e@f.nl', '--cc', 'g@h.nl', '--bcc', 'i@j.nl', '--subject', 'Hoi & dag', '--body', 'r1\nr2'];
        assert.equal(run('none', ...fields).target,
            `https://outlook.office.com/mail/deeplink/compose?to=a%40b.nl%2Cc%40d.nl%2Ce%40f.nl&cc=g%40h.nl&bcc=i%40j.nl&subject=Hoi%20%26%20dag&body=r1%0Ar2%0A%0A${MADE}`);
        assert.equal(run('windows-new', 'mail', '--to', 'a@b.nl', '--subject', 'A B').target,
            `ms-outlook:launch:mail%2Fdeeplink%2Fcompose%3Fto%3Da%2540b.nl%26subject%3DA%2520B%26body%3D${MADE_TWICE}`);
        const classic = run('windows-classic', 'mail', '--to', 'a@b.nl', '--cc', 'c@d.nl', '--subject', 'A B');
        assert.equal(classic.route, 'app');
        assert.equal(classic.target, `mailto:a@b.nl?cc=c%40d.nl&subject=A%20B&body=${MADE}`);
        // The mail form takes plain text; the event form reads HTML: escaped, <br> for a new line.
        assert.match(run('none', 'mail', '--body', 'a & <b>\nc').target, /body=a%20%26%20%3Cb%3E%0Ac%0A%0AMade/);
        assert.match(run('none', 'event', '--subject', 'X', '--start', '2026-11-20 10:00', '--body', 'a & <b>\nc').target, /body=a%20%26amp%3B%20%26lt%3Bb%26gt%3B%3Cbr%3Ec%3Cbr%3E%3Cbr%3EMade/);
        assert.equal(run('mac', 'mail', '--route', 'web', '--to', 'a@b.nl').route, 'web');
        const ics = fail('mac', 'mail', '--route', 'ics');
        assert.equal(ics.status, 1);
        assert.match(ics.stderr, /only for events/);
    });

    it('converts local, offset and all-day times', () => {
        // An offset is honoured and sent as UTC with Z.
        assert.match(run('none', 'event', '--subject', 'X', '--start', '2026-11-20T10:00+01:00').target, /startdt=2026-11-20T09%3A00%3A00Z&enddt=2026-11-20T10%3A00%3A00Z/);
        // A date is all-day and lasts a day; --end is its last day, sent as the day after (exclusive).
        assert.match(run('none', 'event', '--subject', 'X', '--start', '2026-11-24').target, /startdt=2026-11-24&enddt=2026-11-25&allday=true&body=Made/);
        assert.match(run('none', 'event', '--subject', 'X', '--start', '2026-11-24', '--end', '2026-11-24').target, /startdt=2026-11-24&enddt=2026-11-25&allday=true&body=Made/);
        assert.match(run('none', 'event', '--subject', 'X', '--start', '2026-11-24', '--end', '2026-11-26').target, /startdt=2026-11-24&enddt=2026-11-27&allday=true&body=Made/);
        assert.match(run('none', 'event', '--subject', 'X', '--start', '2026-11-24 09:00', '--end', '2026-11-25 17:00', '--all-day').target, /startdt=2026-11-24&enddt=2026-11-26&allday=true&body=Made/);
        // The Mac form has no all-day field: an .ics carries it, never with DTEND on or before DTSTART.
        const mac = run('mac', 'event', '--subject', 'X', '--start', '2026-11-24');
        assert.equal(mac.route, 'ics');
        assert.match(mac.ics, /DTSTART;VALUE=DATE:20261124\r\nDTEND;VALUE=DATE:20261125\r\n/);
        assert.match(run('mac', 'event', '--subject', 'X', '--start', '2026-11-24', '--end', '2026-11-24').ics, /DTSTART;VALUE=DATE:20261124\r\nDTEND;VALUE=DATE:20261125\r\n/);
        assert.match(run('mac', 'event', '--subject', 'X', '--start', '2026-11-24', '--end', '2026-11-26').ics, /DTSTART;VALUE=DATE:20261124\r\nDTEND;VALUE=DATE:20261127\r\n/);
    });

    it('refuses an end before the start', () => {
        const allDay = fail('none', 'event', '--subject', 'X', '--start', '2026-11-24', '--end', '2026-11-23');
        assert.equal(allDay.status, 1);
        assert.match(allDay.stderr, /--end is before --start/);
        const timed = fail('none', 'event', '--subject', 'X', '--start', '2026-11-20 10:00', '--end', '2026-11-20 10:00');
        assert.equal(timed.status, 1);
        assert.match(timed.stderr, /--end must be after --start/);
    });

    it('writes a valid .ics, escaping text and listing attendees', () => {
        const { ics } = run('windows-classic', 'event', '--subject', 'a,b;c', '--start', '2026-11-20 10:00', '--location', 'x\\y', '--body', 'l1\nl2', '--route', 'ics', '--attendees', 'a@b.nl,c@d.nl');
        assert.match(ics, /^BEGIN:VCALENDAR\r\n/);
        assert.match(ics, /END:VEVENT\r\nEND:VCALENDAR\r\n$/);
        assert.doesNotMatch(ics.replaceAll('\r\n', ''), /\n/);
        assert.match(ics, /\r\nUID:[0-9a-f-]{36}@nova-ms-outlook\r\n/);
        assert.match(ics, /\r\nDTSTART:20261120T100000Z\r\nDTEND:20261120T110000Z\r\n/);
        assert.match(ics, /\r\nSUMMARY:a\\,b\\;c\r\n/);
        assert.match(ics, /\r\nLOCATION:x\\\\y\r\n/);
        assert.match(ics, /\r\nDESCRIPTION:l1\\nl2\\n\\nMade by: Nova AI \(Datalab Rotterdam\)\r\n/);
        assert.match(ics, /\r\nATTENDEE;RSVP=TRUE:mailto:a@b.nl\r\nATTENDEE;RSVP=TRUE:mailto:c@d.nl\r\n/);
    });

    it('passes attendees to the Outlook form and says the user must press Send', () => {
        const app = run('windows-new', 'event', '--subject', 'K', '--start', '2026-11-20 10:00', '--attendees', 'a@b.nl');
        assert.equal(app.route, 'app');
        assert.match(app.target, /%26body%3DMade%2520by.*%26to%3Da%2540b\.nl$/);
        assert.match(app.note, /must press Send/);
        const web = run('none', 'event', '--subject', 'K', '--start', '2026-11-20 10:00', '--attendees', 'a@b.nl', '--meeting', 'in-person');
        assert.match(web.target, /&to=a%40b\.nl$/);
        assert.match(web.note, /must press Send.*Teams toggle/);
        assert.equal(run('none', 'event', '--subject', 'K', '--start', '2026-11-20 10:00').note, undefined);
        // No desktop Outlook: an app route becomes the web form.
        assert.equal(run('none', 'event', '--subject', 'K', '--start', '2026-11-20 10:00', '--route', 'app').route, 'web');
    });

    it('opens views in the app where it has a link, and on the web otherwise', () => {
        assert.deepEqual(['route', 'target'].map((k) => run('windows-classic', 'open', 'calendar')[k]), ['app', 'outlook:calendar']);
        assert.equal(run('windows-classic', 'open', 'people').target, 'outlook:contacts');
        const sent = run('windows-classic', 'open', 'mail', '--folder', 'sentitems');
        assert.equal(sent.target, 'https://outlook.office.com/mail/sentitems');
        assert.match(sent.note, /opened Outlook on the web/);
        const mac = run('mac', 'open', 'mail');
        assert.deepEqual([mac.route, mac.target], ['app', 'com.microsoft.Outlook']);
        assert.match(mac.note, /brought forward/);
        assert.equal(run('mac', 'open', 'calendar', '--view', 'day').target, 'https://outlook.office.com/calendar/view/day');
        assert.equal(run('windows-new', 'open', 'people').target, 'ms-outlook:launch:people');
        assert.equal(run('windows-new', 'open', 'mail').target, 'ms-outlook:launch:mail%2Finbox');
        assert.equal(run('none', 'open', 'settings', '--account', 'personal').target, 'https://outlook.live.com/mail/options/general');
        assert.equal(run('none', 'open', 'calendar').target, 'https://outlook.office.com/calendar/view/week');
    });

    it('opens any Outlook on the web path, in the new Outlook for Windows when it is there', () => {
        assert.equal(run('windows-new', 'path', 'calendar/view/month').target, 'ms-outlook:launch:calendar%2Fview%2Fmonth');
        assert.equal(run('windows-new', 'path', '/calendar/view/month', '--route', 'web').target, 'https://outlook.office.com/calendar/view/month');
        assert.equal(run('mac', 'path', 'calendar/view/month').route, 'web');
    });

    it('gives the web link with every field when opening fails', () => {
        const event = unopenable('windows-new', 'event', '--subject', 'K', '--start', '2026-11-20', '--location', 'H.4.12', '--attendees', 'a@b.nl');
        assert.equal(event.status, 1);
        assert.equal(event.opened, false);
        assert.equal(event.error, 'OSError: no handler');
        assert.equal(event.fallback, `open this link instead: https://outlook.office.com/calendar/deeplink/compose?subject=K&startdt=2026-11-20&enddt=2026-11-21&allday=true&location=H.4.12&body=${MADE}&to=a%40b.nl`);
        assert.equal(unopenable('mac', 'mail', '--to', 'a@b.nl', '--account', 'personal').fallback, `open this link instead: https://outlook.live.com/mail/deeplink/compose?to=a%40b.nl&body=${MADE}`);
        assert.equal(unopenable('windows-classic', 'open', 'calendar').fallback, 'open this link instead: https://outlook.office.com/calendar/view/week');
        assert.equal(unopenable('windows-new', 'path', 'people').fallback, 'open this link instead: https://outlook.office.com/people');
        assert.match(unopenable('mac', 'event', '--subject', 'K', '--start', '2026-11-20 10:00', '--meeting', 'online').fallback, /https:\/\/teams\.microsoft\.com\/_#\/l\/meeting\/new\?subject=K&/);
        // A web route failing has nothing better to offer.
        const web = unopenable('none', 'mail', '--to', 'a@b.nl');
        assert.equal(web.status, 1);
        assert.equal(web.fallback, undefined);
    });
});

describe('nova-ms-teams', () => {
    const scripts = () => join(SKILLS_DIR, 'nova-ms-teams', 'scripts');
    const python = process.platform === 'win32' ? 'python' : 'python3';
    // NOVA_TEAMS_SIMULATE fakes the installed Teams; --print never opens or copies anything.
    const env = (simulate) => ({ ...process.env, NOVA_TEAMS_SIMULATE: simulate, TZ: 'UTC0', PYTHONDONTWRITEBYTECODE: '1', LANG: 'en_US.UTF-8', LC_ALL: '', LC_MESSAGES: '' });
    const run = (simulate, ...args) => JSON.parse(execFileSync(python, [join(scripts(), 'teams.py'), ...args, '--print'], { encoding: 'utf8', env: env(simulate) }));
    const fail = (simulate, ...args) => spawnSync(python, [join(scripts(), 'teams.py'), ...args, '--print'], { encoding: 'utf8', env: env(simulate) });
    // Runs the script with opening and copying replaced, to see the clipboard handling and the web fallback.
    const fake = (simulate, { opens, copies }, ...args) => {
        const code = 'import sys; sys.path.insert(0, sys.argv[1]); import teams\n'
            + `teams.open_target = lambda *a: ${opens ? '(True, None)' : '(False, "OSError: no handler")'}\n`
            + `teams.copy_to_clipboard = lambda *a: ${copies ? 'True' : 'False'}\n`
            + 'sys.exit(teams.main(sys.argv[2:]))';
        const out = spawnSync(python, ['-c', code, scripts(), ...args], { encoding: 'utf8', env: env(simulate) });
        return { status: out.status, ...JSON.parse(out.stdout) };
    };

    it('is installed by default, with its script, routes and alias', async () => {
        assert.ok((await installSkills(novaHome)).includes('nova-ms-teams'));
        for (const file of ['SKILL.md', 'scripts/teams.py', 'references/routes.md', 'LICENSE.txt', 'NOTICE']) {
            assert.ok(existsSync(join(novaHome, 'skills', 'nova-ms-teams', file)), file);
        }
        for (const [skill, alias] of [['nova-ms-teams', 'teams'], ['nova-ms-outlook', 'outlook']]) {
            const head = readFileSync(join(SKILLS_DIR, skill, 'SKILL.md'), 'utf8');
            const description = /^description: (.+)$/m.exec(head)?.[1] ?? '';
            assert.ok(description.length > 0 && description.length <= 200, `${skill} description`);
            assert.match(head, new RegExp(`^aliases: \\[${alias}\\]$`, 'm'));
        }
    });

    it('prepares a chat message in the app, or on the web without it', () => {
        const web = run('none', 'chat', '--to', 'a@b.nl', '--message', 'Hoi & dag\nr2');
        assert.equal(web.route, 'web');
        assert.equal(web.target, 'https://teams.microsoft.com/_#/l/chat/0/0?users=a@b.nl&message=Hoi%20%26amp%3B%20dag%0Ar2');
        // The message box reads HTML: escaped, but newlines stay newlines (they work there).
        assert.match(run('none', 'chat', '--to', 'a@b.nl', '--message', '<b>x</b>').target, /message=%26lt%3Bb%26gt%3Bx%26lt%3B%2Fb%26gt%3B$/);
        assert.match(web.note, /not sent/);
        // A topic only names a group chat; addresses split and repeat.
        assert.equal(run('mac', 'chat', '--to', 'a@b.nl, c@d.nl', '--to', 'e@f.nl', '--topic', 'P X').target,
            'msteams:/l/chat/0/0?users=a@b.nl,c@d.nl,e@f.nl&topicName=P%20X');
        assert.equal(run('windows', 'chat', '--to', 'a@b.nl', '--topic', 'P X').target, 'msteams:/l/chat/0/0?users=a@b.nl');
        assert.equal(run('windows', 'chat', '--to', 'a@b.nl', '--route', 'web').route, 'web');
        const none = fail('none', 'chat', '--message', 'x');
        assert.equal(none.status, 1);
        assert.match(none.stderr, /needs --to/);
    });

    it('opens the scheduling form for a meeting, with the location in the text', () => {
        const web = run('none', 'meeting', '--subject', 'Kick-off', '--start', '2026-11-20 10:00', '--attendees', 'a@b.nl,c@d.nl', '--location', 'H.4.12', '--body', 'Agenda');
        assert.equal(web.target, 'https://teams.microsoft.com/_#/l/meeting/new?subject=Kick-off&startTime=2026-11-20T10%3A00%3A00Z&endTime=2026-11-20T11%3A00%3A00Z&content=Location%3A%20H.4.12%3Cbr%3E%3Cbr%3EAgenda%3Cbr%3E%3Cbr%3EMade%20by%3A%20Nova%20AI%20%28Datalab%20Rotterdam%29&attendees=a@b.nl,c@d.nl');
        assert.match(web.note, /sends the invitations.*Location field stays empty/);
        // The form reads the text as HTML: escaped, with <br> for a new line.
        assert.match(run('none', 'meeting', '--subject', 'X', '--start', '2026-11-20 10:00', '--body', 'a & <b>\nc').target, /content=a%20%26amp%3B%20%26lt%3Bb%26gt%3B%3Cbr%3Ec%3Cbr%3E%3Cbr%3EMade%20by/);
        const app = run('mac', 'meeting', '--subject', 'X', '--start', '2026-11-20T10:00+01:00', '--end', '2026-11-20T12:30+01:00');
        assert.equal(app.target, 'msteams:/l/meeting/new?subject=X&startTime=2026-11-20T09%3A00%3A00Z&endTime=2026-11-20T11%3A30%3A00Z&content=Made%20by%3A%20Nova%20AI%20%28Datalab%20Rotterdam%29');
        assert.equal(app.footer, 'Made by: Nova AI (Datalab Rotterdam)');
        assert.doesNotMatch(app.note, /invitations/);
        assert.match(fail('none', 'meeting', '--subject', 'X', '--start', '2026-11-20').stderr, /needs a start time/);
        assert.match(fail('none', 'meeting', '--subject', 'X', '--start', '2026-11-20 10:00', '--end', '2026-11-20 09:00').stderr, /after --start/);
    });

    it('opens Teams or a copied Teams link, and only Teams links', () => {
        assert.equal(run('mac', 'open').target, 'msteams:');
        assert.equal(run('none', 'open').target, 'https://teams.microsoft.com/');
        const channel = 'https://teams.microsoft.com/l/channel/19%3Aabc%40thread.tacv2/General?groupId=g&tenantId=t';
        assert.equal(run('windows', 'open', '--link', channel).target, 'msteams:/l/channel/19%3Aabc%40thread.tacv2/General?groupId=g&tenantId=t');
        assert.equal(run('none', 'open', '--link', channel).target, 'https://teams.microsoft.com/_#/l/channel/19%3Aabc%40thread.tacv2/General?groupId=g&tenantId=t');
        assert.equal(run('none', 'open', '--link', 'msteams:/l/chat/0/0?users=a@b.nl').target, 'https://teams.microsoft.com/_#/l/chat/0/0?users=a@b.nl');
        assert.equal(run('mac', 'open', '--link', 'https://teams.microsoft.com/_#/l/chat/0/0?users=a@b.nl').target, 'msteams:/l/chat/0/0?users=a@b.nl');
        for (const link of ['https://evil.example/l/channel/x', 'https://teams.microsoft.com.evil.example/l/x', 'javascript:alert(1)']) {
            const bad = fail('mac', 'open', '--link', link);
            assert.equal(bad.status, 1, link);
            assert.match(bad.stderr, /must be a Teams link/);
        }
    });

    it('puts a channel message on the clipboard, and says when it could not', () => {
        const link = 'https://teams.microsoft.com/l/channel/19%3Aabc/General?groupId=g&tenantId=t';
        const copied = fake('mac', { opens: true, copies: true }, 'open', '--link', link, '--message', 'Hoi');
        assert.deepEqual([copied.status, copied.opened, copied.clipboard], [0, true, true]);
        assert.match(copied.note, /on the clipboard/);
        assert.equal(fake('mac', { opens: true, copies: false }, 'open', '--link', link, '--message', 'Hoi').clipboard, false);
        assert.match(run('mac', 'open', '--link', link, '--message', 'Hoi').note, /not copied/);
    });

    it('gives the web link when the app cannot be opened', () => {
        const chat = fake('windows', { opens: false }, 'chat', '--to', 'a@b.nl', '--message', 'Hoi');
        assert.deepEqual([chat.status, chat.opened, chat.error], [1, false, 'OSError: no handler']);
        assert.equal(chat.fallback, 'open this link instead: https://teams.microsoft.com/_#/l/chat/0/0?users=a@b.nl&message=Hoi');
        assert.equal(fake('none', { opens: false }, 'chat', '--to', 'a@b.nl').fallback, undefined);
    });

    it('reports whether the Teams app is installed', () => {
        assert.deepEqual(['teams', 'routes'].map((k) => run('none', 'detect')[k]), ['none', 'web only: Teams on the web (teams.microsoft.com)']);
        assert.equal(run('windows', 'detect').teams, 'app');
    });
});

it('compareVersions orders releases and prereleases', () => {
    assert.equal(compareVersions('1.2.0', '1.10.0'), -1);
    assert.equal(compareVersions('1.0.0', '1.0.0-alpha.3'), 1);
    assert.equal(compareVersions('1.0.0-alpha.10', '1.0.0-alpha.9'), 1);
    assert.equal(compareVersions('1.0.0', '1.0.0'), 0);
});

it('installs the embedded copies from a CommonJS bundle, where import.meta is empty', async () => {
    const { buildSync } = await import('esbuild');
    const dir = mkdtempSync(join(tmpdir(), 'nova-skills-cjs-'));
    const out = join(dir, 'bundle.cjs');
    buildSync({ entryPoints: [fileURLToPath(new URL('../index.js', import.meta.url))], bundle: true, platform: 'node', format: 'cjs', outfile: out, logLevel: 'silent' });
    const { createRequire } = await import('node:module');
    const bundled = createRequire(import.meta.url)(out);
    assert.equal(bundled.SKILLS_DIR, undefined);
    assert.equal(bundled.VERSION, VERSION);
    const home = join(dir, '.nova-ai');
    assert.deepEqual((await bundled.installSkills(home, { include: ['nova-browser'] })).sort(), ['nova-browser', 'nova-docx', 'nova-ms-outlook', 'nova-ms-teams', 'nova-pdf', 'nova-pptx', 'nova-xlsx']);
    // The same files as from the package folder.
    const fromDisk = join(dir, 'disk');
    await installSkills(fromDisk, { include: ['nova-browser'] });
    for (const name of ['nova-browser', 'nova-docx', 'nova-ms-outlook', 'nova-ms-teams']) {
        assert.equal(JSON.parse(readFileSync(join(home, 'skills', name, BUNDLE_FILE), 'utf8')).hash, JSON.parse(readFileSync(join(fromDisk, 'skills', name, BUNDLE_FILE), 'utf8')).hash);
    }
    rmSync(dir, { recursive: true, force: true });
});

it('embedded.js is current (run npm run embed)', async () => {
    const { embeddedSource } = await import('../scripts/embed.mjs');
    assert.equal(readFileSync(new URL('../embedded.js', import.meta.url), 'utf8'), embeddedSource());
});

describe('nova-browser (optional)', () => {
    const folder = () => join(novaHome, 'skills', 'nova-browser');

    it('is installed only for an app that asks for it, read-only with runnable scripts', async () => {
        assert.ok(!(await installSkills(novaHome)).includes('nova-browser'));
        assert.equal(existsSync(folder()), false);
        assert.deepEqual(await installSkills(novaHome, { include: ['nova-browser'] }), ['nova-browser']);
        if (process.platform !== 'win32') {
            assert.equal(statSync(join(folder(), 'SKILL.md')).mode & 0o777, 0o444);
            assert.equal(statSync(join(folder(), 'scripts', 'nova-browser')).mode & 0o777, 0o555);
        }
        // An app without it leaves another app's copy alone.
        await installSkills(novaHome);
        assert.equal(existsSync(join(folder(), 'SKILL.md')), true);
    });

    it('is removed when the app switches the browser off, but never a folder of the user', async () => {
        await installSkills(novaHome, { include: ['nova-browser'] });
        assert.deepEqual(await removeSkills(novaHome, ['nova-browser']), ['nova-browser']);
        assert.equal(existsSync(folder()), false);

        mkdirSync(folder(), { recursive: true });
        writeFileSync(join(folder(), 'SKILL.md'), 'mine');
        assert.deepEqual(await removeSkills(novaHome, ['nova-browser']), []);
        assert.equal(readFileSync(join(folder(), 'SKILL.md'), 'utf8'), 'mine');
    });

    it('takes over the copy the browser host installed', async () => {
        mkdirSync(folder(), { recursive: true });
        writeFileSync(join(folder(), 'SKILL.md'), 'old');
        mkdirSync(join(folder(), 'scripts'));
        writeFileSync(join(folder(), 'scripts', 'nova-browser'), 'old');
        writeFileSync(join(folder(), BUNDLE_FILE), JSON.stringify({ bundledBy: 'Nova AI Browser', version: '1.3.0', hash: 'x' }));
        // The host locked its folders as well as its files.
        for (const dir of [join(folder(), 'scripts'), folder()]) chmodSync(dir, 0o555);
        assert.ok((await installSkills(novaHome, { include: ['nova-browser'] })).includes('nova-browser'));
        assert.equal(marker('nova-browser').bundledBy, BUNDLED_BY);
        // And it can be removed again.
        for (const dir of [join(folder(), 'scripts'), folder()]) chmodSync(dir, 0o555);
        assert.deepEqual(await removeSkills(novaHome, ['nova-browser']), ['nova-browser']);
        assert.equal(existsSync(folder()), false);
    });

    it('runs the browser host the Nova apps registered', { skip: process.platform === 'win32' }, async () => {
        await installSkills(novaHome, { include: ['nova-browser'] });
        const script = join(folder(), 'scripts', 'nova-browser');
        const browserHome = join(base, 'browser');
        const run = () => spawnSync(script, ['tabs_context', 'x=1'], { encoding: 'utf8', env: { ...process.env, NOVA_AI_BROWSER_HOME: browserHome } });

        const missing = run();
        assert.equal(missing.status, 2);
        assert.match(missing.stderr, /not set up/);

        mkdirSync(join(browserHome, 'bin'), { recursive: true });
        writeFileSync(join(browserHome, 'bin', 'nova-ai-browser-host'), '#!/bin/sh\necho "host $*"\n', { mode: 0o755 });
        assert.equal(run().stdout, 'host call tabs_context x=1\n');
    });
});
