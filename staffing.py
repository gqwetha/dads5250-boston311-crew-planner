"""
Crew planning and cost model for the Boston 311 hackathon project.

No model and no LLM anywhere in this file. Crew planning is arithmetic over a
demand forecast, and keeping it here rather than in notebook cells means the
sensitivity runs call the same code as the baseline run.

THE RULES, as the problem sets them
-----------------------------------
21 working days per month. A crew clears CAPACITY_PER_DAY requests per day.
Hiring takes 1 month of lead time. A crew ordered in month t starts in t+1.
Releasing takes 1 month of notice and costs 25% of annual salary, and the crew
is paid through the notice month. Parks alone may take seasonal crews from
April through October at 1.3x monthly cost, with no hiring delay and no
release cost.

A request not closed by its target date costs 20 USD. Once it passes 30 days
beyond target it costs a further 100 USD.

HOW THE LEAD TIME IS ENFORCED
-----------------------------
A plan is 12 crew counts per department. The change between month t and t+1 is
a decision taken in month t, which already satisfies a 1 month lead for hiring
and a 1 month notice for release: the crew count rises or falls one month after
the decision, and the departing crew is paid through month t.

January is the exception. Changing January's count would mean a decision taken
in December 2024, outside the planning horizon. Every policy starts at
START_CREWS and the first change a plan can make takes effect in February.

HOW OVERDUE IS COUNTED
----------------------
A monthly plan can only make a request late if its target falls inside the
month. Target windows differ by an order of magnitude between departments:
PWDx 2 days, BTDT 1 day, ISD a mixture whose short end is near 18 days, PARK
roughly half its volume at 365 days.

Two numbers per department come out of the 311 data and into this file:

    CRITICAL_SHARE     the share of a department's requests whose target falls
                       within 30 days. The rest run on horizons of 90, 120, 365
                       or 720 days and cannot go late inside this plan.
    CRITICAL_WINDOW    the typical target window in days among that share.

From those, the work a department can leave waiting without anything going late is

    allowed_backlog = monthly_capacity * (CRITICAL_WINDOW / 21)

which is how much work clears inside the target window at current capacity.

Backlog ages in monthly buckets and is worked oldest first. Each cohort records
how many of its requests were counted overdue. A request is charged the
20 USD once, in the month it misses its target, and the 100 USD once, if that
same request is still unworked when it passes 30 days beyond target.

LONG_OVERDUE_AGE is 2 months. 30 days past a target of 1 to 18 days falls
between 31 and 48 days, which is more than 1 month of waiting and less than 2.
Monthly buckets cannot resolve that, and 2 is the first whole month boundary
past it, which charges the 100 USD penalty no earlier than it is due.

WHAT THIS FILE DOES NOT CLAIM
-----------------------------
It does not predict what Boston's on-time rate would have been. Under these
rules requests go overdue when capacity falls short; across 2023 and 2024
on-time rates do not move with load, and at PWDx they move against it. This
answers which crew schedule minimises cost under the stated rules.
"""

import math

import pandas as pd

DEPARTMENTS = ["PWDx", "BTDT", "PARK", "ISD"]

CAPACITY_PER_DAY = {"PWDx": 12, "BTDT": 15, "PARK": 6, "ISD": 4}
ANNUAL_COST = {"PWDx": 130_000, "BTDT": 110_000, "PARK": 120_000, "ISD": 140_000}
START_CREWS = {"PWDx": 50, "BTDT": 18, "PARK": 10, "ISD": 16}

WORKING_DAYS = 21
HIRE_LEAD_MONTHS = 1
RELEASE_NOTICE_MONTHS = 1
RELEASE_COST_FRACTION = 0.25

SEASONAL_DEPT = "PARK"
SEASONAL_MONTHS = set(range(4, 11))
SEASONAL_MULTIPLIER = 1.3

OVERDUE_COST = 20
LONG_OVERDUE_COST = 100
LONG_OVERDUE_AGE = 2

MONTHLY_COST = {d: ANNUAL_COST[d] / 12 for d in DEPARTMENTS}

# Measured from the 311 data, 2023 and 2024.
CRITICAL_SHARE = {"PWDx": 0.98, "BTDT": 0.99, "PARK": 0.46, "ISD": 0.57}
CRITICAL_WINDOW = {"PWDx": 2.0, "BTDT": 1.0, "PARK": 6.8, "ISD": 18.1}


def monthly_capacity(dept, crews):
    """Requests a department can clear in a month at a given crew count."""
    return crews * CAPACITY_PER_DAY[dept] * WORKING_DAYS


def allowed_backlog(dept, crews):
    """Work that clears inside the target window, and is not yet late."""
    return monthly_capacity(dept, crews) * (CRITICAL_WINDOW[dept] / WORKING_DAYS)


def crews_needed(dept, demand):
    """Smallest crew count whose monthly capacity covers a month's demand."""
    per_crew = CAPACITY_PER_DAY[dept] * WORKING_DAYS
    return math.ceil(demand / per_crew)


def _lock_january(dept, months):
    """Every policy starts at January's crew count.

    A different January would need a decision taken in December 2024, before
    the planning horizon. HIRE_LEAD_MONTHS and RELEASE_NOTICE_MONTHS are both
    1, which makes February the first month a plan can change.
    """
    lead = max(HIRE_LEAD_MONTHS, RELEASE_NOTICE_MONTHS)
    return [START_CREWS[dept]] * lead + list(months)[lead:]


# ----------------------------------------------------------------------
# Policies. Each returns {dept: [crews for months 1..12]}.
# ----------------------------------------------------------------------

def plan_status_quo(demand):
    """Hold January's permanent crew counts unchanged all year.

    Seasonal Parks crews are still available, because the April to October
    allowance needs no hiring decision. Withholding it from this policy alone
    would compare the others against a baseline the city does not have.
    """
    return {d: [START_CREWS[d]] * 12 for d in DEPARTMENTS}


def plan_chase(demand, coverage=1.0):
    """Size crews to each month's forecast demand.

    The forecast covers the whole year before it starts. A crew needed in
    March is ordered in February, and January is fixed at START_CREWS.
    """
    plan = {}
    for d in DEPARTMENTS:
        wanted = [max(1, crews_needed(d, demand[d][m] * coverage)) for m in range(12)]
        plan[d] = _lock_january(d, wanted)
    return plan


def plan_smoothed(demand, quantile=0.75, max_step=2):
    """Work toward a level sized for a high-demand month, 2 crews at a time.

    Fewer hires and releases than sizing to each month, at the cost of surplus
    crews in quiet months and a shortfall in the busiest ones.
    """
    plan = {}
    for d in DEPARTMENTS:
        base = crews_needed(d, pd.Series(demand[d]).quantile(quantile))
        crews = [START_CREWS[d]]
        for _ in range(1, 12):
            prev = crews[-1]
            step = max(-max_step, min(max_step, base - prev))
            crews.append(prev + step)
        plan[d] = crews
    return plan


# ----------------------------------------------------------------------
# Simulation
# ----------------------------------------------------------------------

def simulate(demand, plan, use_seasonal=True):
    """Run a crew plan against a demand forecast and price it.

    demand   {dept: [12 monthly request counts]}
    plan     {dept: [12 crew counts]}

    Returns one row per department-month.
    """
    rows = []

    for d in DEPARTMENTS:
        # Each cohort is (age in months, requests remaining, of which overdue).
        backlog = []
        prev_crews = START_CREWS[d]

        for m in range(12):
            month_no = m + 1
            permanent = plan[d][m]
            standing = sum(c for _, c, _ in backlog)

            # Seasonal Parks crews are sized against the work actually waiting,
            # which is the standing backlog plus this month's arrivals.
            seasonal = 0
            if use_seasonal and d == SEASONAL_DEPT and month_no in SEASONAL_MONTHS:
                shortfall = (standing + demand[d][m]) - monthly_capacity(d, permanent)
                if shortfall > 0:
                    seasonal = crews_needed(d, shortfall)

            crews = permanent + seasonal
            capacity = monthly_capacity(d, crews)
            slack = allowed_backlog(d, crews)

            # Oldest work first, then this month's arrivals. Each cohort records
            # its own overdue count, which keeps the 100 USD penalty on requests
            # already charged the 20 USD.
            work = capacity
            aged = []
            newly_long = 0.0
            for age, count, od in backlog:
                take = min(work, count)
                work -= take
                left = count - take
                if left > 0:
                    od_left = od * (left / count)
                    if age < LONG_OVERDUE_AGE <= age + 1:
                        newly_long += od_left
                    aged.append((age + 1, left, od_left))

            arriving = demand[d][m]
            done_new = min(work, arriving)
            unworked_new = arriving - done_new
            overdue = max(0.0, CRITICAL_SHARE[d] * unworked_new - slack)
            if unworked_new > 0:
                aged.append((1, unworked_new, overdue))
            backlog = aged

            hires = max(0, permanent - prev_crews)
            releases = max(0, prev_crews - permanent)
            prev_crews = permanent

            crew_cost = permanent * MONTHLY_COST[d]
            seasonal_cost = seasonal * MONTHLY_COST[d] * SEASONAL_MULTIPLIER
            release_cost = releases * ANNUAL_COST[d] * RELEASE_COST_FRACTION
            overdue_cost = overdue * OVERDUE_COST + newly_long * LONG_OVERDUE_COST

            rows.append({
                "department": d,
                "month": month_no,
                "demand": arriving,
                "critical_demand": CRITICAL_SHARE[d] * arriving,
                "crews": permanent,
                "seasonal_crews": seasonal,
                "capacity": capacity,
                "hires": hires,
                "releases": releases,
                "backlog": sum(c for _, c, _ in backlog),
                "overdue": overdue,
                "long_overdue": newly_long,
                "crew_cost": crew_cost,
                "seasonal_cost": seasonal_cost,
                "release_cost": release_cost,
                "overdue_cost": overdue_cost,
                "total_cost": crew_cost + seasonal_cost + release_cost + overdue_cost,
            })

    return pd.DataFrame(rows)


def summarise(result):
    """One row per department plus a total, from a simulate() result.

    on_time_pct counts every request, which is the figure comparable to the
    rates the city publishes. on_time_critical_pct counts only requests whose
    target falls inside 30 days, which is the work a monthly plan can affect.
    """
    g = result.groupby("department").agg(
        demand=("demand", "sum"),
        critical_demand=("critical_demand", "sum"),
        hires=("hires", "sum"),
        releases=("releases", "sum"),
        seasonal_months=("seasonal_crews", lambda s: int((s > 0).sum())),
        overdue=("overdue", "sum"),
        long_overdue=("long_overdue", "sum"),
        crew_cost=("crew_cost", "sum"),
        seasonal_cost=("seasonal_cost", "sum"),
        release_cost=("release_cost", "sum"),
        overdue_cost=("overdue_cost", "sum"),
        total_cost=("total_cost", "sum"),
    ).reindex(DEPARTMENTS)

    g["on_time_pct"] = (1 - g["overdue"] / g["demand"]) * 100
    g["on_time_critical_pct"] = (1 - g["overdue"] / g["critical_demand"]) * 100

    total = g.sum(numeric_only=True)
    total["on_time_pct"] = (1 - g["overdue"].sum() / g["demand"].sum()) * 100
    total["on_time_critical_pct"] = (1 - g["overdue"].sum() / g["critical_demand"].sum()) * 100
    g.loc["TOTAL"] = total
    return g


def compare(demand, policies=None, use_seasonal=True):
    """Run several policies against the same demand and stack the totals."""
    if policies is None:
        policies = {
            "hold January permanent crews": plan_status_quo,
            "match demand each month": plan_chase,
            "smoothed, max 2 crews a month": plan_smoothed,
        }

    rows = []
    for name, fn in policies.items():
        s = summarise(simulate(demand, fn(demand), use_seasonal=use_seasonal))
        t = s.loc["TOTAL"]
        rows.append({
            "policy": name,
            "hires": int(t["hires"]),
            "releases": int(t["releases"]),
            "crew_cost": t["crew_cost"] + t["seasonal_cost"],
            "severance": t["release_cost"],
            "overdue_cost": t["overdue_cost"],
            "total_cost": t["total_cost"],
            "on_time_pct": t["on_time_pct"],
            "on_time_critical_pct": t["on_time_critical_pct"],
        })
    return pd.DataFrame(rows).set_index("policy")


def demand_from_forecast(forecast_df):
    """Turn a long forecast table into {dept: [12 counts]}."""
    w = forecast_df.pivot_table(index="month", columns="department", values="requests")
    return {d: [float(w.loc[m, d]) for m in range(1, 13)] for d in DEPARTMENTS}


def scale(demand, factor):
    """Every month scaled by the same factor, for the sensitivity runs."""
    return {d: [v * factor for v in demand[d]] for d in DEPARTMENTS}


def spike(demand, dept, month, factor):
    """One month of one department multiplied, for a storm scenario."""
    out = {d: list(v) for d, v in demand.items()}
    out[dept][month - 1] *= factor
    return out
