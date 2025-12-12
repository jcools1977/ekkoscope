# EkkoScope Technical Whitepaper
## Generative Engine Optimization (GEO) Platform for AI Visibility Analysis

**Version 1.0 | December 2025**

---

## Abstract

EkkoScope is a software platform that measures how frequently a business is mentioned by AI assistants (ChatGPT, Perplexity, Gemini) in response to industry-relevant queries. The platform generates structured queries, submits them to multiple AI providers via their APIs, parses the responses to detect brand mentions, and calculates a visibility score based on the ratio of mentions to total probes. This whitepaper describes the technical methodology, scoring algorithms, and analytical capabilities implemented in the system.

---

## 1. Problem Statement

Large Language Models (LLMs) increasingly influence consumer decisions through conversational AI assistants. When users ask questions like "What's the best roofing company in Charleston?" or "Where can I buy bulk packaging supplies?", AI systems generate recommendations based on their training data and real-time web access capabilities.

Businesses have limited visibility into whether they appear in these AI-generated recommendations. Traditional SEO metrics do not capture AI assistant behavior, as LLMs synthesize responses rather than returning ranked links.

EkkoScope addresses this gap by programmatically querying AI providers and measuring brand presence in their responses.

---

## 2. System Architecture

### 2.1 Core Components

| Component | Function | Technology |
|-----------|----------|------------|
| Query Generator | Creates industry-specific search queries with intent classification | Python, template-based generation |
| Visibility Hub | Orchestrates API calls to multiple AI providers | Async Python, httpx |
| Response Parser | Extracts brand mentions from AI responses | JSON parsing, string matching |
| Scoring Engine | Calculates visibility metrics using deterministic math | Python arithmetic |
| Report Generator | Produces PDF reports with analysis results | FPDF2 library |
| Sherlock Engine | Semantic gap analysis using vector embeddings | Pinecone, OpenAI embeddings |

### 2.2 Data Flow

```
Business Configuration → Query Generation → Multi-Provider API Calls → 
Response Parsing → Brand Detection → Visibility Scoring → Report Generation
```

---

## 3. Query Generation Methodology

### 3.1 Intent Classification System

EkkoScope classifies queries into five intent categories, each assigned a business value score:

| Intent Type | Description | Value Score (1-10) |
|-------------|-------------|-------------------|
| Emergency | Urgent, immediate-need situations | 10 |
| High Ticket | Large purchases or contracts | 9 |
| Transactional | Ready-to-buy queries | 8 |
| Replenishment | Regular, recurring purchases | 7 |
| Informational | Research and comparison queries | 5 |

### 3.2 Query Template System

Queries are generated from templates customized by:
- **Business Type**: E-commerce, Local Service, B2B Service
- **Category**: Industry-specific keywords (e.g., "roofing", "packaging supplies")
- **Region**: Geographic location (e.g., "Charleston SC", "United States")

**Example Templates (E-commerce):**
```
"best place to buy {category} online"
"bulk {category} supplier for businesses"
"{category} supplier for {use_case}"
```

**Example Templates (Local Service):**
```
"best {category} in {region}"
"emergency {category} near {region}"
"top {category} company in {region}"
```

### 3.3 Query Volume

Each audit generates 25-50 unique queries per provider, resulting in 75-150 total probes across three AI providers.

---

## 4. AI Provider Integration

### 4.1 Supported Providers

| Provider | API Type | Capability |
|----------|----------|------------|
| OpenAI (GPT-4) | Chat Completions API | Knowledge cutoff-based recommendations |
| Perplexity | Sonar API | Real-time web search with citations |
| Google Gemini | Generative AI API | Knowledge-based recommendations |

### 4.2 Prompt Engineering

Each provider receives a structured prompt requesting recommendations in JSON format:

```
You are an AI assistant helping a user find businesses.
Query: "{query}"
Target Business: "{business_name}"

Return a JSON object with:
- recommended_brands: Array of {name, url, reason}
- target_business_mentioned: boolean
- target_position: integer (1-based rank if mentioned)
```

### 4.3 Response Parsing

The parser extracts:
1. **recommended_brands**: List of businesses mentioned
2. **target_business_mentioned**: Boolean indicating presence
3. **target_position**: Rank position (1 = primary recommendation)

Secondary detection: If the AI does not explicitly flag the target, the parser performs string matching on brand names within the recommendations list.

---

## 5. Visibility Scoring Algorithm

### 5.1 Calculation Method

EkkoScope uses **provider-response level** scoring, not query-level:

```
Visibility Score = (Total Provider Hits / Total Provider Probes) × 100
```

**Where:**
- **Total Provider Probes** = Number of queries × Number of providers with successful responses
- **Total Provider Hits** = Count of responses where target business was mentioned

### 5.2 Example Calculation

| Metric | Value |
|--------|-------|
| Queries | 50 |
| Providers | 3 (OpenAI, Perplexity, Gemini) |
| Successful Probes | 147 |
| Times Mentioned | 9 |
| **Visibility Score** | 9 / 147 = **6.1%** |

### 5.3 Risk Level Classification

| Score Range | Risk Level |
|-------------|------------|
| 0% | CRITICAL |
| 1-19% | HIGH |
| 20-49% | MODERATE |
| 50%+ | LOW |

### 5.4 Data Integrity Guardrails

The system implements strict mathematical verification to prevent inaccurate reporting:

1. **Primary Calculation**: Uses raw probe data from database
2. **Override Protection**: Rejects LLM-generated narrative if it conflicts with calculated score
3. **Forced Correction**: If calculated score is 0% but narrative says "dominating", the system overwrites with accurate text
4. **Template-Based Narratives**: Critical scores trigger deterministic text generation (no LLM involvement)

---

## 6. Per-Provider Analysis

### 6.1 Provider-Specific Scores

Each provider is scored independently:

```python
Provider Score = (Provider Hits / Provider Probes) × 100
```

### 6.2 Behavioral Differences

| Provider | Behavior Pattern |
|----------|------------------|
| **Perplexity** | Real-time web search; higher visibility for businesses with strong web presence |
| **OpenAI (GPT-4)** | Training data dependent; favors well-known brands in training corpus |
| **Gemini** | Hybrid approach; knowledge-based with some real-time capability |

---

## 7. Competitor Analysis

### 7.1 Detection Method

For each query, the system records all non-target brands mentioned in AI responses:

```python
for brand in recommended_brands:
    if brand.name != target_business:
        competitor_counts[brand.name] += 1
```

### 7.2 Competitor Metrics

| Metric | Description |
|--------|-------------|
| Mention Count | Times competitor appeared across all probes |
| Market Share | Competitor mentions / Total probes |
| Threat Level | Based on frequency relative to target |

---

## 8. Sherlock Semantic Intelligence Engine

### 8.1 Purpose

Sherlock identifies **topics** (not keywords) that competitors cover but the client does not. This addresses the limitation of traditional keyword tools that miss semantic meaning.

### 8.2 Technical Implementation

**Vector Database**: Pinecone (serverless)
**Embedding Model**: OpenAI `text-embedding-3-large` (3072 dimensions)
**Index**: `ekkobrain` with namespaces for client content, competitor content, and gap missions

### 8.3 Content Ingestion Pipeline

```
URL → Web Scrape → Extract Text → GPT Topic Extraction → 
Vector Embedding → Pinecone Upsert
```

**Topic Extraction Prompt:**
```
Analyze this website content and extract the main TOPICS covered.
Not keywords - identify the semantic concepts, themes, and subject areas.

For each topic, provide:
1. topic: A clear topic name (2-5 words)
2. category: The broader category (e.g., "services", "problems", "solutions")
3. depth: How thoroughly covered (1-10)
4. example_phrases: 2-3 key phrases from the content
```

### 8.4 Gap Analysis Algorithm

1. Retrieve client topics from ingested content
2. Retrieve competitor topics from ingested content
3. Identify topics present in competitor data but absent/weak in client data
4. Rank gaps by potential business value

**Output:**
- Missing topics (competitor has, client lacks)
- Weak topics (client has but competitor covers more deeply)
- Coverage comparison scores

---

## 9. PDF Report Generation

### 9.1 Standard GEO Report Sections

1. **Cover Page**: Business name, report date, market focus
2. **Executive Dashboard**: Key metrics (visibility %, primary recommendations, average score)
3. **Query Analysis**: Per-query breakdown with provider results
4. **Competitor Matrix**: Top competitors by mention frequency
5. **Multi-Source Visibility**: Provider comparison chart
6. **Genius Insights**: AI-generated strategic recommendations
7. **Page Blueprints**: Content specifications for new pages
8. **30-Day Action Plan**: Phased implementation tasks
9. **Recommendations**: Prioritized optimization actions

### 9.2 Report Technology

- **Library**: FPDF2 (Python)
- **Typography**: JetBrains Mono
- **Color Scheme**: Dark theme with cyan accents (#00F0FF)

---

## 10. Limitations and Accuracy Considerations

### 10.1 What EkkoScope Measures

EkkoScope measures **AI API response content** at the time of query execution. This represents how AI assistants respond to specific prompts under specific conditions.

### 10.2 What EkkoScope Does Not Measure

- End-user AI assistant interactions (which may differ due to personalization)
- Voice assistant responses (Siri, Alexa)
- AI responses in non-English languages (unless configured)
- Real-time changes in AI model behavior

### 10.3 Variability Factors

AI responses may vary based on:
- Model version updates
- API parameter settings (temperature, etc.)
- Time of query (for providers with real-time search)
- Geographic location signals

### 10.4 Reproducibility

Each audit stores:
- Raw API responses
- Parsed data
- Calculated scores
- Timestamp

Re-running the same queries may produce different results as AI models update.

---

## 11. Data Storage and Privacy

### 11.1 Data Persistence

| Data Type | Storage | Retention |
|-----------|---------|-----------|
| Business Configuration | SQLite | Permanent |
| Audit Results | SQLite | Permanent |
| Query Responses | SQLite (JSON) | Permanent |
| PDF Reports | Filesystem | Permanent |
| Vector Embeddings | Pinecone | Permanent |

### 11.2 API Key Handling

API keys are stored as environment secrets and never logged or exposed in responses.

---

## 12. Pricing Tiers and Capabilities

| Tier | Price | Capability |
|------|-------|------------|
| Full Report | $490 one-time | Single comprehensive audit with PDF |
| Continuous Monitoring | $290/month | Bi-weekly audits with trend tracking |
| Auto-Fix Agents | $1,188/month | Reports + AI agents generate remediation assets |

---

## 13. Technical Specifications

| Specification | Value |
|---------------|-------|
| Backend Framework | FastAPI + Uvicorn |
| Python Version | 3.11+ |
| Database | SQLite (SQLAlchemy ORM) |
| Vector Database | Pinecone |
| Embedding Dimensions | 3072 |
| PDF Library | FPDF2 |
| Payment Processing | Stripe |
| Max Queries per Audit | 50 per provider |
| Supported Providers | OpenAI, Perplexity, Gemini |

---

## 14. Conclusion

EkkoScope provides a systematic method for measuring business visibility within AI assistant recommendations. The platform's value lies in:

1. **Quantification**: Converting qualitative AI behavior into measurable metrics
2. **Multi-Provider Analysis**: Comparing visibility across different AI ecosystems
3. **Intent Classification**: Prioritizing high-value query types
4. **Semantic Gap Analysis**: Identifying content opportunities through vector similarity
5. **Data Integrity**: Ensuring reported scores match calculated values through automated verification

The visibility scores reflect actual API responses at query time and provide businesses with data to inform content strategy decisions.

---

## Appendix A: Scoring Formula Reference

```
Overall Visibility = Σ(is_target_found) / Σ(successful_probes) × 100

Provider Visibility = Σ(provider_target_found) / Σ(provider_probes) × 100

Query Score = 
  2 if target is primary recommendation
  1 if target is mentioned (not primary)
  0 if target not mentioned
```

## Appendix B: Intent Template Count

| Intent Type | Template Count |
|-------------|----------------|
| Emergency | 4 |
| High Ticket | 6 |
| Replenishment | 5 |
| Informational | 6 |
| Transactional | 5 |

---

*Document generated from EkkoScope codebase analysis*
*All technical claims verified against implemented functionality*
