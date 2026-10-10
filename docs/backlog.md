# Backlog

Things we've decided to do later. One feature at a time: pick the one that matters most, build it small, check it on the phone.

## Next features we've talked about

These belong together: the e1RM and the TM are **two numbers with two jobs**, and today the page works both out from the same set.

- **TM comes only from a set you mark (the `TS`).** A button on each set row. Tapping it makes that set the one that sets the movement's TM (only one per movement; tapping another moves it). TM = that set's e1RM x the TM percentage (default 95%, changeable). The TM is a **stored value** (movement, TS e1RM, TM %, date set) kept in this app's database, because it stays fixed until you mark a new TS (day 3's top set sets next week's TM). Hevy has no field for it. Until a TS is marked, the TM tile says so; it does not guess. *(Decided 2026-10-08. Still to confirm: the TM stays fixed until a new TS is marked, rather than updating after every session.)*
- **Parked: keep noisy sets out of the e1RM.** The e1RM is the highest e1RM across the sets, so one inflated set wins (the RPE table has to guess the reps left on a low-RPE set, e.g. an 8 @5 gives about 13 reps to failure). Decided 2026-10-08 to leave it until the e1RM is used to load weights; once the TS sets the TM it is only a metric. Preferred rule when it comes back: a set counts only if its RPE is 7 or higher (one constant in `exercise_state.py` and `log.html`; the last-set feature stays exempt). On the 19 Sep squat session that gives 332 (292 x 3 @8) instead of 343 (265 x 5 @6), the more trustworthy figure. Rejected: a rep cap (it would drop a real 9 @9.5 AMRAP) and a set-to-set window (it needs peer sets, so it can't judge a lone set, and a ramping session can mislead it). Bring it back if the e1RM tile looks too high.
- **Keep our own record of sets.** Hevy cannot store RPE below 6 or 6.5 (it is simply left blank when posting). A local log would keep every RPE as a number so history can use it.

## Nice to have

- **Hevy exercise thumbnails on the picker cards.** Hevy's exercise templates carry a `thumbnail_url`. The app doesn't store it yet (`hevy_exercise_cache` has only id, title, muscle), so it needs a column, a change to the sync, and the image on each square card. *(Asked for 2026-10-08: nice, not needed yet.)*
- **Require the `tests` check before merging** (GitHub: Settings, Branches). A repo setting, not code.

## Using it away from the PC

The gym is the garage on the home network, so none of this blocks use there.

- **Reach the app from outside the home network.** A private VPN such as Tailscale (already on the PC) would do it without exposing the app to the internet.
- **A login.** The app has none, and it can write workouts to the user's Hevy account. Needed before it is reachable from anywhere but the home network.

## Tidy-ups

- **Rename the project** (still 531 BBB-AR in the name, docs, container and database file) once the direction settles.
- **Parked design work:** `docs/notation-spec.md` (program notation, TM/e1RM rules). Not being built now.

## Done recently

- Recent workouts page, workout entry page, own RPE table, per-movement auto weight, kg conversion, picker with recent first, current e1RM from today's best set (2026-10-08).
- The e1RM from the last session now uses the best set (highest e1RM), not the heaviest; today's best set already did (2026-10-08).
- Rounding step per movement: `step_kg` is stored per movement (default 2.5 kg) and planned weights round to it, so micro-loaded lifts like weighted pull-ups can use 0.5 kg (2026-10-08).
- Tests run on GitHub for every push and pull request.
- Removed the old Hevy write-back from the legacy session route and `HevyClient.post_workout` (2026-10-08).
- Removed the unused `HEVY_API_KEY` variable and its CasaOS entry from `docker-compose.yml` (2026-10-08).
- Posts to Hevy as the nearest half kilo (198 lb -> 90 kg); an RPE Hevy can't store is left blank.
