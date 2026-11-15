# DSH Trajectory V1 — Five Retrieval Prompts for VRS Leads

**Scope note:** this document was produced in the **RAG LA Restaurant** workspace.
NVRS is a separate project. The prompts below are for using the RAG pipeline to
find VRS leads, not for NVRS frontend work.

**Product reference:** [NVRS Nutritional Consultant](https://alexanderthenotsobad.us/static/nvrs-details.html)

**Clarification that matters:** a prompt cannot *manufacture* a hit. In this
pipeline there are two prompts — the **retrieval query** (what evidence gets
fetched) and the **generation prompt** (how the pitch is written). Hits are
determined by retrieval. The generation guardrail is working correctly: it
refused Drago Centro and Girl & the Goat because their evidence was praise, not
pain.

The five prompts below are **retrieval queries** for `--query`. Each targets one
buyer pain that the NVRS Nutritional Consultant actually solves.

---

## 1. Allergen safety and ingredient opacity

> Customers with a food allergy or intolerance who could not get a clear answer
> about ingredients, cross-contamination, or which dishes were safe, and felt
> the staff were guessing.

**Hit looks like:** an explicit allergy plus uncertainty or a safety complaint —
“I have a shellfish allergy and the server couldn’t tell me if the sauce
contained it.”

**Pitch angle:** the consultant reads ingredient-level data and answers allergen
questions in natural language, reducing risk and server time.

**Maps to:** ingredient-level menu + Nutritional Consultant.

---

## 2. Dietary restriction gaps

> Customers who wanted vegan, vegetarian, gluten-free, or dairy-free dishes and
> found the options missing, unclear, or impossible to confirm with the staff.

**Hit looks like:** a stated restriction plus “no options,” “couldn’t confirm,”
or “the server didn’t know.”

**Pitch angle:** the consultant filters the full menu by restriction and explains
substitutions.

**Maps to:** dietary filtering.

---

## 3. Macro and health goals

> Customers looking for calorie counts, protein, carbs, or lighter and healthier
> options who could not find nutrition information or guidance on the menu.

**Hit looks like:** a macro or calorie goal plus missing nutrition data.

**Pitch angle:** the consultant reasons over ingredient-level nutrition and
recommends dishes that hit the diner’s targets.

**Maps to:** macros and nutrition.

---

## 4. Menu complexity and decision fatigue

> Customers overwhelmed by a large or complicated menu who could not decide what
> to order, did not understand the dishes, or wished someone would recommend
> something.

**Hit looks like:** “too many choices,” “overwhelming,” “couldn’t decide,”
“didn’t know what to get.”

**Pitch angle:** the consultant acts as a guide, narrows the menu, and recommends
based on stated preferences.

**Maps to:** conversational menu.

---

## 5. Group dining with mixed needs

> Customers dining in a group with different dietary needs or allergies who
> struggled to find dishes everyone could eat, or had to ask repeated questions
> to assemble an order.

**Hit looks like:** “dinner with a vegan friend,” “my wife is gluten-free,” “we
had to ask three times.”

**Pitch angle:** the consultant handles multiple diners’ needs in one
conversation.

**Maps to:** the consultant’s multi-preference reasoning.

---

## How to test them

Run each query on the same index, evidence-only first:

```bash
python query_lead.py \
  --query "Customers with a food allergy..." \
  --top-k 50 \
  --restaurants 5 \
  --no-llm
```

Then, for the ones that return actual complaints:

```bash
python query_lead.py \
  --query "Customers with a food allergy..." \
  --restaurants 5
```

Score each run as **hit restaurants ÷ retrieved restaurants**, where a hit
requires at least one complaint quote that matches the category. Compare the
five. Don’t tune the generation prompt until retrieval is producing complaints.

## What to watch for

- **One intent per query.** The current `DEFAULT_QUERY` mixes five intents into
  one sentence; that blur is why results are vague. These five split it.
- **Topic ≠ sentiment.** A query can still surface praise (“options for
  celiacs… knowledgeable”). Use `--no-llm` to inspect before trusting the pitch.
- **Don’t loosen the guardrail.** It is refusing correctly. A “hit” means
  evidence exists, not that the model was forced to speak.
- **Praise-based leads need a different objective.** If you want to sell to
  restaurants that already do dietary clarity well, that’s a separate “amplify
  what you do well” prompt — not a weaker guardrail.
- **Small sample.** Eight restaurants and 50 chunks is enough to compare
  queries, not to prove a market. Treat the best-performing query as a
  hypothesis to test on a larger, stratified sample.
