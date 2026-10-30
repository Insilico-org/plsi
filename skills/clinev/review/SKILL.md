---
name: review
description: Use as PLSI Clinical Evidence when the physician asks what the evidence says about an intervention, a test or a protocol - a graded, guideline-aware evidence review with harms, who should avoid it and what would change the grade, optionally against one patient's care context.
---

# PLSI clinical evidence review

Follow persona.md norms and `shared/team`. Owner: **PLSI Clinical Evidence**. Reply only in handoffs to PLSI; never message the user.
**Status: draft**; steps may change once it has been used.

## When to use

- "What is the evidence for <intervention> in <population>?", "is <test> worth ordering for <purpose>?", a question
  from `visitprep/brief`.
- Not a plan for a patient: that is `clinev/protocol`, then Nostradamus.

## Steps

1. **Frame** the question as population, intervention or test, comparison and outcome, with no patient data. When
   the request names a patient, read their context only to list what bears on the question:

   ```bash
   plsi state show --instance <label> --map care_context
   ```

2. **Search** for support, contradiction and harms; trials as registered:

   ```bash
   plsi evidence search --source pubmed --query "<intervention> <outcome> randomized OR meta-analysis" --limit 20
   plsi evidence search --source europepmc --query "<intervention> <population> guideline" --limit 20
   plsi evidence search --source ctgov --query "<intervention> <condition>" --limit 10
   plsi refs list
   ```

   An Evipedia review is PLSI's to fetch (`plsi.md` step 8); ask for it in the `result` when it would help.

3. **Verify** every identifier you cite; drop what does not resolve:

   ```bash
   plsi evidence verify --kind <pmid|doi|nct> --id <id>
   ```

4. **Write** `<PLSI_HOME>/work/<thread>/evidence-review.md`: the question; the bottom line in one sentence; grade and
   EvidenceClass (persona.md); key studies (design, n, effect with interval, identifier); harms and who should avoid
   it; the guideline position with its source, or "no guideline found" with the queries; what would change the grade;
   with a patient, what in their care context bears on it.

5. **Return one `result`** with the file and the bottom line, grade and harms in `summary`.

## Rules

- Evidence, not orders: the review never tells the physician what to prescribe.
- Contradicting findings as prominent as supporting ones; nothing verified is `Not found`, never a guess.
- Queries carry topics only, never patient data.
