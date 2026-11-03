# PRD: per-store wake schedules for the store scaler

## Context
The existing store-scaler service (services/store-scaler, a FastAPI app already in production) wakes and parks
data stores on request. Today a store is either awake or parked until someone changes it.

## Change
Add an optional wake schedule per store (for example "weekdays 08:00-18:00 NY"), read from the service's existing
ConfigMap. Outside the window the scaler parks the store; inside it wakes it. Existing manual wake/park calls keep
working and override the schedule until the next window boundary.

## Acceptance
- A store with a schedule is awake inside its window and parked outside it.
- A manual call overrides the schedule until the next boundary.
- A store with no schedule behaves exactly as today.

This is a one-time change; we don't expect to keep extending the scheduler afterwards. One person builds it.
