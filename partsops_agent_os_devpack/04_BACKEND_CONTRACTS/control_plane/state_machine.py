from enum import Enum

class RequestState(str, Enum):
    NEW = "NEW"
    PARSING = "PARSING"
    VALIDATION = "VALIDATION"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    SUPPLIER_QUERY = "SUPPLIER_QUERY"
    MATCHING = "MATCHING"
    RANKING = "RANKING"
    RISK_REVIEW = "RISK_REVIEW"
    ADMIN_REVIEW = "ADMIN_REVIEW"
    REPORTING = "REPORTING"
    INVOICE_DRAFT = "INVOICE_DRAFT"
    ADMIN_APPROVAL = "ADMIN_APPROVAL"
    SENT = "SENT"
    ERROR = "ERROR"
    DEAD_LETTER = "DEAD_LETTER"

TRANSITIONS = {
    RequestState.NEW: [RequestState.PARSING],
    RequestState.PARSING: [RequestState.VALIDATION, RequestState.ERROR],
    RequestState.VALIDATION: [RequestState.NEEDS_CLARIFICATION, RequestState.SUPPLIER_QUERY, RequestState.ADMIN_REVIEW],
    RequestState.NEEDS_CLARIFICATION: [RequestState.PARSING, RequestState.DEAD_LETTER],
    RequestState.SUPPLIER_QUERY: [RequestState.MATCHING, RequestState.ERROR],
    RequestState.MATCHING: [RequestState.RANKING, RequestState.ADMIN_REVIEW],
    RequestState.RANKING: [RequestState.RISK_REVIEW],
    RequestState.RISK_REVIEW: [RequestState.ADMIN_REVIEW, RequestState.REPORTING],
    RequestState.ADMIN_REVIEW: [RequestState.REPORTING, RequestState.NEEDS_CLARIFICATION, RequestState.DEAD_LETTER],
    RequestState.REPORTING: [RequestState.INVOICE_DRAFT],
    RequestState.INVOICE_DRAFT: [RequestState.ADMIN_APPROVAL, RequestState.ERROR],
    RequestState.ADMIN_APPROVAL: [RequestState.SENT, RequestState.ADMIN_REVIEW],
    RequestState.ERROR: [RequestState.ADMIN_REVIEW, RequestState.DEAD_LETTER],
}

def can_transition(current: RequestState, nxt: RequestState) -> bool:
    return nxt in TRANSITIONS.get(current, [])
