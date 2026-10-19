import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import sqlglot

@dataclass
class RewriteSuggestion:
    rule_id: str
    rule_name: str
    severity: str              # HIGH, MEDIUM, LOW
    original_sql: str
    rewritten_sql: str
    explanation: str
    expected_benefit: str

class BaseRewriteRule(ABC):
    rule_id: str
    rule_name: str
    severity: str

    @abstractmethod
    def evaluate(self, parsed: sqlglot.exp.Expression, raw_sql: str) -> Optional[RewriteSuggestion]:
        """
        Analyzes the AST Expression. If an anti-pattern is matched, returns
        a RewriteSuggestion with the rewritten SQL; otherwise returns None.
        """
        pass