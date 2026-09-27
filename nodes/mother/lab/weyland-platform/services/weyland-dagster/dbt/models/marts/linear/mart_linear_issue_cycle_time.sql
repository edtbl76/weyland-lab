-- Mart: per completed Linear issue, lead time (created → completed) and cycle time (first started → completed) — the
-- B185 time-tracking input. Most lab issues go Backlog → Done without a "started" state, so lead time is always
-- present and cycle time only where work was actually started (the issue's startedAt, else its first transition into
-- a `started`-type state from history). Kind comes from the single-select `Kind` label group.
{{ config(materialized='table') }}

with issues as (
    select
        id, identifier, title, project_id, priority, label_ids,
        from_iso8601_timestamp(created_at)   as created_at,
        from_iso8601_timestamp(started_at)   as started_at,
        from_iso8601_timestamp(completed_at) as completed_at
    from {{ source('linear', 'issues') }}
    where completed_at is not null
),

first_started as (
    select sc.issue_id, min(from_iso8601_timestamp(sc.created_at)) as first_started_at
    from {{ source('linear', 'issue_state_changes') }} sc
    join {{ source('linear', 'workflow_states') }} ws on ws.id = sc.to_state_id
    where ws.type = 'started'
    group by sc.issue_id
),

kinds as (
    select i.id as issue_id, max(l.name) as kind
    from {{ source('linear', 'issues') }} i
    cross join unnest(split(i.label_ids, ',')) as t (label_id)
    join {{ source('linear', 'issue_labels') }} l on l.id = t.label_id
    join {{ source('linear', 'issue_labels') }} g on g.id = l.parent_id and g.name = 'Kind'
    group by i.id
)

select
    i.id                                                            as issue_id,
    i.identifier,
    i.title,
    p.name                                                          as project,
    i.priority,
    k.kind,
    i.created_at,
    coalesce(i.started_at, fs.first_started_at)                     as started_at,
    i.completed_at,
    date_diff('minute', i.created_at, i.completed_at) / 60.0        as lead_time_hours,
    case
        when coalesce(i.started_at, fs.first_started_at) is not null
        then date_diff('minute', coalesce(i.started_at, fs.first_started_at), i.completed_at) / 60.0
    end                                                             as cycle_time_hours
from issues i
left join first_started fs on fs.issue_id = i.id
left join kinds k on k.issue_id = i.id
left join {{ source('linear', 'projects') }} p on p.id = i.project_id
