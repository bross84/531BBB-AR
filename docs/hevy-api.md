# Hevy API: verified facts

Source: the live OpenAPI spec embedded in https://api.hevyapp.com/docs/ (swagger-ui-init.js), read 2026-10-05. Spec version 0.0.1. Hevy states the API is only for Hevy Pro users, may change structure without notice, and asks clients not to poll exactly on the hour. Auth header: `api-key`.

## Endpoints

| Path | Methods | Purpose |
|---|---|---|
| `/v1/exercise_templates` | GET, POST | List exercise templates; create a custom one |
| `/v1/exercise_templates/{id}` | GET | One template |
| `/v1/exercise_history/{exerciseTemplateId}` | GET | Every logged set for one exercise (`start_date`, `end_date` filters) |
| `/v1/workouts` | GET, POST | List workouts; create one |
| `/v1/workouts/{id}` | GET, PUT | One workout; update it |
| `/v1/workouts/count` | GET | Total workout count |
| `/v1/workouts/events` | GET | Updates and deletes since a date (`since`), newest first, for keeping a local cache current |
| `/v1/routines`, `/v1/routines/{id}` | GET, POST, PUT | Routines (planned workouts) |
| `/v1/routine_folders`, `/v1/routine_folders/{id}` | GET, POST / GET | Routine folders |
| `/v1/user/info` | GET | Account info |
| `/v1/body_measurements`, `/v1/body_measurements/{date}` | GET, POST / GET, PUT | Body measurements |

No endpoint deletes a workout, routine or exercise. The spec lists no maximum `pageSize`; defaults are 5 (10 for body measurements). The current code requests 100 for templates and 10 for workouts (those maxima are not confirmed by the spec).

## Sets (what Hevy can store)

Workout set (POST body): `type`, `weight_kg`, `reps`, `rpe`, `distance_meters`, `duration_seconds`, `custom_metric`.

- `type` is one of `warmup`, `normal`, `failure`, `dropset`. There is no AMRAP, joker or "working" type.
- `rpe` is one of **6, 7, 7.5, 8, 8.5, 9, 9.5, 10** or null. RPE 5, 5.5, 6.5 and anything below 6 cannot be stored.
- Routine sets have `type`, `weight_kg`, `reps`, `rep_range`, `distance_meters`, `duration_seconds`, `custom_metric` and **no RPE**. A routine exercise has `notes` and `rest_seconds`.
- `exercise_history` entries carry `rpe`, `weight_kg`, `reps`, `set_type` and `workout_start_time` / `workout_end_time`, so history, last-done dates and e1RM seeding can come straight from Hevy.

## Writing a workout

`POST /v1/workouts` body is `{"workout": {...}}`, all keys snake_case:
- required: `title`, `start_time`, `end_time`, `exercises`
- optional: `description`, `is_private`
- each exercise: `exercise_template_id`, `sets[]`, optional `notes`, `superset_id`

Hevy has no "in-progress workout": a workout is posted complete.

## Exercises

Template fields: `id`, `title`, `type`, `primary_muscle_group`, `secondary_muscle_groups`, `equipment`, `is_custom`, `thumbnail_url`. Custom templates are created with `POST /v1/exercise_templates` (`title`, `exercise_type`, `equipment_category`, `muscle_group`, `other_muscles`). Exercise types: `weight_reps`, `reps_only`, `bodyweight_reps`, `bodyweight_assisted_reps`, `duration`, `weight_duration`, `distance_duration`, `short_distance_weight`.

## Gaps in this repo versus the spec (found 2026-10-05)

1. `main.py` write-back builds `{title, startTime, endTime, exercises:[{exerciseTemplateId, sets:[{type, weightKg, reps}]}]}`: not wrapped in `workout`, camelCase instead of snake_case, no `rpe`, and set types `working` / `amrap` / `joker` that Hevy does not accept. By the spec this request would be rejected. It has never been exercised (zero logged sessions; the tests mock the client).
2. Program import accepts exercise names that are not in the cache (stores an empty `hevy_exercise_id` and reports an error).
3. History is never read except `best_e1rm_from_hevy`, which is unused after the June change.
4. `workouts/events` is not used, so the local cache of Hevy data is never refreshed incrementally.
5. RPE below 6 (used in the user's programs) has no Hevy representation.
