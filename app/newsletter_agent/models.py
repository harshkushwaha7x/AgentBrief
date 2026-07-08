from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, TypedDict

AgentMode = Literal["autonomous", "human"]


@dataclass
class NewsArticle:
    title: str
    url: str
    source: str = "Unknown"
    published_at: str = ""
    snippet: str = ""
    content: str = ""
    relevance_score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ArticleSummary:
    title: str
    url: str
    source: str
    published_at: str
    summary: str
    why_it_matters: str
    key_points: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class NewsletterState(TypedDict, total=False):
    goal: str
    mode: AgentMode
    human_feedback: str | None
    status: str
    plan: list[str]
    search_queries: list[str]
    articles: list[dict]
    selected_articles: list[dict]
    summaries: list[dict]
    subject: str
    markdown: str
    html: str
    draft_markdown: str
    draft_html: str
    critique: str
    revision_notes: list[str]
    output_paths: dict[str, str]
    tool_log: list[str]
    needs_human_review: bool
