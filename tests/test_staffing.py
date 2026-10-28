"""Checks on the crew model in staffing.py.

No model and no data file is needed. Every expected value here is arithmetic
from the rules the problem states, worked out by hand.

Run from the project folder:   python -m unittest discover -s tests
"""

import unittest

import staffing as s


class Capacity(unittest.TestCase):
    """A crew clears CAPACITY_PER_DAY requests on each of 21 working days."""

    def test_monthly_capacity_matches_the_rules(self):
        self.assertEqual(s.monthly_capacity("PWDx", 50), 50 * 12 * 21)
        self.assertEqual(s.monthly_capacity("BTDT", 18), 18 * 15 * 21)
        self.assertEqual(s.monthly_capacity("PARK", 10), 10 * 6 * 21)
        self.assertEqual(s.monthly_capacity("ISD", 16), 16 * 4 * 21)

    def test_january_capacities(self):
        """The 4 figures the notebook prints at January crew counts."""
        self.assertEqual(s.monthly_capacity("PWDx", 50), 12_600)
        self.assertEqual(s.monthly_capacity("BTDT", 18), 5_670)
        self.assertEqual(s.monthly_capacity("PARK", 10), 1_260)
        self.assertEqual(s.monthly_capacity("ISD", 16), 1_344)

    def test_no_crews_clears_nothing(self):
        for d in s.DEPARTMENTS:
            self.assertEqual(s.monthly_capacity(d, 0), 0)


class CrewsNeeded(unittest.TestCase):
    """crews_needed rounds up: a part-month of work still needs a whole crew."""

    def test_exact_fit_needs_no_extra_crew(self):
        self.assertEqual(s.crews_needed("PWDx", 12_600), 50)

    def test_one_request_over_needs_another_crew(self):
        self.assertEqual(s.crews_needed("PWDx", 12_601), 51)

    def test_zero_demand_needs_no_crews(self):
        self.assertEqual(s.crews_needed("PARK", 0), 0)


class AllowedBacklog(unittest.TestCase):
    """Work that clears inside the target window is not yet late."""

    def test_allowed_backlog_scales_with_the_target_window(self):
        self.assertAlmostEqual(s.allowed_backlog("PWDx", 50), 12_600 * (2.0 / 21))
        self.assertAlmostEqual(s.allowed_backlog("BTDT", 18), 5_670 * (1.0 / 21))

    def test_the_figures_the_notebook_prints(self):
        self.assertAlmostEqual(s.allowed_backlog("PWDx", 50), 1_200.0)
        self.assertAlmostEqual(s.allowed_backlog("BTDT", 18), 270.0)
        self.assertAlmostEqual(s.allowed_backlog("PARK", 10), 408.0)
        self.assertAlmostEqual(s.allowed_backlog("ISD", 16), 1_158.4)


def flat_demand(per_month):
    """The same demand in every department in every month."""
    return {d: [float(per_month)] * 12 for d in s.DEPARTMENTS}


class JanuaryIsFixed(unittest.TestCase):
    """Hiring takes a month. No policy can change January."""

    def test_every_policy_starts_at_the_given_counts(self):
        demand = flat_demand(5_000)
        for plan in (s.plan_status_quo(demand),
                     s.plan_chase(demand),
                     s.plan_smoothed(demand)):
            for d in s.DEPARTMENTS:
                self.assertEqual(plan[d][0], s.START_CREWS[d])

    def test_every_policy_gives_12_months(self):
        demand = flat_demand(5_000)
        for plan in (s.plan_status_quo(demand),
                     s.plan_chase(demand),
                     s.plan_smoothed(demand)):
            for d in s.DEPARTMENTS:
                self.assertEqual(len(plan[d]), 12)


class SmoothedMovesSlowly(unittest.TestCase):
    """The smoothed policy moves by at most 2 crews between months."""

    def test_no_step_larger_than_2(self):
        plan = s.plan_smoothed(flat_demand(20_000))
        for d in s.DEPARTMENTS:
            steps = [abs(b - a) for a, b in zip(plan[d], plan[d][1:])]
            self.assertLessEqual(max(steps), 2)


class Simulation(unittest.TestCase):
    """Cost and overdue behaviour under the stated rules."""

    def test_light_demand_goes_nothing_overdue(self):
        demand = flat_demand(100)
        result = s.summarise(s.simulate(demand, s.plan_status_quo(demand)))
        self.assertAlmostEqual(result.loc["TOTAL", "overdue"], 0.0)

    def test_light_demand_costs_only_salaries(self):
        demand = flat_demand(100)
        result = s.summarise(s.simulate(demand, s.plan_status_quo(demand),
                                        use_seasonal=False))
        salaries = sum(s.START_CREWS[d] * s.ANNUAL_COST[d] for d in s.DEPARTMENTS)
        self.assertAlmostEqual(result.loc["TOTAL", "total_cost"], salaries, places=2)

    def test_heavy_demand_goes_overdue(self):
        demand = flat_demand(50_000)
        result = s.summarise(s.simulate(demand, s.plan_status_quo(demand)))
        self.assertGreater(result.loc["TOTAL", "overdue"], 0.0)

    def test_holding_crews_hires_and_releases_no_one(self):
        demand = flat_demand(5_000)
        result = s.summarise(s.simulate(demand, s.plan_status_quo(demand)))
        self.assertEqual(result.loc["TOTAL", "hires"], 0.0)
        self.assertEqual(result.loc["TOTAL", "releases"], 0.0)


class LongOverduePenalty(unittest.TestCase):
    """A request still unworked 30 days past target costs a further 100 USD."""

    def test_nothing_late_means_no_second_penalty(self):
        demand = flat_demand(100)
        result = s.summarise(s.simulate(demand, s.plan_status_quo(demand)))
        self.assertAlmostEqual(result.loc["TOTAL", "long_overdue"], 0.0)

    def test_sustained_overload_reaches_the_second_penalty(self):
        demand = flat_demand(50_000)
        result = s.summarise(s.simulate(demand, s.plan_status_quo(demand)))
        self.assertGreater(result.loc["TOTAL", "long_overdue"], 0.0)

    def test_the_second_penalty_is_charged_on_fewer_requests_than_the_first(self):
        """Only work still unworked after 2 months picks it up."""
        demand = flat_demand(50_000)
        result = s.summarise(s.simulate(demand, s.plan_status_quo(demand)))
        self.assertLess(result.loc["TOTAL", "long_overdue"],
                        result.loc["TOTAL", "overdue"])


class SeasonalParksCrews(unittest.TestCase):
    """Parks alone may take seasonal crews, and only from April through October."""

    def test_seasonal_crews_appear_only_in_the_allowed_months(self):
        demand = flat_demand(10_000)
        result = s.simulate(demand, s.plan_status_quo(demand))
        park = result[result["department"] == "PARK"]
        outside = park[~park["month"].isin(range(4, 11))]
        self.assertEqual(outside["seasonal_crews"].sum(), 0)

    def test_seasonal_crews_do_appear_when_parks_is_short(self):
        demand = flat_demand(10_000)
        result = s.simulate(demand, s.plan_status_quo(demand))
        park = result[result["department"] == "PARK"]
        inside = park[park["month"].isin(range(4, 11))]
        self.assertGreater(inside["seasonal_crews"].sum(), 0)

    def test_no_other_department_takes_seasonal_crews(self):
        demand = flat_demand(10_000)
        result = s.simulate(demand, s.plan_status_quo(demand))
        others = result[result["department"] != "PARK"]
        self.assertEqual(others["seasonal_crews"].sum(), 0)


class ReleaseCost(unittest.TestCase):
    """Releasing a crew costs a quarter of its annual salary."""

    def test_one_release_costs_a_quarter_of_annual_salary(self):
        demand = flat_demand(100)
        plan = {d: [s.START_CREWS[d]] * 12 for d in s.DEPARTMENTS}
        plan["PWDx"] = [50] + [49] * 11          # 1 crew released, from month 2
        result = s.summarise(s.simulate(demand, plan, use_seasonal=False))
        self.assertEqual(result.loc["PWDx", "releases"], 1.0)
        self.assertAlmostEqual(result.loc["PWDx", "release_cost"],
                               s.ANNUAL_COST["PWDx"] * 0.25)

    def test_hiring_costs_no_severance(self):
        demand = flat_demand(100)
        plan = {d: [s.START_CREWS[d]] * 12 for d in s.DEPARTMENTS}
        plan["PWDx"] = [50] + [51] * 11          # 1 crew hired, from month 2
        result = s.summarise(s.simulate(demand, plan, use_seasonal=False))
        self.assertEqual(result.loc["PWDx", "hires"], 1.0)
        self.assertAlmostEqual(result.loc["PWDx", "release_cost"], 0.0)


class Scenarios(unittest.TestCase):
    """scale and spike change demand the way the sensitivity section assumes."""

    def test_scaling_by_1_changes_nothing(self):
        demand = flat_demand(1_000)
        self.assertEqual(s.scale(demand, 1.0), demand)

    def test_scaling_multiplies_every_month(self):
        scaled = s.scale(flat_demand(1_000), 1.2)
        for d in s.DEPARTMENTS:
            self.assertEqual(scaled[d], [1_200.0] * 12)

    def test_spike_changes_one_month_of_one_department(self):
        demand = flat_demand(1_000)
        spiked = s.spike(demand, "PWDx", 2, 3.0)
        self.assertEqual(spiked["PWDx"][1], 3_000.0)
        self.assertEqual(spiked["PWDx"][0], 1_000.0)
        self.assertEqual(spiked["BTDT"], demand["BTDT"])

    def test_spike_leaves_the_original_alone(self):
        demand = flat_demand(1_000)
        s.spike(demand, "PWDx", 2, 3.0)
        self.assertEqual(demand["PWDx"][1], 1_000.0)


if __name__ == "__main__":
    unittest.main()
