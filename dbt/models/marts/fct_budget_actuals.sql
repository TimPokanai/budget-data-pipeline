-- One row per (category, month): planned amount, actual amount (summed
-- from fct_transactions), and their difference. This is the direct
-- replacement for the source workbook's `Monthly Budget Summary` sheet
-- and its SUMIFS/Difference formulas -- the open question Phase 2 left
-- for this phase to resolve (see docs/phase-3-transformation.md).

with budgets as (

    select * from {{ ref('stg_budgets') }}

),

categories as (

    select * from {{ ref('dim_categories') }}

),

actuals as (

    select
        category_id,
        txn_month as budget_month,
        sum(amount) as actual_amount

    from {{ ref('fct_transactions') }}
    group by 1, 2

),

-- Full outer join, not a plain join off either side: a category with a
-- plan but zero spend this month, and a category with spend but no plan
-- entered, both need to surface in the same shape. A left join from
-- budgets would silently drop the second case; the sheet's SUMIFS never
-- had to handle it because Planned was always the driving list by
-- construction, but a general-purpose model can't assume that.
combined as (

    select
        coalesce(b.category_id, a.category_id)     as category_id,
        coalesce(b.budget_month, a.budget_month)    as budget_month,
        b.planned_amount,
        coalesce(a.actual_amount, 0)                as actual_amount

    from budgets b
    full outer join actuals a
        on  a.category_id  = b.category_id
        and a.budget_month = b.budget_month

)

select
    c.category_id,
    c.category_name,
    c.category_type,
    combined.budget_month,
    -- Left as NULL, not coalesced to 0: "no plan entered" and "planned to
    -- spend exactly $0" are different facts worth keeping apart.
    combined.planned_amount,
    combined.actual_amount,
    combined.actual_amount - coalesce(combined.planned_amount, 0) as difference_amount

from combined
join categories c
    on c.category_id = combined.category_id

order by combined.budget_month, c.category_name
