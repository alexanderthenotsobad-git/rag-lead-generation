# Strategy Memo: Where the Lead Signal Actually Lives

**Status:** decision memo, not code. The pipeline is operational; the thesis is not.
**Bottom line:** stop leading with review-mined customer pain. Use a **menu-first funnel**:
free/cheap restaurant characteristics narrow the list, menu scoring ranks it, and paid
review enrichment is reserved for a shortlist. Keep the RAG machinery — it becomes the
enrichment and pitch layer.

---

## 1. What the current pipeline actually proves

The engineering claims hold: discovery works, HasData returns full review text, the 384-dim
index accepts review-level chunks, retrieval regroups by restaurant, and the guardrail stops
DeepSeek from inventing a pitch when the evidence is absent. That is a real, demoable system.

What it does **not** prove is that review text contains a usable buying signal. Three findings
from the existing corpus argue against it:

1. **The reviews are about the wrong things.** Upscale steakhouses, Italian spots, and Creole
   restaurants generate text about price, service, portions, ambience, and food quality. Nobody
   writes "I couldn't understand the menu" about a steakhouse.
2. **Embeddings cannot separate praise from complaint.** When the query was sharpened to target
   complaints, the top result was still a *praise* review: "options for celiacs… the staff and
   kitchen are knowledgeable and actually give a shit." Cosine similarity matches topic
   vocabulary — celiac, gluten-free, vegetarian, menu — not sentiment. A review celebrating
   accommodation ranks identically to one lamenting its absence. The generation guardrail can
   reject an obvious praise review, but retrieval has already spent its top-k slots on it, and
   subtler mixed reviews slip through. Ranking is polluted even when the pitch is not.
3. **The pain point is rare relative to the data.** Twenty restaurants × ~10 reviews ≈ 200
   reviews. The specific complaint may appear once per hundreds of restaurants. Proving or
   disproving the thesis at that base rate means scraping thousands of reviews, i.e. thousands
   of HasData credits, to find a handful of examples.

There is also a category error underneath all three: **customer pain is not a purchase reason.**
A restaurant owner does not buy a menu app because diners are confused. They buy because it
raises average check, saves staff time answering ingredient questions, reduces allergen risk,
or differentiates them from the restaurant next door. The review-mining thesis is one inferential
step removed from the buying decision, and that step is doing a lot of unexamined work.

---

## 2. The three candidate directions, scored

| | **1. Characteristic targeting** | **2. Anti-pain framing** | **3. Menu-first scoring** |
|---|---|---|---|
| **Core idea** | Filter by traits that predict fit: menu complexity, review volume, dietary-mention density | Praise of dietary accommodation is the signal; sell "amplify what you do well" | Fetch public menus; score complexity and dietary labeling directly |
| **Signal directness** | Medium — proxies for need | Medium — proves differentiation exists, not that it is lacking | **High** — measures the exact artifact the product improves |
| **Marginal data cost** | Low (Places) to medium (reviews) | High (HasData per restaurant) | **Near zero** after one-time menu fetch |
| **Coverage risk** | Low | Medium | **High** — menu acquisition is messy (PDFs, images, JS, locked pages) |
| **Pitch quality** | Weak alone — no evidence to quote | **Strong** — a real customer quote | **Strongest** — the lead's own menu is the demo asset |
| **Engineering effort** | Low | Medium (still needs sentiment classification) | **High** — scraping, PDF/OCR, LLM extraction |
| **Fatal flaw** | It is a filter, not a lead generator | Restaurants that already do this well may need the app least; weak urgency | Menus are hard to get at scale |

None of the three is sufficient alone. The mistake would be picking one and discarding the others.

---

## 3. Recommendation: a three-stage funnel

### Stage 0 — Places filter (cheap, no HasData)

Pull candidate restaurants with the fields Places already returns: price level, rating,
`userRatingCount`, cuisine types, location, website. Rank by a busyness proxy
(`userRatingCount`, weighted by rating) and by cuisine complexity (tasting menus, fusion,
multi-section menus). This is direction 1, used as top-of-funnel only.

**Why:** it is nearly free, it scales to hundreds of restaurants, and review volume is the
best available proxy for revenue at risk.

### Stage 1 — Menu scoring (the new core)

For each candidate, fetch the website and menu (HTML section, PDF, or image), then compute:

- **Menu Complexity Score (MCS):** dish count, section count, modifier/option count,
  ingredient-level description density, cuisine fusion indicators.
- **Dietary Labeling Coverage (DLC):** share of dishes with an explicit dietary or allergen
  marker (GF, V, VG, contains nuts, etc.).
- **Lead score:** `normalized(busyness) × normalized(MCS) × (1 − DLC)`.

A restaurant with 84 dishes across nine sections and three dietary labels is a far better lead
than a steakhouse with 20 dishes and no dietary vocabulary — and the former is *provable from
the menu itself*.

**Why this is the strongest signal:** the menu is the product surface. If the menu is complex
and unlabeled, the app has obvious work to do. Every lead arrives with a concrete artifact for
the pitch: "here are the 81 dishes your diners cannot self-serve."

**Operational risk and mitigation:** menu acquisition will not be 100%. Expect HTML, PDFs,
image-only menus, and third-party ordering pages. Start with the website link from Places,
follow `/menu` and PDF links, extract text with a PDF library, and treat OCR as a later
upgrade. **Measure coverage on 30 restaurants before committing.** If fewer than half of
target menus are fetchable, this direction is operationally blocked at scale.

### Stage 2 — Review enrichment (paid, shortlist only)

Only for the top 10–20 menu-scored leads, spend HasData credits. But do **not** rank with raw
cosine. Classify each review with the LLM into:

- **complaint** about menu clarity / ingredients / dietary options,
- **praise** of dietary accommodation,
- **neither**.

Then use the classified quote as pitch evidence. This fixes the praise/complaint blindness that
embeddings cannot fix, and it caps review spend at a few hundred credits per cohort instead of
thousands.

This is direction 2, demoted from thesis to enrichment. It is genuinely useful as a *quote
supply*, not as the ranking engine.

---

## 4. Reframe the pitch around the purchase decision

The current pitch says, in effect, "your customers are confused." That is an accusation with
no revenue attached. Replace it with the owner's language:

| Old frame | New frame |
|---|---|
| "Diners find your menu confusing." | "Diners with restrictions can't self-serve, so your staff absorbs the Q&A." |
| "You lack dietary labels." | "Every unlabeled dish is a table that needs a server to interpret it." |
| "Customers want healthier options." | "Dietary-aware parties are a growing check segment you can capture before they sit down." |

The pitch asset becomes the menu audit itself: "We read your 84 dishes; 81 have no ingredient
or allergen data. Here is what your diners see when they try to decide." That is specific,
verifiable, and not dependent on a stranger's review.

**Sharpen the ICP too.** Single-location fine dining is a high-CAC, low-expansion segment.
Small multi-unit groups (3–10 locations) with standardized menus are better: one sale covers
many menus, menu complexity compounds, and dietary demand is more likely to appear in reviews.

---

## 5. Validation plan (cheap, ordered, falsifiable)

The expensive mistake would be buying more reviews to test a thesis that a menu audit and five
phone calls can test for almost nothing.

**Week 1 — menu audit, 30 restaurants (no HasData spend).**
- Pull 30 Places candidates across price levels and cuisines.
- Attempt to fetch each menu; record success/failure and failure mode.
- Score MCS and DLC; eyeball whether the ranking matches intuition.
- **Gate:** if menu coverage < 50%, direction 3 cannot be the core. Fall back to direction 1
  plus review enrichment for a smaller list.

**Week 2 — owner conversations, 5–10 (no scraping).**
- Ask, don't pitch: How often do guests ask about ingredients or allergens? How much server
  time does it take? Have you lost a booking over it? What would a 5% check lift be worth?
- **Gate:** if fewer than 3 of 10 owners recognize the problem as costly, the pain thesis is
  weak regardless of what reviews say. Reframe or stop.

**Week 3 — one paid cohort, only if the gates pass.**
- 10–20 shortlisted leads, one HasData page each (100–200 credits).
- LLM-classify reviews; hand-label 50 to check classifier precision.
- **Gate:** if complaint precision < 0.8 on the hand-labeled set, do not scale HasData.

**Kill criteria, stated up front:**
- Menu coverage < 50% → direction 3 is not viable as the core.
- Owner problem recognition < 30% → the pain thesis is not a buying thesis.
- Review classifier precision < 0.8 → review enrichment cannot be trusted for pitches.
- No measurable check-size or staff-time mechanism in conversations → the product thesis needs
  rework before more lead-gen spend.

---

## 6. Cost model

| Item | Unit cost | A 30-restaurant audit | A 20-restaurant review cohort |
|---|---|---|---|
| Places Text Search | per request, 20 results | 2 requests | 1–2 requests |
| HasData reviews | 10 credits/call | 0 | 200 credits |
| Menu fetch | free (HTTP) | 30 fetches | — |
| HF embeddings | free tier / low | — | 200 chunks |
| DeepSeek | ~$0.03/month at current usage | extraction tokens only | classification + pitches |
| Pinecone | free tier | — | 384-dim index |

The menu-first funnel moves the expensive line item (HasData) from "the whole list" to "the
shortlist," which is the difference between a 1,000-credit monthly budget lasting one cohort
and lasting five.

---

## 7. What happens to the existing RAG pipeline

It is not wasted; its role changes.

- **Chunk → retrieve → group → generate** remains the right pattern, but the corpus becomes
  menu sections and dishes, not only reviews.
- The review path survives as **Stage 2 enrichment** and as the source of pitch quotes.
- The guardrail survives and becomes more important: menu-derived pitches must cite actual
  dishes, not invented ones.
- The job-market testbed is unaffected: the same architecture retrieves résumé chunks against
  a job description and generates a tailored letter. The lesson transfers — chunk the unit the
  buyer cares about, and do not trust cosine similarity for sentiment.

---

## 8. Open questions worth answering before the next build

1. **Can menus be fetched reliably enough?** This is the gating unknown. Answer it with 30
   URLs, not with architecture.
2. **What does "menu complexity" mean operationally?** Dish count is easy; "ingredient-level
   description density" needs a definition a human can apply consistently.
3. **Is dietary labeling the right axis, or is it menu *structure*?** A menu can be complex and
   well-labeled (good app fit, less urgent) or simple and unlabeled (easy app fit, low value).
   The score should be tested against owner interest, not assumed.
4. **Who is the buyer?** Owner, GM, or marketing? The pitch and the price point differ.
5. **What is the actual value claim?** Check lift, staff minutes, or allergen risk reduction —
   pick one and instrument it in the first five pilots.

---

## 9. Decision requested

Approve the funnel — **Places filter → menu scoring → shortlist review enrichment** — and the
two-week, no-HasData validation plan. The alternative, continuing to scrape reviews to prove a
rare and sentiment-blind pain point, spends the scarcest resource (credits) on the least direct
evidence.
