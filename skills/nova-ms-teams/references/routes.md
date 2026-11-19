# Teams routes

What `scripts/teams.py` uses, why, and how far each route has been verified. Microsoft documents
these deep links (Microsoft Learn, "Deep link to a chat", "Deep link to open a meeting scheduling
dialog", "Deep link to a channel"); the Teams clients can still change how they handle them. When
the app route stops working, `--route web` still does.

## Detection

| Platform | How the script detects Teams |
|---|---|
| Windows | Appx package `MSTeams` (new Teams) |
| macOS | `/Applications/Microsoft Teams.app` or `~/Applications/Microsoft Teams.app` |
| Linux and others | no Teams app: web |

With the app, a `/l/...` path is opened as `msteams:/l/...`; otherwise as
`https://teams.microsoft.com/_#/l/...`. The documented `https://teams.microsoft.com/l/...` first
shows a launcher page ("download the app / use the web app") whose web button did not react in an
automated browser; `/_#/` goes straight to Teams on the web (`teams.cloud.microsoft`).

## Chat

```
/l/chat/0/0?users=a@x.nl,b@x.nl&topicName=Project%20X&message=Hoi
```

`users` are UPNs (usually the e-mail address), plain commas between them. One user opens the 1:1
chat, several a group chat; `topicName` only applies to a new group chat, so the script sends it
only with several users. `message` is put in the compose box, not sent.

Verified 19 November 2026 on Teams on the web (Chrome, macOS, work account), chat with oneself:
the text lands in the compose box with newlines (`%0A`), accents, `#`, `?` and `=` intact.
The box reads `message` as **HTML**, in the app and on the web: `<x>` vanished, `<b>` turned bold,
`&lt;` became `<`. The script therefore escapes `&`, `<` and `>`; newlines stay `%0A` (they work).
**A draft that is already in that chat's box is kept: the link does not replace it**, so tell the
user to check the box. The `msteams:` route works in the Teams app on macOS (text and newline
in the box). Group chats and `topicName` untested.

## Meeting

```
/l/meeting/new?subject=&startTime=&endTime=&content=&attendees=a@x.nl,b@x.nl
```

The same route `nova-ms-outlook` uses for online and hybrid meetings. `startTime`/`endTime` are
ISO 8601 in UTC with `Z` (the link does not accept `+`).

Verified 19 November 2026 on Teams on the web (Chrome on Windows and macOS): subject, attendees,
date, local start and end time and the online-meeting toggle are filled in.

- `content` is read as **HTML**: plain newlines (`%0A`, `%0D%0A`) disappear, `<br>` breaks a line.
  The script escapes `&`, `<`, `>` and turns newlines into `<br>`.
- The form has a *Location* field, but the link cannot fill it: `location=` is ignored. The script
  puts the location at the top of `content`; the user can type it in the field.
- With attendees the button says *Send* (*Verzenden*), without them *Save* (*Opslaan*).
- `msteams:` untested.

## Channels and other places

A channel link looks like
`https://teams.microsoft.com/l/channel/<channel id>/<name>?groupId=<team id>&tenantId=<tenant id>`.
The IDs cannot be derived from the channel's name without Microsoft Graph, so the user copies the
link in Teams. There is no parameter to fill in a channel post; the script copies the text to the
clipboard (`pbcopy` on the Mac, PowerShell `Set-Clipboard` on Windows, `wl-copy`/`xclip`/`xsel`
on Linux). `open --link` accepts any `https://teams.microsoft.com/l/...`,
`https://teams.cloud.microsoft/l/...` or `msteams:` link (also message and chat links).

*Copy link* (*Koppeling kopiëren*) on a channel now gives a `https://teams.cloud.microsoft/l/channel/...`
link. Verified 19 November 2026 on macOS: the script turned it into `msteams:/l/channel/...` and
the Teams app opened that channel, and `pbcopy` put the text (newlines, accents) on the clipboard.
Windows and Linux (app route and clipboard) untested.

## Not used

- `/l/call/0/0?users=`: starts a call at once.
- Microsoft Graph (`POST /chats/{id}/messages`, `/teams/{id}/channels/{id}/messages`): sends
  directly and needs consent from the organisation; this skill never sends.
- `teams.live.com` (Teams Free): does not support these links reliably.
