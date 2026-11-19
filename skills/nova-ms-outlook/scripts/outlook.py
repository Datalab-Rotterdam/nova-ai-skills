#!/usr/bin/env python3
"""Nova AI Outlook: open Outlook forms and views on this computer, or Outlook on the web.

Opens things for the user to finish; never saves, sends or deletes anything itself.

    outlook.py detect
    outlook.py mail  [--to A] [--cc A] [--bcc A] [--subject S] [--body B] [--lang nl|en|...]
    outlook.py event --subject S --start WHEN [--end WHEN] [--location L] [--body B] [--all-day] [--lang nl|en|...]
                     [--attendees A ...] [--meeting in-person|online|hybrid]
    outlook.py open  calendar|mail|people|settings [--view day|workweek|week|month] [--date YYYY-MM-DD]
                     [--folder inbox|drafts|sentitems|deleteditems|junkemail|archive]
    outlook.py path  OWA_PATH            (new Outlook for Windows and the web only)

Common options:
    --route auto|app|ics|web   auto (default) picks the best route for the Outlook found here;
                               web always works (Outlook on the web).
    --account work|personal    which Outlook on the web: outlook.office.com (work/school, default)
                               or outlook.live.com (outlook.com / hotmail).
    --print                    only print the link/file, do not open it (for a remote or headless session).

--meeting online|hybrid opens the Microsoft Teams scheduling form (subject, time, attendees, text),
so the meeting gets a Teams link; Outlook's own event links cannot switch Teams on.

Every e-mail and event ends with "Made by: Nova AI (Datalab Rotterdam)" in the user's language
(--lang, default this computer's language), e.g. "Gemaakt door: Nova AI (Datalab Rotterdam)".

WHEN is local time "YYYY-MM-DD HH:MM", an ISO time with offset, or "YYYY-MM-DD" for all-day.
Prints one JSON object: what was opened, through which route, and the link.
Standard library only; Python 3.8+.
"""
import argparse
import datetime as dt
import html
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import uuid
from urllib.parse import quote

LANG_HELP = 'language of the user (nl, en, de, fr, es, it, pt) for the "Made by" line; default: this computer\'s'
MAC_BUNDLE_ID = "com.microsoft.Outlook"
MAC_APP_PATHS = ["/Applications/Microsoft Outlook.app", os.path.expanduser("~/Applications/Microsoft Outlook.app")]
MAC_TEAMS_PATHS = ["/Applications/Microsoft Teams.app", os.path.expanduser("~/Applications/Microsoft Teams.app")]
TEAMS_WEB = "https://teams.microsoft.com"
WEB_HOSTS = {"work": "https://outlook.office.com", "personal": "https://outlook.live.com"}
VIEWS = ("day", "workweek", "week", "month")
FOLDERS = ("inbox", "drafts", "sentitems", "deleteditems", "junkemail", "archive")
# Classic Outlook for Windows: outlook.exe /select <folder>
CLASSIC_SELECT = {"calendar": "outlook:calendar", "mail": "outlook:inbox", "people": "outlook:contacts"}


def enc(value):
    return quote(str(value), safe="")


def query(pairs):
    return "&".join(f"{k}={enc(v)}" for k, v in pairs if v not in (None, "", []))


def html_text(text):
    """Teams' scheduling form (`content`) and Outlook's event form (`body`) read HTML: plain
    newlines vanish, <br> breaks a line."""
    return html.escape(text or "", quote=False).replace("\r\n", "\n").replace("\n", "<br>")


# --------------------------------------------------------------------------- detection

def _run(cmd, timeout=20):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _detect_windows():
    found = {"os": "windows", "new": None, "classic": None}
    version = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                    "(Get-AppxPackage -Name Microsoft.OutlookForWindows | Select-Object -First 1).Version"])
    alias = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "olk.exe")
    if version or os.path.exists(alias):
        found["new"] = {"version": version or None}
    teams = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                  "(Get-AppxPackage -Name MSTeams | Select-Object -First 1).Version"])
    found["teams"] = {"version": teams} if teams else None
    try:
        import winreg
        key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE"
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, key) as k:
                    exe = winreg.QueryValue(k, None)
                    if exe and os.path.exists(exe.strip('"')):
                        found["classic"] = {"path": exe.strip('"')}
                        break
            except OSError:
                continue
    except ImportError:
        pass
    return found


def _detect_mac():
    found = {"os": "macos", "app": None}
    app = next((p for p in MAC_APP_PATHS if os.path.isdir(p)), None)
    if not app:
        hits = _run(["mdfind", f"kMDItemCFBundleIdentifier == '{MAC_BUNDLE_ID}'"]).splitlines()
        app = hits[0] if hits else None
    if app:
        info = {"path": app, "version": None, "mode": "unknown"}
        try:
            with open(os.path.join(app, "Contents", "Info.plist"), "rb") as f:
                info["version"] = plistlib.load(f).get("CFBundleShortVersionString")
        except (OSError, plistlib.InvalidFileException):
            pass
        mode = _run(["defaults", "read", MAC_BUNDLE_ID, "IsRunningNewOutlook"])
        info["mode"] = {"1": "new", "0": "legacy"}.get(mode, "unknown")
        found["app"] = info
    teams = next((p for p in MAC_TEAMS_PATHS if os.path.isdir(p)), None)
    found["teams"] = {"path": teams} if teams else None
    return found


def detect():
    """Which Outlook is installed here. NOVA_OUTLOOK_SIMULATE overrides it (tests only)."""
    sim = os.environ.get("NOVA_OUTLOOK_SIMULATE")
    if sim:
        return {
            "windows-new": {"os": "windows", "new": {"version": "sim"}, "classic": None, "teams": {"version": "sim"}},
            "windows-classic": {"os": "windows", "new": None, "classic": {"path": "OUTLOOK.EXE"}, "teams": None},
            "mac": {"os": "macos", "app": {"path": MAC_APP_PATHS[0], "version": "sim", "mode": "new"},
                    "teams": {"path": MAC_TEAMS_PATHS[0]}},
            "none": {"os": "other"},
        }[sim]
    if sys.platform.startswith("win"):
        return _detect_windows()
    if sys.platform == "darwin":
        return _detect_mac()
    return {"os": "linux" if sys.platform.startswith("linux") else sys.platform}


def flavour(found):
    """new-windows, classic-windows, mac or None (no desktop Outlook: use the web)."""
    if found.get("os") == "windows":
        if found.get("new"):
            return "new-windows"
        if found.get("classic"):
            return "classic-windows"
    if found.get("os") == "macos" and found.get("app"):
        return "mac"
    return None


# --------------------------------------------------------------------------- footer

# Every e-mail and meeting this skill prepares ends with this line, in the user's language.
FOOTER_NAME = "Nova AI (Datalab Rotterdam)"
FOOTER_LABELS = {"nl": "Gemaakt door", "en": "Made by", "de": "Erstellt von", "fr": "Créé par",
                 "es": "Creado por", "it": "Creato da", "pt": "Criado por"}
LOCATION_LABELS = {"nl": "Locatie", "en": "Location", "de": "Ort", "fr": "Lieu",
                   "es": "Ubicación", "it": "Luogo", "pt": "Local"}


def system_lang():
    """Two-letter language of this computer's user: LC_ALL/LC_MESSAGES/LANG, the macOS or Windows
    setting, else English."""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if value and value not in ("C", "POSIX") and not value.startswith("C."):
            return value[:2].lower()
    if sys.platform == "darwin":
        value = _run(["defaults", "read", "-g", "AppleLocale"])
        if value:
            return value[:2].lower()
    if sys.platform.startswith("win"):
        try:
            import ctypes
            import locale
            value = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), "")
            if value:
                return value[:2].lower()
        except (ImportError, AttributeError, OSError):
            pass
    return "en"


def lang_code(lang):
    code = (lang or system_lang()).replace("-", "_")[:2].lower()
    return code if code in FOOTER_LABELS else "en"


def footer(lang):
    return f"{FOOTER_LABELS[lang_code(lang)]}: {FOOTER_NAME}"


def with_footer(body, lang):
    line = footer(lang)
    body = (body or "").rstrip()
    if line in body:
        return body
    return f"{body}\n\n{line}" if body else line


# --------------------------------------------------------------------------- times

def parse_when(text):
    """Returns (aware datetime, all_day)."""
    text = text.strip()
    if len(text) == 10:
        d = dt.date.fromisoformat(text)
        return dt.datetime(d.year, d.month, d.day).astimezone(), True
    value = dt.datetime.fromisoformat(text.replace("Z", "+00:00").replace("T", " ", 1))
    if value.tzinfo is None:
        value = value.astimezone()  # local time
    return value, False


def utc_iso(value):
    # UTC with Z: Outlook mishandles positive UTC offsets in deep links.
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- routes

def web_url(account, path, pairs=()):
    q = query(pairs)
    return f"{WEB_HOSTS[account]}/{path.lstrip('/')}" + (f"?{q}" if q else "")


def launch_uri(path, pairs=()):
    """New Outlook for Windows: ms-outlook:launch:<path, encoded once more>. olk.exe decodes it
    once and opens https://outlook.office.com/<path>; values must therefore be encoded twice."""
    q = query(pairs)
    return "ms-outlook:launch:" + enc(path.lstrip("/") + (f"?{q}" if q else ""))


def mailto_uri(to, cc, bcc, subject, body):
    return "mailto:" + ",".join(to) + (("?" + q) if (q := query(
        [("cc", ",".join(cc)), ("bcc", ",".join(bcc)), ("subject", subject), ("body", body)])) else "")


def ics_text(subject, start, end, all_day, location, body, attendees):
    def esc(s):
        return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    def stamp(v):
        return v.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Nova AI//nova-ms-outlook//EN", "METHOD:PUBLISH",
             "BEGIN:VEVENT", f"UID:{uuid.uuid4()}@nova-ms-outlook", f"DTSTAMP:{stamp(dt.datetime.now(dt.timezone.utc))}"]
    if all_day:
        lines += [f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}", f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}"]
    else:
        lines += [f"DTSTART:{stamp(start)}", f"DTEND:{stamp(end)}"]
    lines.append(f"SUMMARY:{esc(subject)}")
    if location:
        lines.append(f"LOCATION:{esc(location)}")
    if body:
        lines.append(f"DESCRIPTION:{esc(body)}")
    lines += [f"ATTENDEE;RSVP=TRUE:mailto:{a}" for a in attendees]
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


def write_ics(text):
    folder = os.path.join(tempfile.gettempdir(), "nova-ms-outlook")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"event-{dt.datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}.ics")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return path


# --------------------------------------------------------------------------- opening

def open_target(target, kind, how, found, dry):
    """kind: uri | file | classic-select | activate. how: system | outlook (mac: force Outlook)."""
    if dry:
        return False, None
    try:
        osname = found.get("os")
        if kind == "classic-select":
            subprocess.Popen([found["classic"]["path"], "/select", target])
        elif kind == "activate":  # macOS: bring Outlook forward
            subprocess.run(["open", "-b", MAC_BUNDLE_ID], check=True, capture_output=True, timeout=20)
        elif osname == "windows":
            os.startfile(target)  # noqa: protocol URIs and files through the registered handler
        elif osname == "macos":
            if how == "outlook" and kind == "uri":
                cmd = ["open", "-b", MAC_BUNDLE_ID, target]
            elif how == "outlook":
                cmd = ["open", "-a", found["app"]["path"], target]
            else:
                cmd = ["open", target]
            subprocess.run(cmd, check=True, capture_output=True, timeout=20)
        else:
            opener = shutil.which("xdg-open")
            if opener:
                subprocess.run([opener, target], check=True, capture_output=True, timeout=20)
            else:
                import webbrowser
                if not webbrowser.open(target):
                    return False, "no browser to open it with"
        return True, None
    except Exception as e:  # report, do not crash: the agent can still give the link to the user
        return False, f"{type(e).__name__}: {e}"


# --------------------------------------------------------------------------- actions

def plan_mail(a, fl):
    pairs = [("to", ",".join(a.to)), ("cc", ",".join(a.cc)), ("bcc", ",".join(a.bcc)),
             ("subject", a.subject), ("body", a.body)]
    if a.route == "web" or (a.route == "auto" and fl is None):
        return "web", web_url(a.account, "mail/deeplink/compose", pairs), "uri", "system"
    if a.route == "ics":
        raise SystemExit("--route ics is only for events")
    if fl is None:
        return "web", web_url(a.account, "mail/deeplink/compose", pairs), "uri", "system"
    if fl == "new-windows":
        return "app", launch_uri("mail/deeplink/compose", pairs), "uri", "system"
    # classic Windows and Mac: mailto, on the Mac sent to Outlook even when it is not the default
    return "app", mailto_uri(a.to, a.cc, a.bcc, a.subject, a.body), "uri", "outlook" if fl == "mac" else "system"


def plan_teams(a, start, end, found):
    """Teams scheduling form: the documented teams.microsoft.com/l/meeting/new link. With Teams
    installed it goes to the app (msteams:), otherwise to Teams on the web."""
    content = a.body
    if a.meeting == "hybrid" and a.location:
        content = f"{LOCATION_LABELS[lang_code(a.lang)]}: {a.location}" + (f"\n\n{a.body}" if a.body else "")
    pairs = [("subject", a.subject), ("startTime", utc_iso(start)), ("endTime", utc_iso(end)), ("content", html_text(content))]
    path = "/l/meeting/new?" + query(pairs)
    if a.attendees:  # the documented form: plain commas between the addresses
        path += "&attendees=" + ",".join(quote(x, safe="@") for x in a.attendees)
    if found.get("teams") and a.route != "web":
        return "teams-app", "msteams:" + path, "uri", "system"
    # "/_#" skips the launcher page ("download the app / use the web app") and lands directly in
    # the scheduling form on Teams on the web (teams.cloud.microsoft), with the fields filled in.
    return "teams-web", TEAMS_WEB + "/_#" + path, "uri", "system"


def plan_event(a, fl, found=None):
    start, all_day = parse_when(a.start)
    all_day = all_day or a.all_day
    if a.end:
        end, _ = parse_when(a.end)
        if all_day:
            # --end names the last day ("24 to 26 November"); .ics and Outlook want the day after it.
            end = dt.datetime.combine(end.date() + dt.timedelta(days=1), dt.time()).astimezone()
            if end.date() <= start.date():
                raise SystemExit("--end is before --start")
        elif end <= start:
            raise SystemExit("--end must be after --start")
    else:
        end = start + (dt.timedelta(days=1) if all_day else dt.timedelta(hours=1))
    if all_day:
        web_pairs = [("subject", a.subject), ("startdt", start.strftime("%Y-%m-%d")),
                     ("enddt", end.strftime("%Y-%m-%d")), ("allday", "true")]
    else:
        web_pairs = [("subject", a.subject), ("startdt", utc_iso(start)), ("enddt", utc_iso(end))]
    # The event form reads body as HTML (newlines vanish); the mail form and .ics take plain text.
    web_pairs += [("location", a.location), ("body", html_text(a.body)), ("to", ",".join(a.attendees))]

    if a.meeting in ("online", "hybrid"):
        if all_day:
            raise SystemExit("an online meeting needs a start and end time, not --all-day")
        return plan_teams(a, start, end, found or {})

    route = a.route
    if route == "auto" and a.attendees and fl in ("mac", "classic-windows"):
        # An .ics import or events/new does not make the user the organizer of a meeting
        # request; the Outlook on the web form does.
        route = "web"
    if route == "auto":
        if fl is None:
            route = "web"
        elif fl == "new-windows":
            route = "app"
        else:  # Mac and classic Windows: an .ics opens as an appointment form
            route = "ics"
    if route == "app" and fl is None:
        route = "web"
    if route == "app" and fl == "mac":
        # ms-outlook://events/new takes only title, start and end: the text with the "Made by"
        # line would be lost, so the Mac gets an .ics, which carries every field.
        route = "ics"

    if route == "web":
        return "web", web_url(a.account, "calendar/deeplink/compose", web_pairs), "uri", "system"
    if route == "ics":
        text = ics_text(a.subject, start, end, all_day, a.location, a.body, a.attendees)
        return "ics", (text if a.print else write_ics(text)), "file", "outlook" if fl == "mac" else "system"
    if fl == "new-windows":
        return "app", launch_uri("calendar/deeplink/compose", web_pairs), "uri", "system"
    text = ics_text(a.subject, start, end, all_day, a.location, a.body, a.attendees)
    return "ics", (text if a.print else write_ics(text)), "file", "system"


def plan_open(a, fl):
    if a.what == "calendar":
        path = f"calendar/view/{a.view or 'week'}"
        if a.date:
            d = dt.date.fromisoformat(a.date)
            path += f"/{d.year}/{d.month}/{d.day}"
    elif a.what == "mail":
        path = f"mail/{a.folder or 'inbox'}"
    elif a.what == "people":
        path = "people"
    else:
        path = "mail/options/general"

    if a.route == "web" or fl is None:
        return "web", web_url(a.account, path), "uri", "system", None
    if fl == "new-windows":
        return "app", launch_uri(path), "uri", "system", None
    if fl == "classic-windows" and a.what in CLASSIC_SELECT and not (a.view or a.date or a.folder):
        return "app", CLASSIC_SELECT[a.what], "classic-select", "system", None
    if fl == "mac" and a.what in ("calendar", "mail") and not (a.view or a.date or a.folder):
        # The Mac app has no route to a view; bringing Outlook forward is the closest.
        return "app", MAC_BUNDLE_ID, "activate", "outlook", "Outlook for Mac has no link to a specific view; it was brought forward"
    return "web", web_url(a.account, path), "uri", "system", "this Outlook has no link for that view; opened Outlook on the web"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--route", choices=("auto", "app", "ics", "web"), default="auto")
    common.add_argument("--account", choices=tuple(WEB_HOSTS), default="work")
    common.add_argument("--print", action="store_true", help="print the link or file, do not open it")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("detect", parents=[common])
    m = sub.add_parser("mail", parents=[common])
    for f in ("--to", "--cc", "--bcc"):
        m.add_argument(f, action="append", default=[])
    m.add_argument("--subject", default="")
    m.add_argument("--body", default="")
    m.add_argument("--lang", help=LANG_HELP)
    e = sub.add_parser("event", parents=[common])
    e.add_argument("--subject", required=True)
    e.add_argument("--start", required=True)
    e.add_argument("--end")
    e.add_argument("--location", default="")
    e.add_argument("--body", default="")
    e.add_argument("--all-day", action="store_true")
    e.add_argument("--lang", help=LANG_HELP)
    e.add_argument("--attendees", action="append", default=[],
                   help="makes it a meeting request: Outlook then shows Send instead of Save")
    e.add_argument("--meeting", choices=("in-person", "online", "hybrid"),
                   help="online/hybrid: Teams meeting through the Teams scheduling form")
    o = sub.add_parser("open", parents=[common])
    o.add_argument("what", choices=("calendar", "mail", "people", "settings"))
    o.add_argument("--view", choices=VIEWS)
    o.add_argument("--date")
    o.add_argument("--folder", choices=FOLDERS)
    pp = sub.add_parser("path", parents=[common])
    pp.add_argument("owa_path")
    a = p.parse_args(argv)
    for field in ("to", "cc", "bcc", "attendees"):  # "a@x.nl, b@x.nl" and repeated flags both work
        if hasattr(a, field):
            setattr(a, field, [x.strip() for v in getattr(a, field) for x in v.split(",") if x.strip()])

    if a.cmd in ("mail", "event"):
        a.body = with_footer(a.body, a.lang)
    found = detect()
    fl = flavour(found)
    result = {"command": a.cmd, "os": found.get("os"), "outlook": fl or "none", "detected": found}
    if a.cmd == "detect":
        result["routes"] = {
            "new-windows": "app: ms-outlook:launch (mail, events, views, folders); ics; web",
            "classic-windows": "app: mailto, ics (events), outlook.exe /select (folders); web",
            "mac": "app: mailto (mail), ics (events); web for views",
            "none": "web only: Outlook on the web",
        }[fl or "none"]
        result["teams"] = "app (msteams:)" if found.get("teams") else "web (teams.microsoft.com)"
        print(json.dumps(result, indent=2))
        return 0

    note = None
    if a.cmd in ("mail", "event"):
        result["footer"] = footer(a.lang)
    if a.cmd == "mail":
        route, target, kind, how = plan_mail(a, fl)
    elif a.cmd == "event":
        route, target, kind, how = plan_event(a, fl, found)
        notes = []
        if a.attendees:
            notes.append("attendees added: the user must press Send; invitations go out only then")
        if route.startswith("teams"):
            notes.append("Teams scheduling form: the meeting gets a Teams link and appears in the Outlook calendar"
                         + ("; the location is at the top of the meeting text, the form's Location field stays empty "
                            "(the link cannot fill it): the user can type it there" if a.meeting == "hybrid" and a.location else ""))
        elif a.meeting == "in-person":
            notes.append("in person: if Outlook switches the Teams toggle on by itself "
                         "(setting 'Add online meeting to all meetings'), ask the user to switch it off")
        note = "; ".join(notes) or None
    elif a.cmd == "open":
        route, target, kind, how, note = plan_open(a, fl)
    else:
        if a.route == "web" or fl != "new-windows":
            route, target, kind, how = "web", web_url(a.account, a.owa_path), "uri", "system"
        else:
            route, target, kind, how = "app", launch_uri(a.owa_path), "uri", "system"

    if kind == "file" and a.print:
        result.update(route=route, ics=target, opened=False)
    else:
        opened, error = open_target(target, kind, how, found, a.print)
        result.update(route=route, target=target, opened=opened)
        if error:
            result["error"] = error
            if route not in ("web", "teams-web"):
                result["fallback"] = "open this link instead: " + _fallback_web(a)
    if note:
        result["note"] = note
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if (result.get("opened") or a.print) else 1


def _fallback_web(a):
    """The same action on Outlook (or Teams) on the web, with every field the app route had."""
    a.route = "web"
    if a.cmd == "mail":
        return plan_mail(a, None)[1]
    if a.cmd == "event":
        return plan_event(a, None, {})[1]
    if a.cmd == "open":
        return plan_open(a, None)[1]
    return web_url(a.account, a.owa_path)


if __name__ == "__main__":
    sys.exit(main())
