-- Staging: BRFSS 2011-present prevalence. Select + cast the columns the state-health mart needs; the
-- break-out / response filtering lives in the mart (business logic).
with src as (
    select * from {{ source('datasets_health', 'brfss_prevalence') }}
)
select
    cast(year as integer) as year,
    cast(locationabbr as varchar) as state,
    cast(topic as varchar) as topic,
    cast(response as varchar) as response,
    cast(break_out as varchar) as break_out,
    cast(data_value as double) as data_value
from src
where year is not null
  and locationabbr is not null
  and data_value is not null
