# Backlog

Things we've decided to do later. One feature at a time: pick the one that matters most, build it small, check it on the phone.

## Next features we've talked about

- **Parked: keep noisy sets out of the e1RM.** The e1RM is the highest e1RM across the sets, so one inflated set wins (the RPE table has to guess the reps left on a low-RPE set, e.g. an 8 @5 gives about 13 reps to failure). Decided 2026-10-08 to leave it until the e1RM is used to load weights; once the TS sets the TM it is only a metric. Preferred rule when it comes back: a set counts only if its RPE is 7 or higher (one constant in `exercise_state.py` and `log.html`; the last-set feature stays exempt). On the 19 Sep squat session that gives 332 (292 x 3 @8) instead of 343 (265 x 5 @6), the more trustworthy figure. Rejected: a rep cap (it would drop a real 9 @9.5 AMRAP) and a set-to-set window (it needs peer sets, so it can't judge a lone set, and a ramping session can mislead it). Bring it back if the e1RM tile looks too high.
- **Our own number pad instead of the on-screen keyboard.** In landscape the system keyboard covers about half the screen. A compact pad in the page (digits, a decimal point, Next and Done) would be about a third of the height. The inputs would use `inputmode="none"` so the system keyboard stays away, and the pad would dock at the bottom and move between the weight, reps and RPE boxes. Decided 2026-10-11 to do it later; for now the page hides the bottom bar while you type and scrolls the box above the keyboard. *(Asked about 2026-10-11: future.)*
- **Per-lift RPE charts, alongside the current one.** Decided 2026-10-15. Each lift gets an optional chart of its own, starting as a copy of the current one, with a setting per lift for which chart it uses (the current one stays the default). Then a read-only report of how your sets compare with the chart, and finally suggested corrections you approve. Anchors: the daily 1@8 (marked as the TS), AMRAPs and RPE 10 sets. Build in that order, one at a time.
- **The marked TS sets the TM at once.** Today a TS only sets the TM when the workout is saved, so a 1@8 done first doesn't change that session's planned weights (the e1RM basis does follow it). Make the TM tile use today's marked TS straight away.

## Nice to have

- **Hevy exercise thumbnails on the picker cards.** Hevy's exercise templates carry a `thumbnail_url`. The app doesn't store it yet (`hevy_exercise_cache` has only id, title, muscle), so it needs a column, a change to the sync, and the image on each square card. *(Asked for 2026-10-08: nice, not needed yet.)*
- **Require the `tests` check before merging** (GitHub: Settings, Branches). A repo setting, not code.

## Using it away from the PC

The gym is the garage on the home network, so none of this blocks use there.

- **Reach the app from outside the home network.** A private VPN such as Tailscale (already on the PC) would do it without exposing the app to the internet.
- **A login.** The app has none, and it can write workouts to the user's Hevy account. Needed before it is reachable from anywhere but the home network.

## Tidy-ups

- **Parked design work:** `docs/notation-spec.md` (program notation, TM/e1RM rules). Not being built now.

## Done recently

- Estimated RPE cells from your own data (2026-10-16): the `/rpe-charts` tabs no longer measure sets against the TS's table-derived e1RM. Each workout gets its own e1RM fitted from its sets (every set counts, the TS included), a cell is the average share of the sets at that RPE and reps, and once a lift has 15 sets from 3 workouts spanning 4 reps of effort the cells you haven't hit are interpolated from the sets at nearby efforts (a set of 5 at RPE 7 is as hard as 8 at RPE 10, so they inform the same curve), marked `est`, never from the table in use, and empty past the hardest and easiest effort logged. The overall scale is only fixed up to a straight-line fit and a true RPE 10 single = 100%, so a tested max per lift would be the one real pin. Thresholds are constants in `rpe_observed.py` (`MIN_SETS`, `MIN_WORKOUTS`, `MIN_K_SPAN`). Still to come: per-lift editable charts and choosing which one a lift uses.
- Table-free curve fit on `/rpe-charts` (2026-10-16): measuring sets against the TS's e1RM is circular (that e1RM comes from the table's own value at the TS's cell), so each lift tab also shows a fit that uses only the table's structure: k = reps + reps in reserve, a straight line in k, a true RPE 10 single = 100%, one e1RM per workout. Every set counts, the TS included. The TS also gets its own labelled cell on the grid. Refinements to consider (from the RTS article on customizing an RPE chart, https://store.reactivetrainingsystems.com/blogs/advanced-concepts/customizing-your-rpe-chart): the curve is steeper near the top (their example loses 5 points per rep from 1 to 4 reps, 3.75 from 4 to 8, about half that beyond), so a two-segment fit with a knot near 4 reps once there is data across it; and an optional real tested max per lift (a meet or gym 1RM) as the one pin that is not an RPE judgement.
- RPE tables page (2026-10-16), `/rpe-charts`: tabs for squat, bench and deadlift (the Hevy exercises from the Progress page) plus General (the table in use, shared by every other movement); each lift tab is a grid of RPE by reps filled in from your own logged sets, as a share of the lift's newest TS e1RM, next to the table in use (cell colour and gap show how far off it is, n shows how many sets it rests on). Read-only; the per-lift charts to edit and switch between are still to come. Warm-ups, drop sets and the TS itself are left out.
- The TS pins the e1RM (2026-10-16): a set marked TS and ticked done, or else the latest saved TS, is the movement's e1RM (tile marked "TS"), and no other set outranks it, however high its own e1RM comes out. Only a movement with no TS mixes in its best set. The TM still changes only when the workout is saved. Open point: once a movement has a saved TS there is no way back to the best-set e1RM short of clearing its TS history.
- Rest time per exercise and a much louder alarm (2026-10-16): each exercise has its own rest time (a chip on its card, stored per movement in `exercise_refs.rest_sec`), the bar picker is now the default for exercises without one, and the end-of-rest alarm is square waves at full volume for about 3 seconds.
- Our own record of sets (2026-10-15): every set of a workout saved to Hevy is also kept in the `logged_sets` table with the RPE as typed (Hevy drops anything below 6 or 6.5), the set type, whether it was the TS, and the Hevy workout id. Only starts from the day it was deployed; Hevy history is not backfilled yet.

- Renamed the project to Rackbook (2026-10-15): page titles, docs, container, volume (`rackbook-data`) and database file (`rackbook.db`). `plan.md` is a history log and keeps the old name.

- Recent workouts page, workout entry page, own RPE table, per-movement auto weight, kg conversion, picker with recent first, current e1RM from today's best set (2026-10-08).
- The e1RM from the last session now uses the best set (highest e1RM), not the heaviest; today's best set already did (2026-10-08).
- Rounding step per movement: `step_kg` is stored per movement (default 2.5 kg) and planned weights round to it, so micro-loaded lifts like weighted pull-ups can use 0.5 kg (2026-10-08).
- The TS: the toggle in front of each set cycles set, warm-up, TS, failure, drop set. A TS set sets the movement's TM (its e1RM x the TM %) when the workout is saved to Hevy, and the TM holds until the next TS is saved. Every TS is kept in `training_max_history`. Until a movement has a TS, the TM falls back to the last session's best set. A block feature that picks the TS by itself is still to come (2026-10-09).
- Weights are entered and posted in kg, with the lb beside them as a reference; a kg/lb switch in the header flips which one you type in (for a commercial gym), each movement has a rounding step in both units, and a Previous column shows what you did on each set last time (2026-10-11).
- Warm-up sets on request: a "+ Warm-up sets" button builds them from last session's warm-ups scaled to today's first working weight (or a 40/55/70/85% ladder), and never by itself (2026-10-11).
- Plate loader under each exercise's sets, modelled on the Barbell Loader: the plates for each end of the bar drawn in the usual colours, for the next set you have not ticked or one you pick; the bar (20 kg barbell, SSB, buffalo, neutral grip, Arch Nem., custom) and the chains are remembered for each movement. Kg plates 25 to 1.25; in lb mode a 45 lb bar and 45 to 2.5 lb plates (2026-10-11).
- Tests run on GitHub for every push and pull request.
- Removed the old Hevy write-back from the legacy session route and `HevyClient.post_workout` (2026-10-08).
- Removed the unused `HEVY_API_KEY` variable and its CasaOS entry from `docker-compose.yml` (2026-10-08).
- Posts to Hevy as the nearest half kilo (198 lb -> 90 kg); an RPE Hevy can't store is left blank.
