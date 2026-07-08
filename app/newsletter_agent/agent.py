from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Literal

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

from app.newsletter_agent.llm import get_chat_model
from app.newsletter_agent.models import AgentMode, NewsletterState
from app.newsletter_agent.tools import (
    article_from_dict,
    articles_to_dicts,
    fetch_article_tool,
    html_generator_tool,
    rank_articles_tool,
    revise_summaries_tool,
    self_critique_tool,
    simulated_sender_tool,
    summaries_to_dicts,
    summarizer_tool,
    summary_from_dict,
    web_search_tool,
)

DEFAULT_GOAL = "Create a weekly newsletter on latest AI agent news and send it to our subscribers."

load_dotenv()


def run_newsletter_agent(
    goal: str = DEFAULT_GOAL,
    mode: AgentMode = "autonomous",
    human_feedback: str | None = None,
) -> dict:
    """Run the full agent workflow from one function call."""

    graph = build_newsletter_graph()
    initial_state: NewsletterState = {
        "goal": goal,
        "mode": mode,
        "human_feedback": human_feedback,
        "status": "running",
        "tool_log": [],
        "revision_notes": [],
    }
    final_state = graph.invoke(initial_state)

    return {
        "status": final_state.get("status", "unknown"),
        "subject": final_state.get("subject", ""),
        "markdown": final_state.get("markdown", final_state.get("draft_markdown", "")),
        "html": final_state.get("html", final_state.get("draft_html", "")),
        "critique": final_state.get("critique", ""),
        "plan": final_state.get("plan", []),
        "search_queries": final_state.get("search_queries", []),
        "articles": final_state.get("selected_articles", []),
        "summaries": final_state.get("summaries", []),
        "output_paths": final_state.get("output_paths", {}),
        "tool_log": final_state.get("tool_log", []),
        "needs_human_review": final_state.get("needs_human_review", False),
        "revision_notes": final_state.get("revision_notes", []),
    }


def build_newsletter_graph():
    graph = StateGraph(NewsletterState)
    graph.add_node("plan", _plan_node)
    graph.add_node("research", _research_node)
    graph.add_node("write", _write_node)
    graph.add_node("review", _review_node)
    graph.add_node("revise", _revise_node)
    graph.add_node("send", _send_node)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "research")
    graph.add_edge("research", "write")
    graph.add_edge("write", "review")
    graph.add_conditional_edges(
        "review",
        _route_after_review,
        {
            "await_human": END,
            "revise": "revise",
            "send": "send",
        },
    )
    graph.add_edge("revise", "send")
    graph.add_edge("send", END)
    return graph.compile()


def _plan_node(state: NewsletterState) -> NewsletterState:
    goal = state["goal"]
    plan = [
        "Clarify the newsletter objective and success criteria.",
        "Search recent public news for AI-agent product, model, and infrastructure updates.",
        "Rank and deduplicate articles for relevance and recency.",
        "Summarize the top 5-7 articles for a builder audience.",
        "Generate a clean Markdown and HTML email draft.",
        "Critique the draft, revise it, and simulate sending by saving files.",
    ]
    queries = [
        "latest AI agent news autonomous agents when:30d",
        "AI agents product launch model providers agentic workflows when:30d",
        "LangGraph AutoGen CrewAI AI agent framework news when:30d",
        "OpenAI Anthropic Google AI agents tool use news when:30d",
    ]

    return {
        "plan": plan,
        "search_queries": queries,
        "tool_log": _log(state, "planner", f"Built a {len(plan)} step plan for: {goal}"),
    }


def _research_node(state: NewsletterState) -> NewsletterState:
    all_articles = []
    for query in state.get("search_queries", []):
        results = web_search_tool(query, limit=10)
        all_articles.extend(results)

    ranked = rank_articles_tool(all_articles, state["goal"], limit=7)

    enriched = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_article_tool, article.url): article
            for article in ranked
        }
        for future in as_completed(futures):
            article = futures[future]
            try:
                article.content = future.result()
            except Exception:
                article.content = ""
            enriched.append(article)

    enriched = sorted(enriched, key=lambda item: item.relevance_score, reverse=True)

    return {
        "articles": articles_to_dicts(all_articles),
        "selected_articles": articles_to_dicts(enriched),
        "tool_log": _log(
            state,
            "web_search",
            f"Collected {len(all_articles)} raw results and selected {len(enriched)} stories.",
        )
        + [
            "article_fetcher: Tried to enrich selected stories with article body text.",
        ],
    }


def _write_node(state: NewsletterState) -> NewsletterState:
    model = get_chat_model()
    articles = [article_from_dict(item) for item in state.get("selected_articles", [])]

    summaries = [
        summarizer_tool(article, state["goal"], model=model)
        for article in articles[:7]
    ]
    subject, markdown, html = html_generator_tool(state["goal"], summaries)

    return {
        "summaries": summaries_to_dicts(summaries),
        "subject": subject,
        "draft_markdown": markdown,
        "draft_html": html,
        "markdown": markdown,
        "html": html,
        "tool_log": _log(
            state,
            "summarizer",
            f"Summarized {len(summaries)} stories using {'an LLM' if model else 'local extractive logic'}.",
        )
        + ["html_generator: Created initial Markdown and HTML newsletter drafts."],
    }


def _review_node(state: NewsletterState) -> NewsletterState:
    model = get_chat_model()
    summaries = [summary_from_dict(item) for item in state.get("summaries", [])]
    critique = self_critique_tool(summaries, state.get("markdown", ""), model=model)
    needs_human_review = state.get("mode") == "human" and not state.get("human_feedback")
    status = "needs_review" if needs_human_review else "reviewed"

    return {
        "critique": critique,
        "needs_human_review": needs_human_review,
        "status": status,
        "tool_log": _log(
            state,
            "self_critique",
            "Reviewed draft for relevance, coverage, clarity, links, and tone.",
        ),
    }


def _revise_node(state: NewsletterState) -> NewsletterState:
    model = get_chat_model()
    summaries = [summary_from_dict(item) for item in state.get("summaries", [])]
    human_feedback = state.get("human_feedback")
    revised_summaries = revise_summaries_tool(
        summaries,
        critique=state.get("critique", ""),
        human_feedback=human_feedback,
        model=model,
    )
    subject, markdown, html = html_generator_tool(
        state["goal"],
        revised_summaries,
        reviewed=True,
        human_feedback=human_feedback,
    )

    notes = list(state.get("revision_notes", []))
    notes.append("Applied self-critique polish pass with clearer builder-focused framing.")
    if human_feedback:
        notes.append("Applied human editor feedback before simulated send.")

    return {
        "subject": subject,
        "markdown": markdown,
        "html": html,
        "summaries": summaries_to_dicts(revised_summaries),
        "revision_notes": notes,
        "status": "revised",
        "needs_human_review": False,
        "tool_log": _log(
            state,
            "content_editor",
            f"Applied critique using {'an LLM' if model else 'deterministic cleanup'}.",
        )
        + ["html_generator: Regenerated the final newsletter after review."],
    }


def _send_node(state: NewsletterState) -> NewsletterState:
    output_paths = simulated_sender_tool(
        state.get("subject", "Weekly AI Agent Brief"),
        state.get("markdown", ""),
        state.get("html", ""),
    )

    return {
        "output_paths": output_paths,
        "status": "sent",
        "tool_log": _log(
            state,
            "simulated_sender",
            "Saved Markdown and HTML files instead of sending real email.",
        ),
    }


def _route_after_review(state: NewsletterState) -> Literal["await_human", "revise", "send"]:
    if state.get("needs_human_review"):
        return "await_human"
    if state.get("mode") == "autonomous" or state.get("human_feedback"):
        return "revise"
    return "send"


def _log(state: NewsletterState, tool_name: str, message: str) -> list[str]:
    return list(state.get("tool_log", [])) + [f"{tool_name}: {message}"]
