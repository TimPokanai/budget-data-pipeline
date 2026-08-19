-- One row per category. Thin pass-through today, but the seam where a
-- future grouping (e.g. "needs" vs. "wants") would get added without
-- touching stg_categories or anything downstream.

select
    category_id,
    category_name,
    category_type,
    category_created_at

from {{ ref('stg_categories') }}
