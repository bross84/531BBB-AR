# Program Notation Spec (DRAFT v0.1)

Status: **draft for review — no code implements the new parts yet.**
Goal: one defined, program-agnostic notation for entering any training program as text. 5/3/1 is just one program written in it. Everything the parser accepts today stays valid.

Examples for Starr / Bridge-style programs below are **illustrative placeholders to show the notation, not the real prescriptions** of those programs.

---

## 1. Principles

1. **Backward compatible.** Every line that parses today keeps parsing to the same result. New syntax only adds.
2. **One shape per line.** A slot line is `Exercise - set-groups [load-source]`. No program-specific line types.
3. **The notation describes the prescription, not the formulas.** Rules like "how e1RM updates" or "how weight progresses" are named by tags; the math lives in code/config, not in the text.
4. **Pure and testable.** The parser stays pure (no DB, no HTTP). Every construct has a test.
5. **Unambiguous.** Each symbol means one thing. The current grammar breaks this in one place (`@` is RPE in `5@5,6,7` but a percentage in `@.65`); this spec fixes it without breaking old input (section 6).

---

## 2. Document structure

```
# comment (ignored)

{block}.{micro}.{day}[: Label]
Exercise Name - <set-groups> [load-source]
Exercise Name - <set-groups> [load-source]
```

- **Header** `{block}.{micro}.{day}`: three integers. Slots under it belong to that day until the next header. (Today a slot may also sit on the header line; that stays valid.)
- **Optional label** after `:` on a header, e.g. `1.1.1: Heavy`. *(new)*
- **Slot line**: `Exercise - groups [tag]`. Split on the **last** ` - `, so names containing ` - ` work.
- **Blank lines and `#` comments** are ignored.

---

## 3. Set groups

A slot has one or more groups joined by ` / `. Each group expands to one or more sets.

### 3.1 Group forms

| Form | Meaning | Status |
|---|---|---|
| `NxR` | N sets of R reps, no intensity (free) | exists |
| `NxR@I` | N sets of R reps at intensity I | exists (RPE only) |
| `R@I1,I2,I3` | one set per intensity, shared reps | exists (RPE only) |
| `R1@I1,R2@I2,R3@I3` | per-set reps and intensity (wave) | exists (RPE only) |
| `NxRJ +p1,p2,..` | Joker sets, jump percentages | exists |
| `NxR@65%` + load source | N sets of R reps at a percent of the baseline, e.g. `5x10@65% e1RM`. General form, not BBB-specific; the old `NxR @.65 e1RM` is a legacy alias that parses to the same thing | alias exists; `%` form new |

### 3.2 Intensity `I` (what follows `@`)

| Form | Meaning | Status |
|---|---|---|
| `@7`, `@7.5` | target RPE (weight derived from the RPE chart) | exists |
| `@75%` | percentage of the slot's **baseline** (the load source, section 4) | **new** |
| `@100kg`, `@225lb` | absolute weight | **new** |
| `@-10%` | percentage drop from the slot's **top set** (back-off) | **new** |

Rule: a bare number after `@` is RPE; a `%` or unit is explicit. This removes the `@.65` ambiguity.

### 3.3 Modifiers

- Trailing **`+`** on the last intensity = last set is AMRAP (`5@5,6,7+`, `1@85%+`). Unchanged.
- **`J`** marks Joker sets (unchanged).
- **`TS`** (new, chosen by user 2026-10-03) marks the **TM set**: the set whose e1RM becomes the next microcycle's TM. Case-insensitive. Goes after the intensity and after any `+`: `3@8TS`, `1@9+TS`. On a `NxR@ITS` group it marks the group's last set. At most one `TS` per slot (parse error if more). No `TS` means the TM does not change. Distinct from the `TM90` source tag.
- **Top set**: the heaviest non-Joker set is the "top set" automatically. `@-10%` back-offs are relative to it. *(new)*

---

## 4. Load source (the trailing tag)

Where the slot's baseline weight comes from. One tag per slot, at the end of the last group.

| Tag | Baseline | Status |
|---|---|---|
| `TM90` | training max x 0.90 | exists |
| `e1RM` | latest e1RM for the exercise | exists |
| `DDP` / `DDP+2.5` | last session's weight, plus increment | exists (stub) |
| *(none)* | free logging — no computed weight | exists |
| `LAST` | last session's top set weight (no increment) | **new, proposed** |

Percent intensities (`@75%`) multiply the baseline. RPE intensities use the baseline as an e1RM and look the percentage up in the RPE chart.

---

## 5. Rules attached to a slot (OPEN — needs your input)

Two things are not expressible yet: **how e1RM updates after logging** and **how weight progresses**. Proposed syntax: trailing `[key=value]` options, so the set groups stay clean.

```
Squat - 5@75%,80%,85%+ TM90 [e1rm=amrap]
Squat - 1@8 / 3x5@-10% e1RM [e1rm=rpe]
Squat - 5x5 LAST [inc=2.5]
```

Candidate keys (all optional, with defaults chosen so existing programs behave exactly as today):

| Key | Values | Default |
|---|---|---|
| `e1rm` | `amrap` (Epley, Joker band), `rpe` (any set with reps + RPE, via chart), `none` | `amrap` where an AMRAP exists, else `none` |
| `inc` | kg added to the baseline per session/week on success | none |
| `round` | rounding step in kg for this exercise (microloading) | `2.5` |
| `joker_band` | ±fraction | `0.05` |

I deliberately have **not** fixed the progression semantics (per session vs. per microcycle, on-success vs. always) — those are the rules I still need to hear from you.

---

## 6. Compatibility map (old -> canonical)

The parser accepts both; reconstruction (editor round-trip) emits the canonical form.

| Old | Canonical |
|---|---|
| `5x10 @.65 e1RM` | `5x10@65% e1RM` (same meaning; legacy alias only, no separate BBB concept in the notation. Internally the `bbb_pct` fields fold into the general percent-of-baseline path, covered by the characterisation tests) |
| `5@5,6,7+` | unchanged |
| `5@5,3@6,1@7+` | unchanged |
| `3x1J +10,15,20` | unchanged |
| `TM90`, `e1RM`, `DDP+2.5` | unchanged |

---

## 7. Examples

**5/3/1 BBB (all valid today)**
```
1.1.1
Squat - 5@5,6,7+ / 3x1J +10,15,20 TM90
Squat - 5x10 @.65 e1RM
Lying Leg Curl - 5x10
```

**Ramped 5x5 with a weekly increment (illustrative)**
```
1.1.1: Heavy
Squat - 5@50%,62%,75%,87%,100% LAST [inc=2.5]
1.1.2: Light
Squat - 4@50%,62%,75%,80% LAST
```

**RPE top set + back-offs (illustrative)**
```
1.1.1
Squat - 1@8 / 3x5@-10% e1RM [e1rm=rpe]
```

---

## 8. Decisions made

1. **Ramps / intensity style (2026-10-03):** RPE is the primary way to write intensity, one RPE per set: `5@6,7,8` = three sets of 5 at RPE 6, 7, 8 (Starr day 1). `3x5@7` (same RPE every set) also works. Percent and absolute-weight forms stay in the spec as optional extras.
2a. **Within-session re-planning (2026-10-03):** for RPE slots, each logged set (weight, reps, actual RPE) updates the e1RM, and the *next set's* planned weight is recomputed from the updated e1RM at its own target RPE. NOT implemented today: session weights are currently fixed at session load. Needs a frontend recompute and a rule for which sets count (e.g. ignore a set with no actual RPE).
2. **e1RM update (2026-10-03):** no stated preference, so all four behaviours stay available per slot (`amrap`, `rpe`, fixed increment, manual). Defaults: slots with an AMRAP set keep `amrap` (5/3/1 unchanged); RPE slots default to `rpe`; free slots do nothing.

3. **Units (2026-10-03):** weights are kg (plates are kg) and stored as kg, rounded to 2.5 kg. Every weight is shown with its lb equivalent beside it; e1RM is shown in lb (matches the user's spreadsheet). Text may use `kg` or `lb` suffixes; a bare number is kg.
4. **Real-world shape (from user's spreadsheet, 2026-10-03):** a lift is typically 5 sets of 5 where the first sets are a ramp with no RPE (weight only) and only the last 1-2 sets carry a target RPE (e.g. 3 ramp sets, then RPE 7 and 8). e1RM is computed on the RPE sets only. This already parses today as `3x5 / 5@7,8 e1RM` (free group + RPE group).

5. **Current program shape (user's Micro 3 sheet, 2026-10-03):** main lifts and variations are RPE-prescribed, each with its own e1RM: `5@6,7,8`, `8@5,6,7`, `5@6,3@7,1@8`, and top sets plus a back-off (`5@6,5@7,3@8,8@6`). All of these parse today. Free sets (e.g. Pendlay row `4x5`) have typed weights, pre-filled from last session (default, not yet confirmed). Actual RPE is logged and can differ from plan (7.5, 8.5). A TM per main lift (Squat/Bench/Deadlift/Press) is shown at the top of the microcycle.
6. **Does NOT parse today (corrected by user, 2026-10-03):** GPP day comes from the BBM Bridge template: 30 min steady-state cardio, modality varies (row or walk), so it is a duration, not sets x reps. Dips and Incline DB Curl are either myo-reps or density blocks (5 min, 6-10 reps or failure). Pull-ups are `3x5 / 1x3 / 1x8` (parses today as groups) and follow the "BS Method" = Bill Starr 5x5 shape (ramp of 5s, a heavier set of 3, a lighter back-off set of 8). The same shape appears in the RPE lifts as `5@6,5@7,3@8,8@6`. The weekly progression rule is still unknown. Bare `TM` (no number) is also invalid; today the tag is `TM90`.

7. **TM progression (user, 2026-10-03):** the progression is the TM update. The top set of 3 from Day 3 sets next microcycle's TM; for the 5/3/1+ lift the Day 3 AMRAP does the same. No fixed weekly increment is used. SUPERSEDED by decision 10: the percentage comes from the TM tag, not a per-lift factor. The sheet shows Deadlift day-3 e1RM 407 vs TM 405, but Squat 357 vs TM 316 and Bench 276 vs TM 257; those TMs may predate this day.
9. **Which set drives the TM (user, 2026-10-03):** Squat and Bench: the fixed top set of 3 at RPE 8 (e1RM via the RPE chart). Deadlift: the Day 3 AMRAP, run up to RPE 9, so the reps achieved decide the number (`1@9+`). User then pointed out this will not always be the case, so the TM set is designated explicitly with a `TS` marker (section 3.3), not inferred.

8. **Pull-up progression (user, 2026-10-03):** linear, small (microloaded) weight added each week to the Starr-shape sets `3x5 / 1x3 / 1x8`. Uses the `[inc=...]` option. Consequence: the global 2.5 kg rounding rule must become a per-exercise rounding step (default 2.5 kg, overridable to e.g. 0.5 or 1.0 kg for microloaded lifts), otherwise small increments round away.

10. **TM definition (user, 2026-10-03):** a TM is a max that is a percentage reduction of the e1RM. e1RM 200 with `TM90` gives TM 180. The e1RM itself is never reduced or overwritten by this; the TM is a separate number. TMs apply to main movements only; every other exercise (variations, accessories) plans from its own e1RM history. Where the percentage lives (tag vs block) and whether the TM is frozen at the `TS` set or recomputed live is part of bookmark A.
11. **Own history (user, 2026-10-03):** each exercise, including variations, plans from its own e1RM history, not its parent lift's.
12. **No real data exists (user, 2026-10-03):** the app has never been used for a real session, so there is nothing to migrate; the schema may change freely.
13. **Non-set lines (user, 2026-10-03):** cardio is not logged and is out of scope for now. Myo-reps and density blocks are logged like any other exercise (normal weight/reps sets, open-ended count). Proposed syntax: `free` = no prescribed set count, optional `[note]` text shown on the day, e.g. `Dips - free [5 min density block, 6-10 reps or failure]`. The user's own log shorthand for a myo-rep set is weight-first: `20x15 20x5 20x5x3 20x3x2 20x2` (weight x reps [x sets]); note this is the opposite order to the prescription form `NxR` (sets x reps).
14. **Build order (delegated to Claude, 2026-10-03):** (1) parser changes, (2) session engine (e1RM from any RPE set, in-session re-planning, TM), (3) UI, (4) schema cleanup and rename. Spec review before each step, one small commit per change.

15. **Round 3 answers (user, 2026-10-03):** quick-entry log shorthand wanted, but after the session engine (bookmark C). Dates stay out of the program text; the UI should instead show "last done" dates from the logged_at timestamp on each logged set (not shown anywhere today). Day labels (`1.3.4: Label`) stay optional and low priority. Cross-day references: not needed now, maybe in future, deferred. Project rename: at the end of step 4.
16. **RPE chart check (2026-10-03):** the app's chart (`data/rpe_chart.csv`) with `e1RM = weight / chart% x 2.2046 lb` reproduces 20 of 26 e1RMs in the user's sheet within 1.5 lb; the other 6 differ by 1.6-2.6 lb (e.g. squat 132.5 kg x5 @8: app 351.9, sheet 354). The sheet probably uses a slightly different table.

## Bookmarked discussions (not decided; come back to these)

- **A. TM / block-level baseline.** How to say "this whole block plans from the TM". Candidate: a block line `1 [base=TM90]` with slot tags overriding. Also unresolved: where the percentage lives (tag vs block), whether the TM is a snapshot frozen at the `TS` set or recomputed live, and whether a TM change applies from the next microcycle only.
- **B. In-session e1RM rule.** Which e1RM feeds the next set in a session (latest set, average, highest) and what is stored at the end. User wants a detailed answer here; the sheet shows e1RMs 343, 352, 354 across a 6/7/8 RPE ramp, each next set planned from the one before.
- **C. Quick-entry log shorthand.** Whether the workout UI should accept `weight x reps [x sets]` strings (see decision 13).

## 9. Open decisions

1. **Percent-of-baseline vs. percent-of-top-set** for ramps. The Starr example above treats the ramp as percentages of the top set's weight, which `LAST` supplies. Is that how you think about it?
2. **Light/medium days as a function of the heavy day** (e.g. 80% of Monday's top set). Needs a cross-day reference (`@80% of 1.1.1`?) or can the numbers just be typed per day?
3. **Progression semantics** for `inc` and `e1rm=rpe`: your rules.
4. **Units**: the DB stores kg. Accept `lb` in the text and convert, or kg only?
5. **Day label syntax** (`1.1.1: Heavy`) — fine, or different?
