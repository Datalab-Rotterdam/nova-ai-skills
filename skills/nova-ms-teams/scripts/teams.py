#!/usr/bin/env python3
"""Nova AI Teams: prepare Microsoft Teams chat messages and meetings, in the Teams app or on the web.

Opens things for the user to finish; never sends, posts or saves anything itself.

    teams.py detect
    teams.py chat    --to A [--to B ...] [--message M] [--topic T]
    teams.py meeting --subject S --start WHEN [--end WHEN] [--attendees A ...] [--body B] [--location L] [--lang nl|en|...]
    teams.py open    [--link TEAMS_LINK] [--message M]

Common options:
    --route auto|app|web   auto (default) opens the Teams app when it is installed, otherwise
                           Teams on the web; web always opens Teams on the web.
    --print                only print the link, do not open it (for a remote or headless session).

chat     opens a 1:1 chat (one --to) or a group chat (several) with the message typed in the box.
meeting  opens the Teams scheduling form; the meeting gets a Teams link and lands in the calendar.
         Its text ends with "Made by: Nova AI (Datalab Rotterdam)" in the user's language (--lang).
open     opens Teams, or a link the user copied from Teams (a channel, chat or message); with
         --message the text is put on the clipboard, because a channel link cannot carry text.

WHEN is local time "YYYY-MM-DD HH:MM" or an ISO time with offset.
Prints one JSON object: what was opened, through which route, and the link.
Standard library only; Python 3.8+.
"""
import argparse
import datetime as dt
import html
import json
import os
import shutil
import subprocess
import sys
from urllib.parse import quote, urlsplit

MAC_TEAMS_PATHS = ["/Applications/Microsoft Teams.app", os.path.expanduser("~/Applications/Microsoft Teams.app")]
LANG_HELP = 'language of the user (nl, en, de, fr, es, it, pt) for the "Made by" line; default: this computer\'s'
TEAMS_WEB = "https://teams.microsoft.com"
TEAMS_HOSTS = ("teams.microsoft.com", "teams.cloud.microsoft")


def enc(value):
    return quote(str(value), safe="")


def query(pairs):
    return "&".join(f"{k}={enc(v)}" for k, v in pairs if v not in (None, "", []))


# Teams reads both the chat message and the meeting text as HTML: "<x>" vanishes, "<b>" turns bold.
def html_text(text):
    """The scheduling form reads `content` as HTML: plain newlines vanish, <br> breaks a line."""
    return html.escape(text or "", quote=False).replace("\r\n", "\n").replace("\n", "<br>")


def addresses(values):
    # The documented links take plain commas between the addresses.
    return ",".join(quote(x, safe="@") for x in values)


# --------------------------------------------------------------------------- detection

def _run(cmd, timeout=20):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def detect():
    """Whether the Teams app is installed here. NOVA_TEAMS_SIMULATE overrides it (tests only)."""
    sim = os.environ.get("NOVA_TEAMS_SIMULATE")
    if sim:
        return {
            "windows": {"os": "windows", "teams": {"version": "sim"}},
            "mac": {"os": "macos", "teams": {"path": MAC_TEAMS_PATHS[0]}},
            "none": {"os": "other", "teams": None},
        }[sim]
    if sys.platform.startswith("win"):
        version = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                        "(Get-AppxPackage -Name MSTeams | Select-Object -First 1).Version"])
        return {"os": "windows", "teams": {"version": version} if version else None}
    if sys.platform == "darwin":
        app = next((p for p in MAC_TEAMS_PATHS if os.path.isdir(p)), None)
        return {"os": "macos", "teams": {"path": app} if app else None}
    return {"os": "linux" if sys.platform.startswith("linux") else sys.platform, "teams": None}


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
    text = text.strip()
    if len(text) == 10:
        raise SystemExit("a Teams meeting needs a start time (YYYY-MM-DD HH:MM), not only a date")
    value = dt.datetime.fromisoformat(text.replace("Z", "+00:00").replace("T", " ", 1))
    return value.astimezone() if value.tzinfo is None else value


def utc_iso(value):
    # UTC with Z: the Teams link does not accept a "+" offset.
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- routes

def route_for(path, found, route):
    """A /l/... deep link: msteams: for the installed app, otherwise Teams on the web. "/_#" skips
    the launcher page ("download the app / use the web app") and lands in Teams on the web."""
    if found.get("teams") and route != "web":
        return "app", "msteams:" + path
    return "web", TEAMS_WEB + "/_#" + path


def plan_chat(a, found):
    if not a.to:
        raise SystemExit("chat needs --to: the e-mail address (UPN) of everyone in the chat")
    path = "/l/chat/0/0?users=" + addresses(a.to)
    extra = query([("topicName", a.topic if len(a.to) > 1 else ""), ("message", html.escape(a.message, quote=False))])
    return route_for(path + (f"&{extra}" if extra else ""), found, a.route)


def plan_meeting(a, found):
    start = parse_when(a.start)
    end = parse_when(a.end) if a.end else start + dt.timedelta(hours=1)
    if end <= start:
        raise SystemExit("--end must be after --start")
    content = a.body
    if a.location:  # the scheduling form has no location field
        content = f"{LOCATION_LABELS[lang_code(a.lang)]}: {a.location}" + (f"\n\n{a.body}" if a.body else "")
    path = "/l/meeting/new?" + query([("subject", a.subject), ("startTime", utc_iso(start)),
                                       ("endTime", utc_iso(end)), ("content", html_text(content))])
    if a.attendees:
        path += "&attendees=" + addresses(a.attendees)
    return route_for(path, found, a.route)


def plan_open(a, found):
    if not a.link:
        if found.get("teams") and a.route != "web":
            return "app", "msteams:"
        return "web", TEAMS_WEB + "/"
    parts = urlsplit(a.link.strip())
    if parts.scheme == "msteams":
        path = a.link.strip()[len("msteams:"):]
    elif parts.scheme == "https" and parts.hostname in TEAMS_HOSTS and parts.path.startswith(("/l/", "/_")):
        path = a.link.strip().split(parts.hostname, 1)[1]
        if path.startswith("/_#"):
            path = path[3:]
    else:
        raise SystemExit("--link must be a Teams link (https://teams.microsoft.com/l/...), "
                         "for example from 'Get link to channel' or 'Copy link'")
    if not path.startswith("/l/"):  # another Teams web page: open it as it is
        return "web", a.link.strip()
    return route_for(path, found, a.route)


# --------------------------------------------------------------------------- side effects

def open_target(target, found, dry):
    if dry:
        return False, None
    try:
        osname = found.get("os")
        if osname == "windows":
            os.startfile(target)  # noqa: protocol URIs through the registered handler
        elif osname == "macos":
            subprocess.run(["open", target], check=True, capture_output=True, timeout=20)
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


def copy_to_clipboard(text, found):
    """True when the text is on the clipboard."""
    osname = found.get("os")
    try:
        if osname == "windows":
            # Through an environment variable: piping into PowerShell can garble non-ASCII text.
            env = dict(os.environ, NOVA_TEAMS_CLIPBOARD=text)
            cmd, data = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                         "Set-Clipboard -Value $env:NOVA_TEAMS_CLIPBOARD"], None
        else:
            env = None
            if osname == "macos":
                cmd = ["pbcopy"]
            else:
                tool = next((t for t in ("wl-copy", "xclip", "xsel") if shutil.which(t)), None)
                if not tool:
                    return False
                cmd = {"wl-copy": ["wl-copy"], "xclip": ["xclip", "-selection", "clipboard"],
                       "xsel": ["xsel", "--clipboard", "--input"]}[tool]
            data = text.encode("utf-8")
        subprocess.run(cmd, input=data, env=env, check=True, capture_output=True, timeout=20)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


# --------------------------------------------------------------------------- main

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--route", choices=("auto", "app", "web"), default="auto")
    common.add_argument("--print", action="store_true", help="print the link, do not open it")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("detect", parents=[common])
    c = sub.add_parser("chat", parents=[common])
    c.add_argument("--to", action="append", default=[], help="e-mail address (UPN); repeat or comma-separate")
    c.add_argument("--message", default="")
    c.add_argument("--topic", default="", help="name of a new group chat")
    m = sub.add_parser("meeting", parents=[common])
    m.add_argument("--subject", required=True)
    m.add_argument("--start", required=True)
    m.add_argument("--end")
    m.add_argument("--attendees", action="append", default=[])
    m.add_argument("--body", default="")
    m.add_argument("--location", default="", help="goes into the meeting text (hybrid meeting)")
    m.add_argument("--lang", help=LANG_HELP)
    o = sub.add_parser("open", parents=[common])
    o.add_argument("--link", default="")
    o.add_argument("--message", default="", help="put on the clipboard for the user to paste")
    a = p.parse_args(argv)
    for field in ("to", "attendees"):  # "a@x.nl, b@x.nl" and repeated flags both work
        if hasattr(a, field):
            setattr(a, field, [x.strip() for v in getattr(a, field) for x in v.split(",") if x.strip()])

    if a.cmd == "meeting":
        a.body = with_footer(a.body, a.lang)
    found = detect()
    result = {"command": a.cmd, "os": found.get("os"), "teams": "app" if found.get("teams") else "none",
              "detected": found}
    if a.cmd == "detect":
        result["routes"] = ("app (msteams:), web with --route web" if found.get("teams")
                            else "web only: Teams on the web (teams.microsoft.com)")
        print(json.dumps(result, indent=2))
        return 0

    notes = []
    if a.cmd == "chat":
        route, target = plan_chat(a, found)
        if a.message:
            notes.append("the message is typed in the chat box, not sent: the user presses Send")
        if len(a.to) > 1:
            notes.append("group chat: check the people in it before sending")
    elif a.cmd == "meeting":
        route, target = plan_meeting(a, found)
        result["footer"] = footer(a.lang)
        notes.append("Teams scheduling form: the meeting gets a Teams link and appears in the calendar "
                     "when the user saves it" + ("; with attendees that sends the invitations" if a.attendees else "")
                     + ("; the location is at the top of the meeting text, the form's Location field stays empty "
                        "(the link cannot fill it): the user can type it there" if a.location else ""))
    else:
        route, target = plan_open(a, found)

    result.update(route=route, target=target)
    if getattr(a, "message", "") and a.cmd == "open":
        if a.print:
            notes.append("the message was not copied (--print): give the user the text to paste")
        elif copy_to_clipboard(a.message, found):
            result["clipboard"] = True
            notes.append("the message is on the clipboard: the user pastes it (Ctrl+V / Cmd+V) and presses Send")
        else:
            result["clipboard"] = False
            notes.append("could not copy the message: give the user the text to paste")
    opened, error = open_target(target, found, a.print)
    result["opened"] = opened
    if error:
        result["error"] = error
        if route == "app":
            a.route = "web"
            web = {"chat": plan_chat, "meeting": plan_meeting, "open": plan_open}[a.cmd](a, found)[1]
            result["fallback"] = "open this link instead: " + web
    if notes:
        result["note"] = "; ".join(notes)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if (opened or a.print) else 1


if __name__ == "__main__":
    sys.exit(main())
