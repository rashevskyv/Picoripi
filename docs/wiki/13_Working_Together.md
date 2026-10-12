---
status: current
updated: 2026-10-12
owns: core/collab
tokens: 2.4k
purpose: Rooms, roles, claims, comments
---
# Working Together and Progress

**Language:** English · [Українська](uk/13_Working_Together.md)

## Rooms

One participant **hosts** a room in their own Picoripi; the others **join** it. There is no central server and nothing
to install: the host's Picoripi is the server (`core/collab/server.py`, Python standard library only). Open it with
**Tools → Work Together...** or the **Room:** button in the status bar.

- **Host:** type your name, choose a port (8765 by default) and a password (one is suggested), press **Start the room**.
  Windows may ask to let Picoripi through the firewall. **Copy the invitation** copies the computer's addresses and the
  password; send them to the others.
- **Join:** type your name, the host's address (`192.168.1.20:8765`) and the password, press **Join**.
- **Everyone opens the same project.** Rows are named by file, block key and line, and the room checks a fingerprint of
  every row's source text: a different dump or region of the game is refused with "another project".
- **Network:** the room listens on this computer only (`127.0.0.1`) until you tick **Allow other computers (LAN)**
  before you press **Start the room**. Then every network interface listens and computers on your network can join with
  the password. Traffic is plain HTTP and the password is a shared secret, not encryption: allow other computers only on
  a network you trust. Use a local network or a VPN that joins the computers into one network (Tailscale, ZeroTier,
  Radmin VPN). Forwarding the port on a router works too, at your own risk.

**What is shared.** Every edit of a translation (typing, AI translation, autofix, Undo) reaches the others in a second
or two; the latest text of a row wins in the queue, so typing is not one request per key. Another participant's edit
arrives as an unsaved edit: save as usual. It is not on your Undo stack. Two things bypass the room: **Import BMG**
and **Undo Paste** (they write many rows at once); repeat them on each computer or edit the rows.

**Joining.** When you join, rows the room has replace yours (as unsaved edits; your files keep the old text until you
save). Rows you translated that the room does not have are shared with it. A row you changed and did not save, that
the room has in another version, is not overwritten: it becomes a **conflict**. The status bar says how many rows were
taken, shared and in conflict.

**Conflicts.** Every row in the room has a revision. An edit made on an old revision (two people changed the same row
at the same time) is refused by the room, and the bar above the editor shows both versions: **Take theirs** or
**Keep mine** (which sends yours on top).

**Who is where.** The bar above the editor says **Here now:** with the names of others on the same row, and **Last
changed by** with a name and time. The Work Together window lists everyone in the room and where they are;
double-click a name to go there. The status-bar button shows how many are in the room.

**The room's memory.** The host's room writes its rows and the team's counts to `collab_room.json` in the host's
project folder; a room started again on the same project keeps them. **Leave the room** disconnects; when the host
leaves, the room closes for everyone. Name, port and last address (never the password) are remembered in
`~/.picoripi/collab.json`.

## Roles, claims and comments

**Roles.** A role belongs to your room token, not to a computer.

- **Host:** one. The host can make moderators and can give the host role to someone else (**Make host**, after a
  confirmation). The old host becomes a moderator.
- **Moderator:** any number, set by the host.
- **Reviewer:** marks rows approved. Does not change text.
- **Translator:** the role every participant gets at join. Edits and claims rows.
- **Observer:** reads and comments.

| Action | Host | Moderator | Reviewer | Translator | Observer |
|---|---|---|---|---|---|
| Change a row's text | yes | yes | no | yes | no |
| Approve a row | yes | yes | yes | no | no |
| Claim a row or an area | yes | yes | no | yes | no |
| Give, refuse or take away a claim | yes | yes | no | no | no |
| Assign an area to someone | yes | yes | no | no | no |
| Comment; delete your own comment | yes | yes | yes | yes | yes |
| Delete someone else's comment | yes | yes | no | no | no |
| Remove a participant; allow back | yes | yes (not host or moderators) | no | no | no |
| Change a role | any | translator ↔ observer or reviewer only | no | no | no |
| Read the moderator log | yes | no | no | no | no |

**Claims.** Select a row, a file, a block, a folder or a virtual folder ("Shared", "<console> only") in the block tree,
right-click and press **Claim for me**. A row can also be claimed from the bar above the editor (**Claim this row**).

- An area that nobody claimed is granted at once.
- An area that someone else holds becomes a request. The host or a moderator gives it or refuses it.
- A claimed row can be edited only by its owner. Everybody else sees **Claimed by Name** in the bar, and their edit is
  put back.
- Areas nobody claimed need no claim: everybody edits them.
- A claim stays when its owner leaves; the room shows the owner as offline. The owner, a host or a moderator releases it.

**Presence.** When you open a row that someone else is working on, the status bar says "Name is working here." Nothing
is locked.

**Comments.** Comment on a row, a file, a block, a folder, a virtual folder or the whole project: right-click the tree
item and press **Comment…**, or press **Comment…** in the bar above the editor. A comment has its author, the time and
its text. **Resolve** marks it resolved with who and when; press it again to reopen the comment. Everybody in the room
sees the comments. The room keeps them in `collab_room.json` and in `comments.json` in the project folder, so they stay
after the room closes.

**Approval.** A reviewer, a moderator or the host presses **Approve** in the bar above the editor. A later change of the
row's text removes the approval.

**Identity.** Your token for each name is kept on this computer in `~/.picoripi/collab.json` (never the password). Join
with the same name on the same computer and you get your role back. While you are online, another computer cannot join
with your name.

**Removing a participant.** **Remove from room** keeps a participant out until a host or a moderator presses
**Allow back**. Host and moderators cannot be removed.

**The window.** The Work Together window has four tabs under the list of people: **Roles**, **Claims** (with the
requests), **Comments** and **Moderator log** (host only).

**A room without a window.** A room can run on a computer that stays on, without Picoripi's window:

```
python -m core.collab.server --headless --port 8765 --password-file room-password.txt --project-dir "D:\Projects\MyGame" --owner-token-file owner-token.txt
```

The first participant that joins with the token in `owner-token.txt` becomes the host. The process prints one line with
its port and the room id, and runs until you stop it. The room answers only to the room password (for joining) and to
room tokens (for everything else).

**Remote rooms are off by default.** Picoripi connects to a room only when you press **Start the room** or **Join**.
Nothing connects by itself, and no room address is saved for later. The traffic is plain HTTP: use a VPN or a network
you trust.

## Progress page

**Tools → Progress...** counts the open project in the background and opens a page in the browser
(`progress.html` in the project folder; `core/progress_stats.py`):

- a ring with the share of rows translated, rows and source words translated, rows left, rows today, days in a row,
  and the days to the end at the average pace of the last seven working days;
- achievements: 100, 500, 1,000 … translated rows, finished blocks, a streak of three days or more;
- a chart of translated rows by day (one entry a day in `progress_history.json` in the project folder, written each
  time the page is counted);
- the blocks with the most left, with a bar each.

A row counts as translated when its source has text besides tags and its current text is not empty and differs from
the source (the same rule as the editor).

**In a room** the page is served by the host at `http://<host address>:<port>/stats?token=<your room token>` (the **Progress page** button adds the token;
or Tools → Progress), refreshes itself every 30 seconds, and adds the **Team** board: for each participant the source
words and rows they translated first, their edits, and today's words, with medals for the first three, the
**Leader of the day** and how far the second is behind the first. Rows shared at join count for nobody; polishing a
translated row counts as an edit, not as new words. The page shows counts and names only, never text; anyone who can
reach the room's address can open it. Each participant's Picoripi sends the room a fresh project summary when it
joins and then once a minute while edits happen.
