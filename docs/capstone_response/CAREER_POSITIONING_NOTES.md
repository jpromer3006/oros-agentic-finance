# Career Positioning Notes
**Date:** August 27, 2026
**Context:** Translating OROS into hiring language for an AI and ML pivot, plus what to ask each professor.

---

## 1. The single biggest reframe

Stop leading with "I built a stock analysis system." Every hiring manager in AI has seen a trading side project and most of them discount it immediately, because the category is saturated with people claiming edge they cannot support.

Lead instead with the thing that is genuinely rare:

> I built a multi agent decision system in a domain where being wrong is expensive, and then I built the instrumentation to prove whether it works. The instrumentation found that my own headline result was noise, and I published that.

That is a story about engineering judgment and intellectual honesty in a high stakes domain. It is much rarer than a trading bot, and it maps directly onto what applied AI and forward deployed roles actually screen for: can this person ship something into a real environment and then tell the truth about whether it worked.

The professors' feedback, read carefully, already says this. They praised the architectural discipline, the separation of agent nomination from deterministic sizing, the provenance commitment, and specifically your willingness to admit the record proves nothing. Three of those four are engineering character, not finance. That is the signal.

---

## 2. Translating OROS into role language

| What you built | How to say it in an AI engineering interview |
|---|---|
| Agents nominate, deterministic logic sizes | Constrained the non deterministic component to the part of the pipeline where being wrong is recoverable, and kept irreversible decisions in code that can be unit tested. This is the core safety pattern for agents in regulated settings. |
| Citation validator on every numeric claim | Built mechanical provenance enforcement rather than trusting model output, and made unsourced claims fail closed. |
| Eight interchangeable strategy books behind one registry | Designed for pluggable policy, so domain experts can add or swap decision logic without touching the orchestration layer. |
| Regime router changing strategy weights | Context conditioned routing across specialist components. |
| 1,500 decisions journaled with entry, stop and target before outcome | Built an evaluation substrate first, so the system could be measured rather than argued about. |
| The frozen benchmark that flipped sign | Ran a preregistered control and reported the negative result. |
| Point in time backtest excluding snapshot fundamentals | Identified and eliminated a lookahead leak that would have inflated results. |

Every row on the right is a transferable engineering claim. Not one of them requires the listener to care about stocks.

---

## 3. The honest gap and how to close it

The gap you already named is real: personal scale, not enterprise production. Three things close it faster than another feature.

1. **Ship the sanitized public repository.** Right now the strongest artifact you have is invisible. A public repository with the strategy registry, the backtest harness, the citation validator and the evaluation results, with a README that leads with methodology and states the negative result, is worth more than any resume bullet. It also converts the "personal scale" objection into "here is the code, read it."
2. **Close the four integrity defects and add a test suite.** `tests/` currently contains only an `__init__.py`. For a role where the screen is "can you write production code," an empty test directory in your flagship artifact is the fastest possible disqualifier. This is a two to three week fix and it changes how the repository reads.
3. **Write one public post about the frozen portfolio result.** Not a promotional post. A short technical post titled something close to "my capstone portfolio looked like it beat the market, then it did not, and nothing changed." That post will do more for your credibility with AI engineers than a demo video, because it demonstrates the one thing that is hard to fake.

---

## 4. What to ask each professor, specifically

Ask each of them for something different. A single broad ask to three people usually returns three polite generalities. Three narrow asks return three usable answers.

- **Tendü.** She led the feedback and framed the validation point. Ask her the research question: is the agent layer ablation a publishable result, and if so where. She is the one most likely to know whether this belongs at a workshop, a finance and AI venue, or nowhere yet.
- **Markus.** Ask the direction question. Academic or commercial, given the two blockers you already know about, market data licensing and investment adviser regulation. Ask specifically whether he has seen student projects clear those, because that answer is worth more than a general opinion.
- **Yilu.** Ask the career question and the blind spot question. Where does someone with deep operational domain experience and a short engineering track record fit best, and what weakness in OROS is obvious from outside that you cannot see from inside.

Send one email to all three, but address the three questions by name inside it. The current draft does this.

---

## 5. Academic or commercial: my read

The feedback language is academic. "Rigorous longitudinal validation," "evidence that the underlying approach consistently delivers value," "turning an impressive functioning system into evidence." That is a research standard of proof, not a market standard. A customer does not require a t statistic. A reviewer does.

So the honest answer is that they described an **academic** path, and the strongest version of that path is not a paper about a trading system. It is a paper about the agent ablation: in a multi agent decision system with a deterministic core, does the language model layer contribute to decision quality or only to explanation quality. That question is domain general, it is measurable with what you already have, and it is interesting to people who do not care about markets at all.

The commercial path is not closed, but it is gated by two things that are not engineering problems. Market data licensing is solvable with money. Investment adviser regulation is solvable with a lawyer and a narrower product, most plausibly by selling the research and provenance layer to advisors rather than selling recommendations to consumers. Both are worth pursuing, and neither should be pursued before the validation exists, because a product that claims edge without evidence is the version of this that ends badly.

The path that serves the career pivot fastest is neither. It is the public repository plus the honest write up, because that is what converts into interviews within weeks rather than quarters.

**Suggested sequencing:** public repository and write up now, validation study over the next four to five months, and let the study's result decide between the paper and the product rather than deciding that in advance.
