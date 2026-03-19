import unittest

from agents.planner import PlannerAgent


class PlannerHardCaseTests(unittest.TestCase):
    def test_priority_aliases_are_added_to_query_plan(self):
        planner = PlannerAgent()
        plan = planner.build_plan(
            {
                "deal_id": "tgi-fridays-2024",
                "company_name": "TGI Fridays, Inc.",
                "filing_year": 2024,
                "search_aliases": ["TGI Friday's"],
            }
        )
        queries = [variant["q"] for variant in plan.variants]

        self.assertIn('"TGI Friday\'s" "chapter 11"', queries)
        self.assertIn('"TGI Friday\'s" "first day motions"', queries)

    def test_broad_exact_queries_are_added_for_hard_cases(self):
        planner = PlannerAgent()
        plan = planner.build_plan(
            {
                "deal_id": "exactech-2024",
                "company_name": "Exactech, Inc.",
                "filing_year": 2024,
            }
        )
        queries = [variant["q"] for variant in plan.variants]

        self.assertIn('"Exactech, Inc." "chapter 11"', queries)
        self.assertIn('"Exactech, Inc." "first day motions"', queries)
        self.assertIn('"Exactech, Inc." declaration', queries)

    def test_generic_single_token_alias_does_not_emit_loose_queries(self):
        planner = PlannerAgent()
        plan = planner.build_plan(
            {
                "deal_id": "express-2024",
                "company_name": "Express, Inc.",
                "filing_year": 2024,
            }
        )
        query_names = [variant["name"] for variant in plan.variants]

        self.assertNotIn("loose_rd_ch11", query_names)
        self.assertNotIn("loose_rd_support", query_names)
        self.assertNotIn("loose_rd_dip", query_names)

    def test_followup_variants_cover_missing_doc_types(self):
        planner = PlannerAgent()
        variants = planner.build_followup_variants(
            {
                "deal_id": "conns-2024",
                "company_name": "Conn's, Inc.",
                "filing_year": 2024,
            },
            ["dip_motion", "credit_agreement"],
        )
        queries = [variant["q"] for variant in variants]

        self.assertIn('"Conn\'s, Inc." "debtor in possession financing"', queries)
        self.assertIn('"Conn\'s, Inc." "motion to obtain postpetition financing"', queries)
        self.assertIn('"Conn\'s, Inc." "credit agreement"', queries)

    def test_docket_variants_include_alias_and_yearless_search(self):
        planner = PlannerAgent()
        variants = planner.build_docket_variants(
            {
                "deal_id": "buca-di-beppo-2024",
                "company_name": "Buca C, LLC",
                "filing_year": 2024,
                "search_aliases": ["Buca di Beppo"],
            }
        )
        queries = [variant["q"] for variant in variants]
        types = [variant["type"] for variant in variants]
        years = [variant["filing_year"] for variant in variants]

        self.assertIn('"Buca di Beppo" chapter 11', queries)
        self.assertIn('"Buca" chapter 11', queries)
        self.assertTrue(all(value == "d" for value in types))
        self.assertIn("", years)


if __name__ == "__main__":
    unittest.main()
