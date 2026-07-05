from dataclasses import dataclass

@dataclass
class BudgetStatus:
    allowed: bool
    mode: str
    message: str

class BudgetGuard:
    def __init__(self, session_limit: float, daily_limit: float):
        self.session_limit = session_limit
        self.daily_limit = daily_limit

    def check(self, session_spend: float, daily_spend: float) -> BudgetStatus:
        if session_spend >= self.session_limit or daily_spend >= self.daily_limit:
            return BudgetStatus(False, "paused", "budget limit reached")
        if session_spend >= self.session_limit * 0.8 or daily_spend >= self.daily_limit * 0.8:
            return BudgetStatus(True, "low_cost", "budget warning: switch to low cost mode")
        return BudgetStatus(True, "normal", "budget ok")
