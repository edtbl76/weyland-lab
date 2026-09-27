-- Mart: weekly flow of completed Linear issues — throughput and lead-time distribution per ISO week. This is the
-- Linear side of the EMA-172 DORA picture (change lead time); deployment frequency comes from Port deployment
-- entities, not from here.
{{ config(materialized='table') }}

select
    date_trunc('week', completed_at)                       as week_start,
    count(*)                                               as issues_completed,
    approx_percentile(lead_time_hours, 0.5)                as lead_time_p50_hours,
    approx_percentile(lead_time_hours, 0.85)               as lead_time_p85_hours,
    count(cycle_time_hours)                                as issues_with_cycle_time,
    approx_percentile(cycle_time_hours, 0.5)               as cycle_time_p50_hours
from {{ ref('mart_linear_issue_cycle_time') }}
group by date_trunc('week', completed_at)
