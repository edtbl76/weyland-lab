-- Mart: progress per Linear initiative — the B119.1 OKR view (objective = initiative). Counts the issues of every
-- project in the initiative by workflow-state type, the open High-priority work, percent complete (canceled issues
-- excluded from the denominator), and the date of the latest check-in (initiative update).
{{ config(materialized='table') }}

with issue_state as (
    select i.id, i.project_id, i.priority, ws.type as state_type
    from {{ source('linear', 'issues') }} i
    left join {{ source('linear', 'workflow_states') }} ws on ws.id = i.state_id
),

last_check_in as (
    select initiative_id, max(from_iso8601_timestamp(created_at)) as last_check_in_at
    from {{ source('linear', 'initiative_updates') }}
    group by initiative_id
)

select
    n.id                                                                            as initiative_id,
    n.name                                                                          as initiative,
    n.status,
    n.health,
    n.target_date,
    count(distinct ip.project_id)                                                   as projects,
    count(s.id)                                                                     as issues_total,
    count(case when s.state_type = 'completed' then 1 end)                          as issues_completed,
    count(case when s.state_type in ('canceled', 'duplicate') then 1 end)           as issues_canceled,
    count(case when s.state_type not in ('completed', 'canceled', 'duplicate')
                    and s.priority = 2 then 1 end)                                  as open_high,
    round(100.0 * count(case when s.state_type = 'completed' then 1 end)
          / nullif(count(s.id) - count(case when s.state_type in ('canceled', 'duplicate') then 1 end), 0), 1)
                                                                                    as pct_complete,
    max(c.last_check_in_at)                                                         as last_check_in_at
from {{ source('linear', 'initiatives') }} n
left join {{ source('linear', 'initiative_projects') }} ip on ip.initiative_id = n.id
left join issue_state s on s.project_id = ip.project_id
left join last_check_in c on c.initiative_id = n.id
group by n.id, n.name, n.status, n.health, n.target_date
