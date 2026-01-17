"""
HQ Web Learning Service - Learn from the internet.

This service searches the web for knowledge and ingests it into the
knowledge base to continuously improve the HQ AI agents.

Capabilities:
- Search for industry knowledge (dispatching, fleet management, etc.)
- Search for regulatory/compliance info (tax law, HR, accounting)
- Extract and summarize content from web pages
- Ingest learned content into the knowledge base
"""

import logging
import uuid
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.hq_knowledge_base import (
    HQKnowledgeDocument,
    KnowledgeCategory,
)
from app.services.hq_rag_service import ingest_document

logger = logging.getLogger(__name__)
settings = get_settings()


# =============================================================================
# Learning Topics Configuration
# =============================================================================

# HQ Learning Topics - For FreightOps HQ internal operations
# (Oracle, Sentinel, Nexus agents)
# Focus: HR, Marketing, Business Management, SaaS Operations, Compliance

HQ_LEARNING_TOPICS = {
    # ----- OPERATIONS (SaaS Platform) -----
    KnowledgeCategory.OPERATIONS: [
        {
            "topic": "SaaS platform operations",
            "queries": [
                "SaaS platform operations best practices",
                "SaaS infrastructure management guide",
                "API performance monitoring strategies",
                "SaaS uptime and reliability best practices",
                "incident management for SaaS platforms",
            ]
        },
        {
            "topic": "business management",
            "queries": [
                "small business management best practices",
                "startup operations management guide",
                "team management and leadership",
                "business process optimization",
                "vendor management best practices",
            ]
        },
        {
            "topic": "integration management",
            "queries": [
                "third party integration management",
                "API integration best practices",
                "webhook implementation guide",
                "integration monitoring and alerting",
                "partner integration strategy",
            ]
        },
    ],

    # ----- COMPLIANCE (Platform/Banking) -----
    KnowledgeCategory.COMPLIANCE: [
        {
            "topic": "BSA AML compliance",
            "queries": [
                "BSA AML compliance requirements fintech",
                "KYB know your business verification",
                "suspicious activity report SAR filing",
                "customer due diligence CDD requirements",
                "beneficial ownership requirements",
            ]
        },
        {
            "topic": "data privacy compliance",
            "queries": [
                "data privacy compliance guide",
                "GDPR compliance for SaaS",
                "CCPA California privacy compliance",
                "data protection best practices",
                "privacy policy requirements",
            ]
        },
        {
            "topic": "SOC 2 compliance",
            "queries": [
                "SOC 2 compliance requirements guide",
                "SOC 2 Type 2 audit preparation",
                "security controls for SOC 2",
                "SaaS security best practices",
                "information security policies",
            ]
        },
    ],

    # ----- TAXES (Business) -----
    KnowledgeCategory.TAXES: [
        {
            "topic": "payroll taxes",
            "queries": [
                "payroll tax compliance guide 2024 2025",
                "federal payroll tax deposit requirements",
                "Form 941 quarterly filing guide",
                "state payroll tax requirements",
                "payroll tax penalties and how to avoid",
            ]
        },
        {
            "topic": "business taxes",
            "queries": [
                "small business tax planning strategies",
                "quarterly estimated tax payments",
                "business tax deductions guide",
                "state and local business taxes",
                "tax planning for startups",
            ]
        },
        {
            "topic": "sales tax SaaS",
            "queries": [
                "SaaS sales tax requirements by state",
                "digital goods taxation",
                "nexus rules for SaaS companies",
                "sales tax automation for SaaS",
                "marketplace facilitator laws",
            ]
        },
    ],

    # ----- ACCOUNTING (SaaS) -----
    KnowledgeCategory.ACCOUNTING: [
        {
            "topic": "SaaS accounting",
            "queries": [
                "SaaS revenue recognition ASC 606",
                "deferred revenue accounting SaaS",
                "SaaS metrics MRR ARR calculation",
                "SaaS financial statements guide",
                "subscription billing accounting",
            ]
        },
        {
            "topic": "financial reporting",
            "queries": [
                "GAAP financial statements preparation",
                "cash flow statement analysis",
                "accounts receivable management best practices",
                "financial ratio analysis guide",
                "budgeting and forecasting best practices",
            ]
        },
        {
            "topic": "startup finance",
            "queries": [
                "startup financial planning guide",
                "burn rate and runway calculation",
                "cap table management",
                "fundraising financial preparation",
                "unit economics SaaS",
            ]
        },
    ],

    # ----- HR (Internal) -----
    KnowledgeCategory.HR: [
        {
            "topic": "hiring and recruiting",
            "queries": [
                "tech hiring best practices",
                "interview process optimization",
                "remote hiring guide",
                "employer branding strategies",
                "recruiting metrics and KPIs",
            ]
        },
        {
            "topic": "employment law",
            "queries": [
                "employment law compliance guide 2024 2025",
                "FLSA overtime rules explained",
                "employee vs contractor classification",
                "wrongful termination prevention",
                "workplace harassment prevention",
            ]
        },
        {
            "topic": "employee benefits",
            "queries": [
                "startup employee benefits guide",
                "equity compensation explained",
                "401k plan administration guide",
                "PTO policy best practices",
                "remote work policies",
            ]
        },
        {
            "topic": "performance management",
            "queries": [
                "performance review best practices",
                "employee feedback systems",
                "goal setting frameworks OKR",
                "employee development programs",
                "compensation planning guide",
            ]
        },
    ],

    # ----- PAYROLL (Internal) -----
    KnowledgeCategory.PAYROLL: [
        {
            "topic": "payroll processing",
            "queries": [
                "payroll processing best practices",
                "direct deposit setup guide",
                "payroll deductions explained",
                "garnishment processing requirements",
                "multi-state payroll compliance",
            ]
        },
        {
            "topic": "compensation strategy",
            "queries": [
                "compensation benchmarking guide",
                "salary band creation",
                "bonus structure design",
                "equity compensation planning",
                "total rewards strategy",
            ]
        },
    ],

    # ----- MARKETING (SaaS) -----
    KnowledgeCategory.MARKETING: [
        {
            "topic": "SaaS marketing",
            "queries": [
                "SaaS marketing strategy guide 2024 2025",
                "B2B SaaS lead generation",
                "SaaS customer acquisition strategies",
                "content marketing for SaaS",
                "SaaS pricing strategies",
            ]
        },
        {
            "topic": "customer success",
            "queries": [
                "customer success best practices SaaS",
                "reducing churn SaaS strategies",
                "customer onboarding best practices",
                "NPS and customer satisfaction metrics",
                "upselling and cross-selling strategies",
            ]
        },
        {
            "topic": "growth marketing",
            "queries": [
                "product led growth strategy",
                "SaaS growth hacking techniques",
                "referral program design",
                "conversion rate optimization SaaS",
                "marketing automation for SaaS",
            ]
        },
        {
            "topic": "sales enablement",
            "queries": [
                "B2B SaaS sales process",
                "sales demo best practices",
                "sales objection handling",
                "proposal and contract management",
                "CRM best practices",
            ]
        },
    ],
}

# Tenant Learning Topics - For trucking company tenants
# (Annie, Atlas, Alex, Adam, Harper, Felix agents)
# Focus: Dispatching, Fleet Management, DOT Compliance, IFTA, Driver Management

TENANT_LEARNING_TOPICS = {
    # ----- OPERATIONS (Trucking) -----
    "operations": [
        {
            "topic": "freight dispatching",
            "queries": [
                "how to be a freight dispatcher complete guide",
                "freight dispatcher responsibilities and duties",
                "dispatch software best practices trucking",
                "load planning and optimization strategies",
                "driver communication best practices dispatch",
            ]
        },
        {
            "topic": "fleet management",
            "queries": [
                "fleet management best practices 2024 2025",
                "fleet maintenance scheduling strategies",
                "fleet fuel efficiency optimization",
                "telematics and ELD integration fleet",
                "fleet safety programs and compliance",
            ]
        },
        {
            "topic": "trucking operations",
            "queries": [
                "trucking company operations management",
                "freight capacity planning strategies",
                "deadhead miles reduction techniques",
                "lane optimization trucking",
                "freight rate negotiation strategies",
            ]
        },
        {
            "topic": "load management",
            "queries": [
                "load board best practices trucking",
                "freight matching strategies",
                "backhaul optimization techniques",
                "load weight and dimensions management",
                "hazmat load requirements",
            ]
        },
    ],

    # ----- COMPLIANCE (DOT/FMCSA) -----
    "compliance": [
        {
            "topic": "DOT compliance",
            "queries": [
                "DOT compliance requirements trucking 2024 2025",
                "FMCSA regulations motor carriers",
                "CSA scores and safety ratings explained",
                "drug and alcohol testing requirements DOT",
                "driver qualification file requirements",
            ]
        },
        {
            "topic": "hours of service",
            "queries": [
                "hours of service rules 2024 2025",
                "HOS exceptions and exemptions",
                "ELD mandate compliance requirements",
                "sleeper berth provisions explained",
                "personal conveyance rules trucking",
            ]
        },
        {
            "topic": "safety compliance",
            "queries": [
                "trucking safety audit preparation",
                "roadside inspection preparation",
                "accident reporting requirements trucking",
                "driver safety training programs",
                "cargo securement requirements",
            ]
        },
    ],

    # ----- TAXES (Trucking) -----
    "taxes": [
        {
            "topic": "IFTA reporting",
            "queries": [
                "IFTA fuel tax reporting guide",
                "IFTA quarterly filing requirements",
                "IFTA fuel tax calculation methods",
                "IFTA record keeping requirements",
                "IFTA audit preparation tips",
            ]
        },
        {
            "topic": "trucking taxes",
            "queries": [
                "heavy vehicle use tax form 2290",
                "trucking company tax deductions",
                "per diem tax rules truck drivers",
                "depreciation rules commercial vehicles",
                "fuel tax credits trucking",
            ]
        },
        {
            "topic": "owner operator taxes",
            "queries": [
                "owner operator tax guide",
                "self employment tax trucking",
                "truck driver expense deductions",
                "quarterly tax payments trucking",
                "home office deduction trucking",
            ]
        },
    ],

    # ----- ACCOUNTING (Trucking) -----
    "accounting": [
        {
            "topic": "trucking accounting",
            "queries": [
                "trucking company bookkeeping guide",
                "owner operator accounting basics",
                "freight factoring accounting treatment",
                "trucking company chart of accounts",
                "fuel card reconciliation best practices",
            ]
        },
        {
            "topic": "cost analysis",
            "queries": [
                "cost per mile calculation trucking",
                "trucking profit margins analysis",
                "fuel cost management strategies",
                "maintenance cost tracking",
                "driver pay cost analysis",
            ]
        },
    ],

    # ----- DRIVER MANAGEMENT -----
    "driver_management": [
        {
            "topic": "driver hiring",
            "queries": [
                "CDL driver hiring process guide",
                "driver recruitment strategies trucking",
                "driver retention best practices",
                "driver background check requirements",
                "driver onboarding checklist",
            ]
        },
        {
            "topic": "driver pay",
            "queries": [
                "truck driver pay structures explained",
                "driver pay per mile calculation",
                "driver settlement sheet explained",
                "accessorial pay trucking",
                "driver bonus programs best practices",
            ]
        },
        {
            "topic": "driver compliance",
            "queries": [
                "CDL requirements and endorsements",
                "medical card requirements drivers",
                "driver training documentation",
                "driver file audit checklist",
                "driver performance monitoring",
            ]
        },
    ],

    # ----- EQUIPMENT -----
    "equipment": [
        {
            "topic": "equipment maintenance",
            "queries": [
                "truck preventive maintenance schedule",
                "trailer maintenance checklist",
                "DOT inspection requirements equipment",
                "fleet maintenance software guide",
                "equipment lifecycle management",
            ]
        },
        {
            "topic": "equipment purchasing",
            "queries": [
                "buying vs leasing trucks guide",
                "used truck inspection checklist",
                "truck financing options",
                "trailer specification guide",
                "equipment depreciation strategies",
            ]
        },
    ],
}

# Default to HQ topics for this service
LEARNING_TOPICS = HQ_LEARNING_TOPICS


# =============================================================================
# Web Search Functions
# =============================================================================

async def search_tavily(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search the web using Tavily API.

    Returns list of search results with title, url, and content.
    """
    api_key = settings.tavily_api_key
    if not api_key:
        logger.warning("No Tavily API key configured")
        return []

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "include_answer": True,
                    "include_raw_content": False,
                    "max_results": num_results,
                },
                timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                results = []

                # Include the AI-generated answer if available
                if data.get("answer"):
                    results.append({
                        "title": f"Summary: {query}",
                        "url": "tavily_answer",
                        "content": data["answer"],
                        "score": 1.0,
                    })

                # Add search results
                for result in data.get("results", []):
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "content": result.get("content", ""),
                        "score": result.get("score", 0),
                    })

                return results
            else:
                logger.error(f"Tavily search error: {response.status_code}")
                return []

    except Exception as e:
        logger.error(f"Tavily search error: {e}")
        return []


async def fetch_and_summarize_url(url: str, topic: str) -> Optional[str]:
    """
    Fetch a URL and summarize its content using Grok.

    Returns summarized content suitable for knowledge base.
    """
    if url == "tavily_answer":
        return None  # Skip, already have content

    grok_key = settings.grok_api_key or settings.xai_api_key
    if not grok_key:
        return None

    try:
        # Fetch the page content
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=15.0, follow_redirects=True)
            if response.status_code != 200:
                return None

            # Get text content (basic extraction)
            content = response.text[:10000]  # Limit size

            # Use Grok to summarize
            summary_response = await client.post(
                f"{settings.grok_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {grok_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": settings.grok_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": f"""You are a knowledge extraction assistant. Extract and summarize the key information from this web page about "{topic}".

Format the output as structured knowledge that would be useful for training an AI assistant. Include:
- Key concepts and definitions
- Step-by-step processes or procedures
- Best practices and recommendations
- Important rules, regulations, or requirements
- Common mistakes to avoid

Be factual and comprehensive. Use bullet points and headers for organization."""
                        },
                        {
                            "role": "user",
                            "content": f"Extract knowledge from this content:\n\n{content}"
                        }
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.3
                },
                timeout=60.0
            )

            if summary_response.status_code == 200:
                data = summary_response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    except Exception as e:
        logger.warning(f"Error fetching/summarizing {url}: {e}")

    return None


# =============================================================================
# Learning Functions
# =============================================================================

async def learn_from_web(
    db: AsyncSession,
    category: KnowledgeCategory,
    topic: str,
    queries: List[str],
    max_results_per_query: int = 3,
) -> Dict[str, Any]:
    """
    Learn about a topic by searching the web and ingesting content.

    Args:
        db: Database session
        category: Knowledge category
        topic: Topic name
        queries: List of search queries
        max_results_per_query: Max results per query

    Returns:
        Summary of what was learned
    """
    logger.info(f"Learning about: {topic} ({category.value})")

    all_content = []
    sources = []

    for query in queries:
        logger.info(f"  Searching: {query}")
        results = await search_tavily(query, num_results=max_results_per_query)

        for result in results:
            if result["content"]:
                all_content.append(f"## {result['title']}\n\n{result['content']}")
                if result["url"] != "tavily_answer":
                    sources.append(result["url"])

    if not all_content:
        logger.warning(f"  No content found for topic: {topic}")
        return {"status": "no_content", "topic": topic}

    # Combine all content into a document
    combined_content = f"""# {topic.title()}

This knowledge was gathered from web research on {datetime.utcnow().strftime('%Y-%m-%d')}.

""" + "\n\n---\n\n".join(all_content)

    # Check if we already have a document for this topic
    existing = await db.execute(
        select(HQKnowledgeDocument).where(
            and_(
                HQKnowledgeDocument.title.ilike(f"%{topic}%"),
                HQKnowledgeDocument.category == category
            )
        )
    )
    existing_doc = existing.scalar_one_or_none()

    if existing_doc:
        # Update existing document
        existing_doc.content = combined_content
        existing_doc.source = f"Web Research ({len(sources)} sources)"
        existing_doc.updated_at = datetime.utcnow()
        await db.commit()
        logger.info(f"  Updated existing document: {existing_doc.id}")
        return {
            "status": "updated",
            "topic": topic,
            "document_id": existing_doc.id,
            "sources_count": len(sources),
        }
    else:
        # Create new document
        doc = await ingest_document(
            db=db,
            title=f"Web Research: {topic.title()}",
            content=combined_content,
            category=category,
            source=f"Web Research ({len(sources)} sources)",
        )

        if doc:
            logger.info(f"  Created new document: {doc.id}")
            return {
                "status": "created",
                "topic": topic,
                "document_id": doc.id,
                "sources_count": len(sources),
            }
        else:
            return {"status": "failed", "topic": topic}


async def learn_category(
    db: AsyncSession,
    category: KnowledgeCategory,
) -> List[Dict[str, Any]]:
    """Learn all topics for a category."""
    topics = LEARNING_TOPICS.get(category, [])
    results = []

    for topic_config in topics:
        result = await learn_from_web(
            db=db,
            category=category,
            topic=topic_config["topic"],
            queries=topic_config["queries"],
        )
        results.append(result)

    return results


async def learn_all_topics(db: AsyncSession) -> Dict[str, Any]:
    """
    Learn all configured topics from the web.

    This is the main entry point for comprehensive learning.
    """
    logger.info("=" * 60)
    logger.info("Starting comprehensive web learning")
    logger.info("=" * 60)

    all_results = {}
    total_created = 0
    total_updated = 0
    total_failed = 0

    for category, topics in LEARNING_TOPICS.items():
        logger.info(f"\nCategory: {category.value}")
        category_results = []

        for topic_config in topics:
            result = await learn_from_web(
                db=db,
                category=category,
                topic=topic_config["topic"],
                queries=topic_config["queries"],
            )
            category_results.append(result)

            if result["status"] == "created":
                total_created += 1
            elif result["status"] == "updated":
                total_updated += 1
            else:
                total_failed += 1

        all_results[category.value] = category_results

    summary = {
        "completed_at": datetime.utcnow().isoformat(),
        "total_topics": sum(len(topics) for topics in LEARNING_TOPICS.values()),
        "documents_created": total_created,
        "documents_updated": total_updated,
        "failed": total_failed,
        "results_by_category": all_results,
    }

    logger.info("\n" + "=" * 60)
    logger.info("Learning complete!")
    logger.info(f"Created: {total_created}, Updated: {total_updated}, Failed: {total_failed}")
    logger.info("=" * 60)

    return summary


async def learn_specific_topic(
    db: AsyncSession,
    topic: str,
    category: KnowledgeCategory,
    custom_queries: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Learn about a specific topic with custom queries.

    Args:
        db: Database session
        topic: Topic to learn about
        category: Knowledge category
        custom_queries: Optional custom search queries

    Returns:
        Learning result
    """
    if custom_queries:
        queries = custom_queries
    else:
        # Generate queries from topic
        queries = [
            f"{topic} complete guide",
            f"{topic} best practices",
            f"{topic} requirements",
            f"how to {topic}",
            f"{topic} tips and strategies",
        ]

    return await learn_from_web(
        db=db,
        category=category,
        topic=topic,
        queries=queries,
    )


# =============================================================================
# Research Functions (for agents to use)
# =============================================================================

async def research_topic(query: str, num_results: int = 5) -> str:
    """
    Research a topic and return formatted results.

    This is designed for agents to call when they need current information.
    """
    results = await search_tavily(query, num_results=num_results)

    if not results:
        return f"No results found for: {query}"

    formatted = [f"# Research Results: {query}\n"]

    for i, result in enumerate(results, 1):
        formatted.append(f"## {i}. {result['title']}")
        formatted.append(f"Source: {result['url']}")
        formatted.append(f"\n{result['content']}\n")

    return "\n".join(formatted)
