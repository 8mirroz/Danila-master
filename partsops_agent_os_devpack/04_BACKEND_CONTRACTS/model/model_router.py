class ModelRouter:
    def route(self, task_type: str, risk_level: str = "low", confidence: float = 1.0, budget_low: bool = False) -> str:
        no_llm = {"final_score_calculation", "margin_check", "invoice_gate", "supplier_blacklist_check", "exact_article_match"}
        simple = {"classify_request", "clean_text", "detect_missing_fields", "generate_short_clarification"}
        strong_conditions = risk_level == "high" or confidence < 0.75

        if task_type in no_llm:
            return "deterministic"
        if budget_low:
            return "cheap_fast_model"
        if strong_conditions:
            return "strong_model"
        if task_type in simple:
            return "cheap_fast_model"
        return "mid_model"
