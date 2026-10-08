# Backlog

Things we've decided to do later. One feature at a time: pick the one that matters most, build it small, check it on the phone.

## Next features we've talked about

These three belong together: the e1RM and the TM are **two numbers with two jobs**, and today the page works both out from the same set.

- **TM comes only from a set you mark (the `TS`).** A button on each set row. Tapping it makes that set the one that sets the movement's TM (only one per movement; tapping another moves it). TM = that set's e1RM x the TM percentage (default 95%, changeable). The TM is a **stored value** (movement, TS e1RM, TM %, date set) kept in this app's database, because it stays fixed until you mark a new TS (day 3's top set sets next week's TM). Hevy has no field for it. Until a TS is marked, the TM tile says so; it does not guess. *(Decided 2026-10-08. Still to confirm: the TM stays fixed until a new TS is marked, rather than updating after every session.)*
- **e1RM is the best set, not the TM's set.** The e1RM tile and the e1RM basis use the highest e1RM across all working sets (today's best set, else the best set of the last session). This replaces the "heaviest working set with an RPE" rule, which picked the wrong set for a lift where weight drops but RPE climbs (it picked 110 lb x 3 on the press).
- **Don't count high-rep, low-effort sets toward e1RM.** An 8 @5 set stretches the RPE table to about 13 reps to failure and inflates the e1RM. Proposal: two settings with defaults you can change, max reps and minimum RPE; a set counts only if it is within both. Excluded sets are still logged and posted to Hevy, shown dimmed with a note. The TS is exempt. When no set qualifies (accessories like curls), show a labelled rough estimate rather than nothing. Open: the thresholds (e.g. 6 reps, RPE 7?), and whether to allow a per-movement override later. *(Raised 2026-10-08.)*
- **Auto weight step per movement.** Planned weights snap to the nearest 2.5 kg, which is too coarse for micro-loaded lifts like weighted pull-ups (0.5 kg steps). Only matters if you want RPE-driven weights on those movements.
- **Keep our own record of sets.** Hevy cannot store RPE below 6 or 6.5 (it is simply left blank when posting). A local log would keep every RPE as a number so history can use it.

## Nice to have

- **Hevy exercise thumbnails on the picker cards.** Hevy's exercise templates carry a `thumbnail_url`. The app doesn't store it yet (`hevy_exercise_cache` has only id, title, muscle), so it needs a column, a change to the sync, and the image on each square card. *(Asked for 2026-10-08: nice, not needed yet.)*
- **Require the `tests` check before merging** (GitHub: Settings, Branches). A repo setting, not code.

## Using it away from the PC

The gym is the garage on the home network, so none of this blocks use there.

- **Reach the app from outside the home network.** A private VPN such as Tailscale (already on the PC) would do it without exposing the app to the internet.
- **A login.** The app has none, and it can write workouts to the user's Hevy account. Needed before it is reachable from anywhere but the home network.

## Tidy-ups

- **The unused `HEVY_API_KEY` variable** in `docker-compose.yml` and its CasaOS entry. Nothing reads it (the key is stored encrypted in the database).
- **Rename the project** (still 531 BBB-AR in the name, docs, container and database file) once the direction settles.
- **Parked design work:** `docs/notation-spec.md` (program notation, TM/e1RM rules). Not being built now.

## Done recently

- Recent workouts page, workout entry page, own RPE table, per-movement auto weight, kg conversion, picker with recent first, current e1RM from today's best set (2026-10-08).
- Tests run on GitHub for every push and pull request.
- Removed the old Hevy write-back from the legacy session route and `HevyClient.post_workout` (2026-10-08).
- Posts to Hevy as the nearest half kilo (198 lb -> 90 kg); an RPE Hevy can't store is left blank.
