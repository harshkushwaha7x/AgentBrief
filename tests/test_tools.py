from app.newsletter_agent.models import ArticleSummary, NewsArticle
from app.newsletter_agent.tools import (
    rank_articles_tool,
    revise_summaries_tool,
    summarizer_tool,
)


def test_rank_articles_prefers_agent_relevance():
    articles = [
        NewsArticle(title="General AI chip market update", url="https://example.com/chips"),
        NewsArticle(title="New autonomous AI agents launch for browser workflows", url="https://example.com/agents"),
    ]

    ranked = rank_articles_tool(articles, "latest AI agent news", limit=1)

    assert ranked[0].url == "https://example.com/agents"


def test_rank_articles_penalizes_general_ai_headlines():
    articles = [
        NewsArticle(
            title="The limits of large language models",
            url="https://example.com/general-ai",
            snippet="A broad analysis of model context and pricing.",
            published_at="2026-07-09",
        ),
        NewsArticle(
            title="Agentic AI platform adds autonomous browser agents",
            url="https://example.com/browser-agents",
            snippet="The product adds controls for agent actions.",
            published_at="2026-07-09",
        ),
    ]

    ranked = rank_articles_tool(articles, "latest AI agent news", limit=2)

    assert ranked[0].url == "https://example.com/browser-agents"
    assert ranked[0].relevance_score > ranked[1].relevance_score


def test_summarizer_falls_back_without_model():
    article = NewsArticle(
        title="AI agent framework adds tool use",
        url="https://example.com/story",
        source="Example",
        snippet="A new AI agent framework adds tool use, memory, and workflow controls for developers.",
    )

    summary = summarizer_tool(article, "Create a newsletter", model=None)

    assert summary.title == article.title
    assert summary.summary
    assert summary.key_points


class StubModel:
    def invoke(self, prompt: str):
        assert "Editor feedback:" in prompt
        return type(
            "Response",
            (),
            {
                "content": (
                    '{"summary":"A clearer revised summary.",'
                    '"why_it_matters":"It affects production agent design.",'
                    '"key_points":["Concrete point one.","Concrete point two."]}'
                )
            },
        )()


def test_revision_tool_applies_model_feedback():
    original = ArticleSummary(
        title="Agent launch",
        url="https://example.com/agent",
        source="Example",
        published_at="2026-07-09",
        summary="Original summary.",
        why_it_matters="Original reason.",
        key_points=["Original point.", "Another point."],
    )

    revised = revise_summaries_tool(
        [original],
        critique="Make the takeaway clearer.",
        human_feedback="Focus on production impact.",
        model=StubModel(),
    )

    assert revised[0].summary == "A clearer revised summary."
    assert revised[0].key_points == ["Concrete point one.", "Concrete point two."]
    assert revised[0].title == original.title
