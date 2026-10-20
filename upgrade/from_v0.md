# Upgrading from 0.x

Version 0.x was called TON Token Access Control Bot. Version 1.0 is a rewrite: the data moves from SQLite to Redis,
and a few rules change. You set it up in a new folder next to the old one, so the old bot stays untouched and you can
go back to it.

## What changes

| | 0.x | 1.0 |
|---|---|---|
| Data | SQLite file | Redis |
| No tokens in the admin menu | everyone with a wallet gets in | join requests are declined |
| Jetton minimum | whole tokens, every balance read with 9 decimals | the real decimals of the jetton |
| Kick | removed from the chat | a 5-minute ban, then the user can join again with enough tokens |
| Chat messages | in the language of the user | in `BOT_GROUP_LANGUAGE`, Russian by default |
| Admins | `BOT_ADMIN_ID`, `BOT_DEV_ID` and the admin menu | `BOT_ADMIN_ID` and the admin menu |
| Error reports | to `BOT_DEV_ID` | to `BOT_ADMIN_ID` |
| TON Connect manifest | not checked | checked on start, see [Manifest](#manifest) |

**Moves over:** users and their wallets, chats, tokens, admins from the admin menu, the members the bot let in.

**Does not move:** open bot screens (users send `/start` once) and the holder list, which the first check builds anew.

## Manifest

A wallet signs the connection for the host of the `url` field in the manifest, and the bot checks the signature
against it. On start the bot loads the manifest from `MANIFEST_URL` and stops with an error in the log if:

* the manifest cannot be read;
* it has no `url` field;
* `url` and `MANIFEST_URL` are on different domains.

A 0.x manifest on a JSON hosting with `url` pointing to Telegram does not pass. Use the default manifest:

```env
MANIFEST_URL=https://raw.githubusercontent.com/nessshon/tontokengate-bot/main/assets/tonconnect-manifest.json
```

Or host your own on your domain, with `url` on the same domain:

```json
{
  "url": "https://example.com",
  "name": "My Token Gate",
  "iconUrl": "https://example.com/icon.png"
}
```

## Steps

The commands below take `../token-access-control-bot`, the folder `git clone` made for 0.x, as the folder of the
old bot: put your own path there if you renamed it.

### 1. Stop the old bot

Two bots with one token cannot run at the same time. In the folder of the old bot:

```bash
docker compose down
```

### 2. Get version 1.0

Clone it into a new folder. A `git pull` in the old folder fails on the changed and local files.

```bash
git clone https://github.com/nessshon/tontokengate-bot.git tontokengate-bot
cd tontokengate-bot
```

### 3. Copy the settings and the database

```bash
cp ../token-access-control-bot/.env .env
cp ../token-access-control-bot/app/db/data/database.sqlite .
```

Then check `.env`:

* `MANIFEST_URL`: see [Manifest](#manifest).
* `BOT_DEV_ID` is no longer read. If it was another person, add them in `/admin` after the start.
* The other old keys still work, the unused ones are ignored. Optionally add `TONCENTER_KEY`, see the
  [README](../README.md#environment-variables-reference).

### 4. Move the data into Redis

```bash
docker compose run --rm -v "$PWD/database.sqlite:/app/database.sqlite:ro" bot python -m upgrade.from_v0 database.sqlite
```

`$PWD` is the current folder: Docker takes a file only by its full path. The script reads `database.sqlite` without
changing it and asks Toncenter for the decimals of the jettons 0.x stored without them. It prints what moved:

```text
Moved: users 292, chats 1, tokens 1, admins 0
```

If it prints `Check these tokens`, check or add them in `/admin` after the start. If it stops with an error,
nothing was written: fix what the message says and run it again.

### 5. Start the bot

```bash
docker compose up -d
docker compose logs -f bot
```

### 6. Check in the bot

In `/admin`, check the chats, the tokens and their minimums.

### 7. Clean up

When everything works, delete the old folder and the Redis volume of the old bot.

## Going back

Stop the new bot with `docker compose down` and start the old one in its folder: its database was not changed.
