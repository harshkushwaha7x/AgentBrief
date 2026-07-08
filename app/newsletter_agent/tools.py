from __future__ import annotations

import html
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from xml.etree import ElementTree

from app.newsletter_agent.llm import invoke_text
from app.newsletter_agent.models import ArticleSummary, NewsArticle

AI_AGENT_KEYWORDS = {
    "agent",
    "agents",
    "agentic",
    "autonomous",
    "automation",
    "tool",
    "tools",
    "workflow",
    "workflows",
    "langgraph",
    "langchain",
    "autogen",
    "crewai",
    "openai",
    "anthropic",
    "claude",
    "gemini",
    "grok",
    "operator",
    "computer use",
    "browser use",
    "multi-agent",
    "mcp",
    "model context protocol",
    "digital worker",
    "llm",
}

CORE_AGENT_TERMS = {
    "agent",
    "agents",
    "agentic",
    "autonomous",
    "multi-agent",
    "mcp",
    "model context protocol",
    "digital worker",
    "computer use",
    "browser use",
}


def web_search_tool(query: str, limit: int = 10) -> list[NewsArticle]:
    """Search public Google News RSS without requiring an API key."""

    import httpx

    encoded_query = quote_plus(query)
    url = (
        "https://news.google.com/rss/search"
        f"?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    )
    headers = {"User-Agent": "NewsletterAgent/1.0"}

    try:
        response = httpx.get(url, headers=headers, timeout=12.0, follow_redirects=True)
        response.raise_for_status()
    except Exception:
        return []

    try:
        root = ElementTree.fromstring(response.text)
    except ElementTree.ParseError:
        return []

    articles: list[NewsArticle] = []
    for item in root.findall(".//item")[:limit]:
        raw_title = _text(item, "title")
        link = _text(item, "link")
        source_node = item.find("source")
        source = source_node.text if source_node is not None and source_node.text else "Google News"
        title = _clean_title(raw_title, source)
        published_at = _normalise_pub_date(_text(item, "pubDate"))
        snippet = _clean_snippet(_text(item, "description"), title, source)

        if title and link:
            articles.append(
                NewsArticle(
                    title=title,
                    url=link,
                    source=source,
                    published_at=published_at,
                    snippet=snippet,
                )
            )

    return articles


def fetch_article_tool(url: str, max_chars: int = 4500) -> str:
    """Fetch article text from a URL. Failures return an empty string."""

    import httpx
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; NewsletterAgent/1.0; "
            "+https://example.com/newsletter-agent)"
        )
    }

    try:
        response = httpx.get(url, headers=headers, timeout=12.0, follow_redirects=True)
        response.raise_for_status()
    except Exception:
        return ""

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "form", "nav", "footer"]):
        tag.decompose()

    paragraphs = [
        _squash_spaces(p.get_text(" ", strip=True))
        for p in soup.find_all(["p", "article"])
    ]
    text = " ".join(part for part in paragraphs if len(part.split()) > 8)
    return _squash_spaces(text)[:max_chars]


def rank_articles_tool(articles: list[NewsArticle], goal: str, limit: int = 7) -> list[NewsArticle]:
    seen: set[str] = set()
    deduped: list[NewsArticle] = []

    for article in articles:
        key = _dedupe_key(article.title, article.url)
        if key in seen:
            continue
        seen.add(key)
        article.relevance_score = _score_article(article, goal)
        deduped.append(article)

    ranked = sorted(deduped, key=lambda item: item.relevance_score, reverse=True)
    return ranked[:limit]


def summarizer_tool(article: NewsArticle, goal: str, model: Any | None = None) -> ArticleSummary:
    source_text = " ".join(
        part
        for part in [article.title, article.snippet, article.content]
        if part
    )

    llm_summary = invoke_text(
        model,
        (
            "You are writing a concise weekly newsletter for AI builders.\n"
            f"Goal: {goal}\n"
            "Summarize this article in 2 sentences, then provide 2 short key points, "
            "and one sentence on why it matters. Keep it factual and avoid hype.\n\n"
            f"Article title: {article.title}\n"
            f"Source: {article.source}\n"
            f"Published: {article.published_at}\n"
            f"Text: {source_text[:5000]}"
        ),
    )

    metadata_only = not article.content or len(article.content.split()) < 35

    if llm_summary:
        summary, key_points, why = _parse_llm_summary(llm_summary)
    elif metadata_only:
        summary = _metadata_summary(article)
        key_points = _metadata_key_points(article)
        why = _metadata_why_it_matters(article)
    else:
        summary = _extractive_summary(source_text, max_sentences=2)
        key_points = _extract_key_points(source_text)
        why = _why_it_matters(source_text)

    return ArticleSummary(
        title=article.title,
        url=article.url,
        source=article.source,
        published_at=article.published_at,
        summary=summary,
        why_it_matters=why,
        key_points=key_points,
    )


def html_generator_tool(
    goal: str,
    summaries: list[ArticleSummary],
    reviewed: bool = False,
    human_feedback: str | None = None,
) -> tuple[str, str, str]:
    generated_at = datetime.now(timezone.utc).strftime("%B %d, %Y %H:%M UTC")
    subject = f"Weekly AI Agent Brief: {generated_at.split(' ')[0]} {generated_at.split(' ')[1].rstrip(',')}"
    intro = _build_intro(summaries, reviewed=reviewed, human_feedback=human_feedback)

    markdown_lines = [
        f"# {subject}",
        "",
        f"Generated: {generated_at}",
        "",
        "## Executive Summary",
        intro,
        "",
        "## Top Stories",
    ]

    for index, item in enumerate(summaries, start=1):
        markdown_lines.extend(
            [
                "",
                f"### {index}. {item.title}",
                f"Source: {item.source} | Published: {item.published_at or 'Recent'}",
                "",
                item.summary,
                "",
                "**Key points:**",
                *[f"- {point}" for point in item.key_points[:3]],
                "",
                f"**Why it matters:** {item.why_it_matters}",
                "",
                f"Read more: {item.url}",
            ]
        )

    markdown_lines.extend(
        [
            "",
            "## Simulated Send",
            "This email was generated by the Newsletter Agent and saved locally instead of being sent to real subscribers.",
            "",
            f"Original goal: {goal}",
        ]
    )

    markdown = "\n".join(markdown_lines).strip() + "\n"
    html_body = _render_email_html(subject, generated_at, intro, summaries, goal)
    return subject, markdown, html_body


def self_critique_tool(summaries: list[ArticleSummary], markdown: str, model: Any | None = None) -> str:
    llm_critique = invoke_text(
        model,
        (
            "Critique this AI newsletter draft. Check relevance, story count, clarity, links, "
            "and whether it avoids hype. Return 3 concise bullets and a final verdict.\n\n"
            f"{markdown[:6000]}"
        ),
    )
    if llm_critique:
        return llm_critique

    issues: list[str] = []
    if len(summaries) < 5:
        issues.append("Only a few stories were found; the agent should disclose limited coverage.")
    if len(summaries) > 7:
        issues.append("The newsletter has too many stories for the requested brief.")
    if any(not item.url for item in summaries):
        issues.append("At least one story is missing a source link.")
    if any(len(item.summary.split()) < 20 for item in summaries):
        issues.append("Some summaries are short and need more context.")

    sources = {item.source for item in summaries if item.source}
    if len(sources) < max(2, min(4, len(summaries))):
        issues.append("Source diversity is limited; readers may want broader coverage.")

    if not issues:
        issues.append("The draft has the requested 5-7 story range, source links, and concise summaries.")
        issues.append("The strongest version should keep the builder-focused framing and avoid generic AI headlines.")
        verdict = "Verdict: Ready after one polish pass."
    else:
        verdict = "Verdict: Needs a polish pass before simulated send."

    bullets = "\n".join(f"- {issue}" for issue in issues[:3])
    return f"{bullets}\n{verdict}"


def revise_summaries_tool(
    summaries: list[ArticleSummary],
    critique: str,
    human_feedback: str | None = None,
    model: Any | None = None,
) -> list[ArticleSummary]:
    """Apply review notes to story copy while preserving source metadata."""

    revised: list[ArticleSummary] = []
    editor_notes = human_feedback.strip() if human_feedback else "No additional editor feedback."

    for item in summaries:
        response = invoke_text(
            model,
            (
                "Revise one newsletter story using the review notes below. Preserve facts and do "
                "not invent details. Return only a JSON object with string fields summary and "
                "why_it_matters, plus a key_points array containing 2-3 concise strings.\n\n"
                f"Self-critique:\n{critique[:1500]}\n\n"
                f"Editor feedback:\n{editor_notes[:1000]}\n\n"
                f"Title: {item.title}\n"
                f"Source: {item.source}\n"
                f"Current summary: {item.summary}\n"
                f"Current key points: {json.dumps(item.key_points)}\n"
                f"Current why it matters: {item.why_it_matters}"
            ),
        )
        parsed = _parse_revision_json(response) if response else None

        revised.append(
            ArticleSummary(
                title=item.title,
                url=item.url,
                source=item.source,
                published_at=item.published_at,
                summary=(
                    _squash_spaces(parsed["summary"])
                    if parsed
                    else _trim_sentence(item.summary, 520)
                ),
                why_it_matters=(
                    _squash_spaces(parsed["why_it_matters"])
                    if parsed
                    else _trim_sentence(item.why_it_matters, 240)
                ),
                key_points=(
                    [_trim_sentence(point, 180) for point in parsed["key_points"][:3]]
                    if parsed
                    else _dedupe_strings(
                        [_trim_sentence(point, 180) for point in item.key_points if point]
                    )[:3]
                ),
            )
        )

    return revised


def simulated_sender_tool(
    subject: str,
    markdown: str,
    html_body: str,
    output_dir: str | Path = "outputs",
) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = f"newsletter_{timestamp}"
    markdown_path = output_path / f"{safe_name}.md"
    html_path = output_path / f"{safe_name}.html"

    markdown_path.write_text(
        _build_simulated_email_header(subject) + "\n\n" + markdown,
        encoding="utf-8",
    )
    html_path.write_text(html_body, encoding="utf-8")

    return {
        "markdown": str(markdown_path.resolve()),
        "html": str(html_path.resolve()),
    }


def article_from_dict(data: dict) -> NewsArticle:
    return NewsArticle(**data)


def summary_from_dict(data: dict) -> ArticleSummary:
    return ArticleSummary(**data)


def articles_to_dicts(articles: list[NewsArticle]) -> list[dict]:
    return [asdict(article) for article in articles]


def summaries_to_dicts(summaries: list[ArticleSummary]) -> list[dict]:
    return [asdict(summary) for summary in summaries]


def _text(node: ElementTree.Element, tag: str) -> str:
    child = node.find(tag)
    return child.text.strip() if child is not None and child.text else ""


def _normalise_pub_date(value: str) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return value


def _clean_html(value: str) -> str:
    return _squash_spaces(re.sub(r"<[^>]+>", " ", html.unescape(value)))


def _clean_title(title: str, source: str) -> str:
    value = _clean_html(title)
    source_variants = {source, source.replace(".com", ""), source.split(".")[0]}
    for variant in sorted(source_variants, key=len, reverse=True):
        if not variant:
            continue
        value = re.sub(rf"\s+[-|]\s+{re.escape(variant)}\s*$", "", value, flags=re.I)
    return _squash_spaces(value)


def _clean_snippet(value: str, title: str, source: str) -> str:
    cleaned = _clean_html(value)
    for piece in {title, source}:
        if piece:
            cleaned = cleaned.replace(piece, " ")
    cleaned = _squash_spaces(cleaned)
    if len(cleaned.split()) < 8:
        return ""
    return cleaned


def _squash_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _dedupe_key(title: str, url: str) -> str:
    simple_title = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    simple_title = re.sub(r"\b(the|a|an|to|of|for|and|in|on|with)\b", "", simple_title)
    return _squash_spaces(simple_title)[:90] or url


def _score_article(article: NewsArticle, goal: str) -> float:
    title = article.title.lower()
    text = f"{title} {article.snippet} {article.source}".lower()
    score = 0.0
    for keyword in AI_AGENT_KEYWORDS:
        if _contains_term(text, keyword):
            score += 2.0 if keyword in {"agent", "agents", "agentic", "autonomous"} else 1.0

    title_core_matches = sum(_contains_term(title, term) for term in CORE_AGENT_TERMS)
    text_has_core_term = any(_contains_term(text, term) for term in CORE_AGENT_TERMS)
    score += title_core_matches * 5
    if not text_has_core_term:
        score -= 12

    for word in re.findall(r"[a-zA-Z]{4,}", goal.lower()):
        if _contains_term(text, word):
            score += 0.5

    try:
        published = datetime.fromisoformat(article.published_at).replace(tzinfo=timezone.utc)
        days_old = max((datetime.now(timezone.utc) - published).days, 0)
        score += max(0, 10 - min(days_old, 10))
        if days_old > 45:
            score -= 8
        if days_old > 90:
            score -= 15
    except Exception:
        score += 1

    if "newsletter" in text:
        score -= 1
    return score


def _contains_term(text: str, term: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text))


def _extractive_summary(text: str, max_sentences: int = 2) -> str:
    cleaned = _squash_spaces(text)
    if not cleaned:
        return "No article body was available, so this item is summarized from the headline and available news metadata."

    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    ranked = sorted(
        sentences,
        key=lambda sentence: sum(1 for keyword in AI_AGENT_KEYWORDS if keyword in sentence.lower()),
        reverse=True,
    )
    selected = [sentence for sentence in ranked if len(sentence.split()) >= 8][:max_sentences]
    if not selected:
        selected = sentences[:max_sentences]
    return " ".join(selected).strip()


def _extract_key_points(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", _squash_spaces(text))
    points = [
        sentence.strip()
        for sentence in sentences
        if any(keyword in sentence.lower() for keyword in AI_AGENT_KEYWORDS)
        and 8 <= len(sentence.split()) <= 28
    ]
    if len(points) < 2:
        points.extend(sentences[:2])
    clean_points = [_trim_sentence(point, 150) for point in points if point]
    return clean_points[:3] or ["Article metadata was limited, so the headline is the primary signal."]


def _metadata_summary(article: NewsArticle) -> str:
    title = article.title.rstrip(".")
    date_text = f" on {article.published_at}" if article.published_at else ""
    focus = _metadata_focus(article)
    return (
        f"{article.source} reported{date_text} on {title}. "
        f"For AI-agent teams, the story is mainly a signal about {focus}."
    )


def _metadata_key_points(article: NewsArticle) -> list[str]:
    text = f"{article.title} {article.source}".lower()
    points: list[str] = []

    if any(provider in text for provider in ["openai", "anthropic", "google", "gemini", "claude"]):
        points.append("Tracks competitive moves by frontier model providers in agent capabilities.")
    if any(term in text for term in ["security", "governance", "control", "risk"]):
        points.append("Highlights the need for access control, oversight, and policy around agent actions.")
    if any(term in text for term in ["framework", "langgraph", "autogen", "crewai", "developer", "tools"]):
        points.append("Relevant to developers choosing orchestration, coding, and agent workflow tools.")
    if any(term in text for term in ["manufacturing", "health", "finance", "enterprise"]):
        points.append("Shows agent adoption moving into domain-specific operational workflows.")
    if any(term in text for term in ["autonomous", "coworkers", "digital workers", "24/7"]):
        points.append("Points toward agents being positioned as persistent assistants rather than one-shot chat tools.")

    points.append("Useful for prioritizing reliability, permissions, monitoring, and human review in agent systems.")
    return _dedupe_strings(points)[:3]


def _metadata_why_it_matters(article: NewsArticle) -> str:
    text = f"{article.title} {article.source}".lower()
    if any(provider in text for provider in ["openai", "anthropic", "google"]):
        return "Major model providers shape the tools, pricing, and reliability assumptions teams use when building agents."
    if any(term in text for term in ["security", "governance", "control", "risk"]):
        return "Agent deployments need trust boundaries, auditability, and human control before they can handle sensitive work."
    if any(term in text for term in ["framework", "developer", "tools", "langgraph", "autogen", "crewai"]):
        return "Tooling choices affect how teams design, observe, and maintain multi-step agent workflows."
    return "The story helps teams track how autonomous AI systems are moving from experiments into practical products."


def _metadata_focus(article: NewsArticle) -> str:
    text = f"{article.title} {article.source}".lower()
    if any(term in text for term in ["security", "governance", "control", "risk"]):
        return "governance and safety controls for autonomous systems"
    if any(term in text for term in ["framework", "developer", "tools", "langgraph", "autogen", "crewai"]):
        return "the developer tooling used to build and operate agent workflows"
    if any(provider in text for provider in ["openai", "anthropic", "google", "gemini", "claude"]):
        return "competition among model providers to make agents more capable and persistent"
    if any(term in text for term in ["manufacturing", "health", "finance", "enterprise"]):
        return "enterprise adoption of agents in specialized business processes"
    return "the broader shift from chatbots toward action-taking AI systems"


def _why_it_matters(text: str) -> str:
    lower_text = text.lower()
    if "openai" in lower_text or "anthropic" in lower_text or "google" in lower_text:
        return "Major model providers shape the tools, pricing, and reliability assumptions teams use when building agents."
    if "startup" in lower_text or "funding" in lower_text:
        return "Funding and product activity shows where the agent market is moving beyond prototypes."
    if "framework" in lower_text or "langgraph" in lower_text or "autogen" in lower_text:
        return "Framework changes affect how developers design, observe, and deploy multi-step agent workflows."
    return "The story helps teams track how autonomous AI systems are moving from experiments into practical products."


def _parse_llm_summary(text: str) -> tuple[str, list[str], str]:
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    why = ""
    key_points: list[str] = []
    summary_parts: list[str] = []

    for raw_line in raw_lines:
        line = raw_line.strip(" -\t")
        lower = line.lower()
        if "why" in lower and "matter" in lower:
            why = re.sub(r"^why[^:]*:\s*", "", line, flags=re.I)
        elif lower.startswith(("key", "point")):
            continue
        elif len(key_points) < 3 and (
            raw_line.lstrip().startswith(("*", "-")) or lower.startswith(("1.", "2.", "3."))
        ):
            key_points.append(re.sub(r"^\d+\.\s*", "", line))
        elif len(summary_parts) < 3:
            summary_parts.append(line)

    if not summary_parts:
        summary_parts = [line.strip(" -\t") for line in raw_lines[:2]]
    if not key_points:
        key_points = [_trim_sentence(line, 150) for line in raw_lines[2:5]]
    if not why:
        why = "This matters because it may change how teams build and operate AI agent workflows."

    return " ".join(summary_parts[:2]), key_points[:3], why


def _parse_revision_json(value: str) -> dict[str, Any] | None:
    candidate = value.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.I)
        candidate = re.sub(r"\s*```$", "", candidate)

    try:
        data = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return None

    summary = data.get("summary")
    why = data.get("why_it_matters")
    points = data.get("key_points")
    if not isinstance(summary, str) or not isinstance(why, str):
        return None
    if not isinstance(points, list) or not all(isinstance(point, str) for point in points):
        return None
    if not summary.strip() or not why.strip() or len(points) < 2:
        return None

    return {
        "summary": summary,
        "why_it_matters": why,
        "key_points": points,
    }


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _trim_sentence(value: str, limit: int) -> str:
    value = _squash_spaces(value)
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "."


def _build_intro(
    summaries: list[ArticleSummary],
    reviewed: bool = False,
    human_feedback: str | None = None,
) -> str:
    count = len(summaries)
    sources = sorted({item.source for item in summaries if item.source})
    source_text = ", ".join(sources[:4])
    intro = (
        f"This issue tracks {count} recent AI-agent stories"
        f"{f' from sources including {source_text}' if source_text else ''}. "
        "The focus is practical: product launches, agent infrastructure, model capabilities, "
        "and signals that matter to teams building autonomous workflows."
    )
    if reviewed:
        intro += " The final draft was tightened after self-review for clearer builder takeaways."
    if human_feedback:
        intro += " Human editor guidance was applied before the simulated send."
    return intro


def _render_email_html(
    subject: str,
    generated_at: str,
    intro: str,
    summaries: list[ArticleSummary],
    goal: str,
) -> str:
    article_blocks = []
    for index, item in enumerate(summaries, start=1):
        points = "".join(
            f"<li>{html.escape(point)}</li>" for point in item.key_points[:3]
        )
        article_blocks.append(
            f"""
            <section class="story">
              <div class="story-index">{index}</div>
              <div class="story-body">
                <h2>{html.escape(item.title)}</h2>
                <p class="meta">{html.escape(item.source)} | {html.escape(item.published_at or "Recent")}</p>
                <p>{html.escape(item.summary)}</p>
                <ul>{points}</ul>
                <p class="why"><strong>Why it matters:</strong> {html.escape(item.why_it_matters)}</p>
                <a href="{html.escape(item.url)}">Read source</a>
              </div>
            </section>
            """
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(subject)}</title>
  <style>
    body {{
      margin: 0;
      background: #f6f4ef;
      color: #1f2328;
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.55;
    }}
    .email {{
      max-width: 760px;
      margin: 0 auto;
      background: #ffffff;
    }}
    .masthead {{
      padding: 32px 36px 28px;
      border-top: 6px solid #2d6a4f;
      border-bottom: 1px solid #d8d5cc;
    }}
    .eyebrow {{
      margin: 0 0 8px;
      color: #8a5a00;
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    h1 {{
      margin: 0;
      font-size: 32px;
      line-height: 1.15;
    }}
    .generated {{
      margin: 12px 0 0;
      color: #626b73;
      font-size: 14px;
    }}
    .intro {{
      padding: 24px 36px;
      background: #edf5ef;
      border-bottom: 1px solid #d8d5cc;
    }}
    .story {{
      display: grid;
      grid-template-columns: 44px minmax(0, 1fr);
      gap: 18px;
      padding: 28px 36px;
      border-bottom: 1px solid #e6e2d9;
    }}
    .story-index {{
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: #2d6a4f;
      color: #ffffff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
    }}
    h2 {{
      margin: 0 0 8px;
      font-size: 21px;
      line-height: 1.25;
    }}
    .meta {{
      margin: 0 0 14px;
      color: #626b73;
      font-size: 14px;
    }}
    ul {{
      padding-left: 20px;
    }}
    .why {{
      background: #fff8e5;
      border-left: 4px solid #d08c00;
      padding: 10px 12px;
    }}
    a {{
      color: #1d4f91;
      font-weight: 700;
    }}
    .footer {{
      padding: 24px 36px 32px;
      color: #626b73;
      font-size: 13px;
      background: #f6f4ef;
    }}
    @media (max-width: 620px) {{
      .masthead,
      .intro,
      .story,
      .footer {{
        padding-left: 20px;
        padding-right: 20px;
      }}
      .story {{
        grid-template-columns: 1fr;
      }}
      h1 {{
        font-size: 26px;
      }}
    }}
  </style>
</head>
<body>
  <main class="email">
    <header class="masthead">
      <p class="eyebrow">Weekly Newsletter</p>
      <h1>{html.escape(subject)}</h1>
      <p class="generated">Generated {html.escape(generated_at)}</p>
    </header>
    <section class="intro">
      <p>{html.escape(intro)}</p>
    </section>
    {''.join(article_blocks)}
    <footer class="footer">
      <p>Simulated send only. Generated from goal: {html.escape(goal)}</p>
    </footer>
  </main>
</body>
</html>"""


def _build_simulated_email_header(subject: str) -> str:
    from os import getenv

    sender = getenv("NEWSLETTER_FROM", "ai-newsletter-agent@example.com")
    recipient = getenv("NEWSLETTER_TO", "subscribers@example.com")
    return "\n".join(
        [
            f"To: {recipient}",
            f"From: {sender}",
            f"Subject: {subject}",
        ]
    )
