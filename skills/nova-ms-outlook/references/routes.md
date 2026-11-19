# Outlook routes per platform

What `scripts/outlook.py` uses, why, and how far each route has been verified. "Verified" means
tried by hand on the named version in November 2026; Microsoft does not document most of these
routes, so an update can change them. When a route stops working, `--route web` still does.

## Detection

| Platform | How the script detects Outlook |
|---|---|
| Windows, new Outlook | `Get-AppxPackage Microsoft.OutlookForWindows`, or the `olk.exe` alias in `%LOCALAPPDATA%\Microsoft\WindowsApps` |
| Windows, classic Outlook | registry `App Paths\OUTLOOK.EXE` (HKLM, then HKCU). When both are installed the new Outlook's routes are used |
| macOS | `/Applications/Microsoft Outlook.app` (or `~/Applications`, or Spotlight by bundle id `com.microsoft.Outlook`); version from `Info.plist`; new/legacy mode from `defaults read com.microsoft.Outlook IsRunningNewOutlook` |
| Linux and others | no desktop Outlook: web |

## New Outlook for Windows (olk.exe, 1.2026.1103.200)

The app is a WebView2 shell around Outlook on the web. Its own `ms-outlook:` handler passes the
link to `https://outlook.office.com/mail/deeplink/protocolActivation`, which only understands
`mailto:` and `webcal:` and file activation (`.ics`, `.eml`, `.msg`, `.oft`); everything else
shows "This action isn't supported yet". The jump-list command `ms-outlook:launch:<path>` is
different: olk.exe URL-decodes `<path>` once and opens `https://outlook.office.com/<path>` in the
app. Query values must therefore be encoded twice (once per value, once for the whole path); a
raw space after decoding makes the URL invalid and the app falls back to the inbox.

| Path after `launch:` | Verified |
|---|---|
| `calendar/deeplink/compose?subject=&startdt=&enddt=&location=&body=` | yes (form with subject and time); `allday`, `to` untested |
| `mail/deeplink/compose?to=&cc=&subject=&body=` | yes |
| `calendar/view/{day,workweek,week,month}[/YYYY/M/D]` | yes |
| `mail/{inbox,sentitems,...}` | yes (`sentitems`) |
| `people`, `mail/options/general` | yes |
| `calendar/addcalendar` | opens an empty dialog: do not use |
| `mail/search?q=` | does nothing: there is no search link |
| `mailto:` | yes (also through the system handler) |
| `.ics` file | yes (opens the event to add) |

Other `ms-outlook://` forms (`calendar/compose`, `events/new`, `compose`) all end in "not supported".
The app logs every activation in `%LOCALAPPDATA%\Microsoft\Olk\logs\olk_*.log`
(`Application started with the following command line`, `SourceChanged uri`), which shows where a
link really went.

## Classic Outlook for Windows

Not verified in this round. It handles `mailto:` and opens an `.ics` as an appointment form, and
`outlook.exe /select outlook:calendar` (also `outlook:inbox`, `outlook:contacts`) opens a folder;
these are long-standing, documented command-line options. It has no deep links for other views,
so those open on the web.

## Outlook for Mac (16.115, new Outlook)

A native app that shares its link handling with Outlook for iOS. It registers `mailto`,
`ms-outlook` and `com.microsoft.office.outlook`; an unknown host shows "Unknown host in URL".

| Link | Verified |
|---|---|
| `ms-outlook://emails/new?subject=&body=` | opens a new mail |
| `ms-outlook://events/new?title=&start=&end=` | opens a new event (UTC times with `Z`); no text field, so not used: every event carries the "Made by" line, hence always `.ics` |
| `ms-outlook://`, `ms-outlook://calendar`, `ms-outlook://compose`, `ms-outlook://calendar/compose`, `ms-outlook:launch:` | do not work |
| `mailto:` with `open -b com.microsoft.Outlook` | used for mail: works even when Apple Mail is the default; untested on this machine |
| `.ics` with `open -a "Microsoft Outlook"` | untested on this machine |

AppleScript (`Outlook.sdef`) works only in legacy Outlook; Microsoft cancelled AppleScript for the
new Outlook for Mac. The app does ship App Intents for the Shortcuts app (`CreateDraft`,
`CreateCalendarEvent`, `OpenCalendarEvent`, `ReplyMail`, `ForwardMail`, `GetEvents`, `SearchMail`,
`SendDraft`, ...). They can only be run through a shortcut the user made
(`shortcuts run "<name>" --input-path file.json`); this skill does not use them.
`CreateCalendarEvent` saves the event at once without a form, and `SendDraft` sends: never run
those without the user's explicit go-ahead.

## Teams meetings (online and hybrid)

Outlook's event links have no parameter for the Teams toggle (asked on the Microsoft forum, no
answer), and an .ics cannot create a Teams meeting. The script therefore opens Teams' own,
documented scheduling form (Microsoft Learn, "Deep link to open a meeting scheduling dialog"):

```
https://teams.microsoft.com/l/meeting/new?subject=&startTime=&endTime=&content=&attendees=a@x.nl,b@x.nl
```

`startTime`/`endTime` are ISO 8601; the script sends UTC with `Z` because the link does not accept
`+`. The form has a location field, but the link cannot fill it (`location=` is ignored): for
hybrid meetings the location goes at the top of `content`. `content` is read as HTML, so the
script escapes it and turns newlines into `<br>` (plain newlines disappear). With Teams
installed (Windows: Appx package `MSTeams`; Mac: `Microsoft Teams.app`) the same path is opened as
`msteams:/l/meeting/new?...` so it goes straight to the app; otherwise the https link opens Teams on
the web. Without Teams the script opens `https://teams.microsoft.com/_#/l/meeting/new?...`: the
documented form first shows a launcher page ("download the app / use the web app") whose web
button did not react in an automated browser, while `/_#/` goes straight to the form on
`teams.cloud.microsoft`. Verified 19 November 2026 in Chrome on Windows: subject, date, 10:00-11:00
local time and the online-meeting toggle were filled in. `msteams:` and `attendees` are untested. Saving the form sends the invitations and puts the
meeting, with its Teams link, in the Outlook calendar.

For in-person meetings the Outlook form is used; an account with "Add online meeting to all
meetings" switches Teams on by itself, so the user should check the toggle.

## Meetings with attendees in person

The new Outlook for Windows opens the Outlook form with `to=` (untested parameter). On the Mac and
with classic Outlook the script uses the Outlook on the web form instead of an .ics: importing an
.ics with attendees does not make the user the organizer of a meeting request.

## Outlook on the web (fallback)

`https://outlook.office.com` (work or school) or `https://outlook.live.com` (personal):

| Path | Purpose |
|---|---|
| `/calendar/deeplink/compose?subject=&startdt=&enddt=&location=&body=&allday=true&to=` | new event form |
| `/mail/deeplink/compose?to=&cc=&bcc=&subject=&body=` | new mail form |
| `/calendar/view/week`, `/mail/inbox`, `/people`, `/mail/options/general` | views |

The event form reads `body` as **HTML**: plain newlines disappear, `<br>` breaks a line; the script
escapes the text and turns newlines into `<br>` (verified 19 November 2026, Chrome on macOS). The mail
form takes `body` as plain text: newlines and `<`/`&` arrive as they are (verified the same day); the
user's own signature follows the text.

Use UTC times with `Z` in `startdt`/`enddt`: with a positive offset such as `+01:00` Outlook has been
seen to ignore the time and pick the next hour.
