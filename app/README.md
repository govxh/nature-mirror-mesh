# Nature-Mirror Mesh — tiny app (v1)

A tiny offline-first chat app built on the project's proven stack
(Reticulum + LXMF). One device runs everything: the app, and a local
**Post Office** (an LXMF propagation node) that holds messages for
people who are offline and hands them over when they log in — the same
store-and-forward pattern the full mesh uses, shrunk to one phone.

**Status:** v1, built for testing. Single device, loopback only.
No internet is used or needed. No radio (yet).

## Your account: 2 words

- Your private key is **just 2 words you choose** (e.g. `apple river`).
- The account identity is derived from them deterministically
  (`SHA-512` of the two words → Reticulum identity), so the **same 2
  words always restore the same account and the same unique ID**, on
  any device.
- Your **unique ID** (32 hex characters) is your address: give it to
  friends, they add it as a contact, and messages they send while you
  are offline wait for you at the post office.

> ⚠️ **Honesty box:** a 2-word key is *weak* — it is a testing
> convenience so the restore-by-key flow is easy to try. Anyone who
> guesses your 2 words owns your account. A later version will use a
> 12-word phrase. Do not use v1 for anything valuable.

## Run it on Android (Termux)

1. Install **Termux** (from F-Droid or GitHub — the Play Store version
   is outdated).
2. In Termux:
   ```sh
   pkg update && pkg install python git
   pip install rns lxmf
   ```
   If `pip install rns` fails while building `cryptography`, install
   the prebuilt package first: `pkg install python-cryptography`,
   then re-run the pip command.
3. Get the app:
   ```sh
   git clone https://github.com/govxh/nature-mirror-mesh
   cd nature-mirror-mesh/app
   ```
   (or copy the `app/` folder onto the phone any other way).
4. Start it:
   ```sh
   sh nmm.sh
   ```
   This starts the Post Office in the background (once) and then the
   app in the foreground. Keep the Termux session alive while you use
   the app (a Termux notification / wake-lock helps:
   `termux-wake-lock`).
5. Open **http://127.0.0.1:8899** in the phone's browser.

## Run it on a PC

```sh
python3 -m venv venv && venv/bin/pip install rns lxmf   # or your lab venv
cd app
PYTHON=../lab/venv/bin/python sh nmm.sh    # or plain: sh nmm.sh
```
Then open http://127.0.0.1:8899.

## The 5-step test (try this first)

This is the exact flow the automated test (`test_app_flow.py`)
verifies:

1. Create account 1 with 2 words (e.g. `apple river`). Note your ID.
2. **Log out / clear data.** Create account 2 with 2 *different* words
   (e.g. `tiger moon`). It gets a different ID.
3. In account 2, add account 1's ID as a contact and send it a
   message. The message status becomes **stored at post office** —
   account 1 is "gone", yet the message is safe.
4. Log out. Log back into account 1 **using only its 2 words**. The
   *same ID* comes back, and the message from account 2 is waiting.
5. Reply to account 2, log out, log back into account 2 — the reply
   is there.

**The real offline proof:** turn **airplane mode ON** and repeat.
Nothing in this app can use the internet, so with airplane mode on,
delivery can only have happened locally — that is the proof it works
without any net.

## Files

| File | What |
|---|---|
| `nmm.sh` | One-command launcher (post office + app). |
| `nmm_app.py` | The app: stdlib web UI + per-login RNS/LXMF backend. |
| `postoffice.py` | The Post Office: local LXMF propagation node. |
| `test_app_flow.py` | Automated 5-step acceptance test (see `lab/results/APP_TEST.md`). |
| `data/` | Runtime data (created). `data/postoffice/` = post office identity + message spool (never touched by logouts). `data/users/<id>/` = your local contacts, chat history and LXMF state. `data/sessions/` = ephemeral per-login files, deleted on logout. |

## How it works (one paragraph)

Sending uses LXMF's *propagated* delivery method: your backend hands
the encrypted message to the post office
(`LXMRouter.set_outbound_propagation_node` + propagation), the post
office stores it, and the recipient's backend downloads it on login
(`LXMRouter.request_messages_from_propagation_node`). The post office
is also a Reticulum transport node, so it can answer "what is the
public key for this ID?" for contacts that are currently offline.
Everything runs over loopback TCP on the one device — which is exactly
the post-office/relay role a real node will play in the wider mesh.
