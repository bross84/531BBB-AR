# Backlog

Things we've decided to do later, newest first. One feature at a time: pick the top item that matters, build it small, check it on the phone.

## Nice to have

- **Hevy exercise thumbnails on the picker cards.** Hevy's exercise templates carry a `thumbnail_url`. The app doesn't store it yet (`hevy_exercise_cache` has only id, title, muscle), so it needs a column, a change to the sync, and the image on each square card. *(Asked for 2026-10-08: nice, not needed yet.)*

## Next features we've talked about

- **Mark the set a movement's TM comes from** (the `TS` idea): a button on a set that sets the movement's TM from that set's e1RM, using the TM percentage (default 95%). Today the e1RM and TM are worked out from the last session automatically.
- **Which set defines "last session's e1RM".** The page currently uses the heaviest working set that has an RPE. That is wrong for a lift where weight drops but RPE climbs (it picked 110 lb x 3 on the press). Settle the rule, or let the user mark the set.
- **Keep our own record of sets.** Hevy cannot store RPE below 6 or 6.5 (it is left blank when posting, with a warning on the page). A local log would keep every RPE as a number so history can use it.

## Using it away from the PC

- **Reach the app from the gym.** The phone only reaches the PC on the home Wi-Fi. A private VPN such as Tailscale would fix that without exposing the app to the internet.
- **A login.** The app has none, and it can write workouts to the user's Hevy account. Needed before it is reachable from anywhere but the home network.

## Tidy-ups

- **The old Hevy write-back in `main.py`** (`log_active_block_session` -> `hevy_client.post_workout`) sends the wrong request format and mis-reads Hevy's reply. The new log page does not use it. Remove or fix it. See `docs/hevy-api.md`.
- **Push the branch and open a PR** for `feat/recent-workouts-page`.
- **Rename the project** (still 531 BBB-AR in the name, docs, container and database file) once the direction settles.
- **Parked design work:** `docs/notation-spec.md` (program notation, TM/e1RM rules). Not being built now.
