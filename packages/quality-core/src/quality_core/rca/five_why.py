"""
five_why.py
Deterministic 5-Why Root Cause Analysis (RCA) validator and scoring engine.

Implements forward causal continuity checking ("Why -> Because"), reverse bottom-up
logical necessity evaluation ("Because -> Therefore" per AIAG CQI-20 Step 5 / RULE 3),
anti-pattern detection (circular reasoning, superficial/blame-terminal operator causes
per ASQ Quality Toolbox & Ford Global 8D / RULE 4, premature termination, non-causal jumps),
systemic root cause classification, reversibility scoring, and actionable recommendation generation.

Standards References:
- AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018), Section 5.
- Ford Motor Company, Global 8D (G8D) Problem Solving Manual, Section D4 & D7.
- Nancy R. Tague, The Quality Toolbox (2nd Edition, ASQ Quality Press, 2005), Chapter 5.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from quality_core.rca.schema import validate_five_why

__all__ = [
    "AntiPatternFinding",
    "FiveWhyLinkEval",
    "FiveWhyValidationResult",
    "SystemicAssessment",
    "validate_five_why_chain",
]

_STANDARDS_BASIS = "AIAG CQI-20 / Ford Global 8D / ASQ Quality Toolbox"

_STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll",
    "they're", "they've", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves",
}

_SYSTEMIC_TERMS = {
    "procedure", "policy", "system", "training", "induction", "engineering",
    "standard", "standardized", "poka", "yoke", "pokayoke", "error-proof",
    "errorproofing", "mistake-proof", "checklist", "sign-off", "signed",
    "specification", "instruction", "management", "maintenance plan",
    "autonomous maintenance", "audit", "work instruction", "preventative",
    "preventive", "schedule", "verification", "process control", "design",
    "guideline", "documentation", "governance", "inspection plan",
}

_HUMAN_NOUNS = {
    "operator", "worker", "technician", "employee", "person", "personnel",
    "user", "machinist", "assembler", "inspector", "who",
}

_BLAME_VERBS = {
    "forgot", "forgotten", "neglected", "careless", "carelessness", "inattentive",
    "inattention", "overlooked", "missed", "omitted", "erred", "mistake",
    "error", "fault", "failed to follow", "did not follow", "ignored",
    "disregarded", "skipped",
}


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric words."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    return [w for w in cleaned.split() if w]


def _stem(word: str) -> str:
    """Lightweight suffix stemmer for quality engineering terminology."""
    w = word.lower()
    if len(w) <= 3:
        return w
    for suffix in ("ing", "ation", "ition", "ment", "able", "ible", "ies", "ied", "ed", "es", "s", "al", "ly"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 2:
            base = w[:-len(suffix)]
            if suffix in ("ied", "ies"):
                return base + "y"
            return base
    return w


def _content_tokens(text: str) -> set[str]:
    """Extract content words excluding stop words and single-character tokens."""
    return {_stem(w) for w in _tokenize(text) if w not in _STOP_WORDS and len(w) > 1}


def _jaccard_similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Compute Jaccard similarity coefficient between two token sets."""
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union > 0 else 0.0


def _is_human_blame_statement(text: str) -> bool:
    """Check if a statement attributes root cause to individual human error."""
    text_lower = text.lower()
    tokens = set(_tokenize(text_lower))
    has_human_noun = bool(tokens & _HUMAN_NOUNS)
    has_blame_verb = bool(tokens & _BLAME_VERBS)

    phrases = (
        "operator error", "human error", "worker error", "technician error",
        "operator mistake", "worker mistake", "carelessness", "lack of attention",
        "forgot to", "did not follow", "failed to follow", "not paying attention",
    )
    has_phrase = any(p in text_lower for p in phrases)

    return (has_human_noun and has_blame_verb) or has_phrase


def _has_systemic_resolution(text: str) -> bool:
    """Check if a statement contains systemic process, training, or policy factors."""
    tokens = set(_tokenize(text.lower()))
    if tokens & _SYSTEMIC_TERMS:
        return True
    phrases = (
        "poka yoke", "poka-yoke", "error proof", "error-proof", "sign off",
        "sign-off", "work instruction", "maintenance plan", "maintenance routine",
        "training program", "induction program", "standard work",
    )
    return any(p in text.lower() for p in phrases)


@dataclass
class FiveWhyLinkEval:
    """Evaluation of a single step link in a 5-Why causal chain."""

    step_number: int
    why: str
    because: str
    reverse_statement: str
    is_reversible: bool
    reversibility_score: float
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of link evaluation."""
        return asdict(self)


@dataclass
class AntiPatternFinding:
    """Finding representing an identified anti-pattern in the causal chain."""

    code: str
    severity: Literal["error", "warning", "info"]
    step_number: int | None
    message: str
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of anti-pattern finding."""
        return asdict(self)


@dataclass
class SystemicAssessment:
    """Classification and assessment of the root cause level."""

    classification: Literal["SYSTEMIC", "TECHNICAL_PROCESS", "HUMAN_INDIVIDUAL"]
    is_systemic: bool
    terminal_cause: str
    systemic_factors: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of systemic assessment."""
        return asdict(self)


@dataclass
class FiveWhyValidationResult:
    """Complete validation result for a 5-Why causal chain."""

    basis: str
    valid: bool
    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    reversibility_score: float
    problem_statement: str
    root_cause: str
    total_steps: int
    link_evaluations: list[FiveWhyLinkEval]
    anti_patterns: list[AntiPatternFinding]
    systemic_assessment: SystemicAssessment
    recommendations: list[str]
    leg_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of validation result."""
        return {
            "basis": self.basis,
            "valid": self.valid,
            "verdict": self.verdict,
            "reversibility_score": self.reversibility_score,
            "problem_statement": self.problem_statement,
            "root_cause": self.root_cause,
            "total_steps": self.total_steps,
            "link_evaluations": [e.to_dict() for e in self.link_evaluations],
            "anti_patterns": [p.to_dict() for p in self.anti_patterns],
            "systemic_assessment": self.systemic_assessment.to_dict(),
            "recommendations": list(self.recommendations),
            "leg_type": self.leg_type,
        }


def validate_five_why_chain(
    data: Any,
    problem_statement: str = "Problem Statement",
    root_cause: str | None = None,
    leg_type: str | None = None,
) -> FiveWhyValidationResult:
    """Validate a 5-Why causal chain for forward consistency, reverse logic, and anti-patterns.

    Ingests untrusted 5-Why data (FiveWhyChain, DataFrame, list of dicts/steps, or dict),
    enforces structural constraints via `quality_core.rca.schema.validate_five_why`, evaluates
    forward link progression ("Why -> Because") and reverse bottom-up necessity ("Because -> Therefore"
    per AIAG CQI-20 Step 5), detects anti-patterns (circular reasoning, superficial/terminal operator
    error per ASQ Quality Toolbox & Ford Global 8D, premature termination, non-causal jumps),
    classifies terminal causes, and computes reversibility metrics.

    Parameters
    ----------
    data : Any
        Untrusted 5-Why dataset: FiveWhyChain, pd.DataFrame, list of dicts/FiveWhySteps, or dict.
    problem_statement : str, default "Problem Statement"
        The top-level problem or defect statement being analyzed.
    root_cause : str | None, optional
        Explicit terminal root cause. If None, inferred from the final step's explanation.
    leg_type : str | None, optional
        Optional 3-Legged 5-Why leg classification ('occurrence', 'escape', or 'systemic').

    Returns
    -------
    FiveWhyValidationResult
        Structured validation output containing verdict, reversibility score, link evaluations,
        anti-pattern findings, systemic root cause assessment, and recommendations.

    Raises
    ------
    TypeError
        If data is not a supported type (e.g. integer, None, float).
    pydantic.ValidationError
        If steps are non-consecutive, empty, blank, or violate field constraints.
    """
    chain = validate_five_why(data=data, problem_statement=problem_statement, root_cause=root_cause)

    effective_problem = chain.problem_statement
    effective_root_cause = chain.root_cause or (chain.steps[-1].because if chain.steps else "")
    total_steps = len(chain.steps)

    anti_patterns: list[AntiPatternFinding] = []
    link_evaluations: list[FiveWhyLinkEval] = []
    recommendations: list[str] = []

    # --------------------------------------------------------------------------
    # 1. Anti-Pattern Check: Circular Reasoning
    # --------------------------------------------------------------------------
    problem_tokens = _content_tokens(effective_problem)
    seen_step_tokens: list[tuple[int, set[str], str]] = []

    for step in chain.steps:
        because_tokens = _content_tokens(step.because)

        # Check circularity with problem statement
        if len(because_tokens) >= 2 and len(problem_tokens) >= 2:
            sim = _jaccard_similarity(because_tokens, problem_tokens)
            if sim >= 0.70 or step.because.strip().lower() == effective_problem.strip().lower():
                anti_patterns.append(
                    AntiPatternFinding(
                        code="CIRCULAR_REASONING",
                        severity="error",
                        step_number=step.step_number,
                        message=(
                            f"Step {step.step_number} circular reasoning: explanation '{step.because}' "
                            f"restates the problem statement '{effective_problem}'."
                        ),
                        recommendation="Reformulate the step to explain the underlying mechanism rather than restating the symptom.",
                    )
                )

        # Check circularity with previous steps
        for prev_num, prev_tokens, prev_text in seen_step_tokens:
            if len(because_tokens) >= 2 and len(prev_tokens) >= 2:
                sim = _jaccard_similarity(because_tokens, prev_tokens)
                if sim >= 0.70 or step.because.strip().lower() == prev_text.strip().lower():
                    anti_patterns.append(
                        AntiPatternFinding(
                            code="CIRCULAR_REASONING",
                            severity="error",
                            step_number=step.step_number,
                            message=(
                                f"Step {step.step_number} circular reasoning: explanation '{step.because}' "
                                f"repeats Step {prev_num} explanation '{prev_text}'."
                            ),
                            recommendation=f"Remove the circular loop between Step {prev_num} and Step {step.step_number}.",
                        )
                    )

        seen_step_tokens.append((step.step_number, because_tokens, step.because))

    # --------------------------------------------------------------------------
    # 2. Anti-Pattern Check: Blame-Terminal Operator Error & Premature Termination
    # --------------------------------------------------------------------------
    terminal_step = chain.steps[-1]
    terminal_explanation = chain.root_cause or terminal_step.because

    terminal_is_blame = _is_human_blame_statement(terminal_explanation)
    terminal_has_systemic = _has_systemic_resolution(terminal_explanation)

    if terminal_is_blame and not terminal_has_systemic:
        anti_patterns.append(
            AntiPatternFinding(
                code="BLAME_TERMINAL_OPERATOR_ERROR",
                severity="error",
                step_number=terminal_step.step_number,
                message=(
                    f"Terminal root cause '{terminal_explanation}' terminates at individual operator/human error "
                    "without systemic management, training, or poka-yoke resolution."
                ),
                recommendation=(
                    "Continue drilling down per ASQ Quality Toolbox & Ford Global 8D (RULE 4) to identify why the "
                    "system, training program, or error-proofing failed to prevent or detect the human error."
                ),
            )
        )

    # Check for premature termination
    if total_steps < 3 and not _has_systemic_resolution(terminal_explanation):
        anti_patterns.append(
            AntiPatternFinding(
                code="PREMATURE_TERMINATION",
                severity="warning",
                step_number=total_steps,
                message=(
                    f"Chain terminated at Step {total_steps} with non-systemic cause '{terminal_explanation}'. "
                    "5-Why typically requires 3 to 5 iterations to reach systemic root cause."
                ),
                recommendation="Continue asking 'Why' to drill down past immediate physical/technical causes to systemic policy, maintenance, or procedural safeguards.",
            )
        )

    # --------------------------------------------------------------------------
    # 3. Forward & Reverse Link Progression Evaluation (RULE 3)
    # --------------------------------------------------------------------------
    step_scores: list[float] = []

    for idx, step in enumerate(chain.steps):
        is_terminal = (idx == len(chain.steps) - 1)
        step_findings: list[str] = []
        link_score = 1.0

        # Construct reverse statement ("Because {because}, therefore {prior}")
        if idx == 0:
            prior_symptom = effective_problem if effective_problem != "Problem Statement" else step.why
            reverse_statement = f"Because {step.because.rstrip('.')}, therefore {prior_symptom.rstrip('.')}."
        else:
            prev_step = chain.steps[idx - 1]
            reverse_statement = f"Because {step.because.rstrip('.')}, therefore {prev_step.because.rstrip('.')}."

        # Check for circularity at this step
        has_step_circularity = any(
            p.code == "CIRCULAR_REASONING" and p.step_number == step.step_number
            for p in anti_patterns
        )
        if has_step_circularity:
            link_score = 0.0
            step_findings.append("Circular reasoning detected.")

        # Check for terminal operator blame at this step
        if is_terminal and terminal_is_blame and not terminal_has_systemic:
            link_score = 0.0
            step_findings.append("Terminal operator blame without systemic resolution.")

        # Check for non-causal jump between step i-1 and step i
        if idx > 0 and not has_step_circularity:
            prev_step = chain.steps[idx - 1]
            prev_because_tokens = _content_tokens(prev_step.because)
            curr_why_tokens = _content_tokens(step.why)
            curr_because_tokens = _content_tokens(step.because)

            # Linkage between current why/because and previous because
            overlap_why = len(prev_because_tokens & curr_why_tokens)
            overlap_because = len(prev_because_tokens & curr_because_tokens)
            pronouns = {"it", "this", "that", "these", "those", "he", "she", "they", "its"}
            has_pronoun_reference = bool(set(_tokenize(step.why.lower())) & pronouns)

            if overlap_why == 0 and overlap_because == 0 and not has_pronoun_reference:
                anti_patterns.append(
                    AntiPatternFinding(
                        code="NON_CAUSAL_JUMP",
                        severity="warning",
                        step_number=step.step_number,
                        message=(
                            f"Step {step.step_number} ('{step.why}') introduces disjoint concepts with no "
                            f"lexical or semantic connection to Step {prev_step.step_number} ('{prev_step.because}')."
                        ),
                        recommendation="Ensure each step directly questions the explanation in the preceding step without introducing disjoint topics.",
                    )
                )
                link_score = min(link_score, 0.3)
                step_findings.append("Non-causal jump: weak transition from previous step.")

        # Intermediate human error check (acceptable when followed by systemic resolution)
        step_is_blame = _is_human_blame_statement(step.because)
        if step_is_blame and not is_terminal:
            step_findings.append("Intermediate human factor identified; resolved systemically in subsequent steps.")

        is_reversible = (link_score >= 0.8)
        step_scores.append(link_score)

        notes_str = "; ".join(step_findings) if step_findings else None
        link_evaluations.append(
            FiveWhyLinkEval(
                step_number=step.step_number,
                why=step.why,
                because=step.because,
                reverse_statement=reverse_statement,
                is_reversible=is_reversible,
                reversibility_score=round(link_score, 4),
                notes=notes_str,
            )
        )

    # --------------------------------------------------------------------------
    # 4. Systemic Root Cause Assessment
    # --------------------------------------------------------------------------
    systemic_factors: list[str] = []
    for step in chain.steps:
        tokens = _tokenize(step.because)
        found_terms = [t for t in tokens if t in _SYSTEMIC_TERMS]
        systemic_factors.extend(found_terms)

    term_lower = terminal_explanation.lower()
    for phrase in ("induction plan", "training program", "error-proofing", "poka-yoke", "standard work", "engineering sign-off"):
        if phrase in term_lower:
            systemic_factors.append(phrase)

    systemic_factors = sorted(set(systemic_factors))

    if _has_systemic_resolution(terminal_explanation):
        classification: Literal["SYSTEMIC", "TECHNICAL_PROCESS", "HUMAN_INDIVIDUAL"] = "SYSTEMIC"
        is_systemic = True
    elif _is_human_blame_statement(terminal_explanation):
        classification = "HUMAN_INDIVIDUAL"
        is_systemic = False
    else:
        classification = "TECHNICAL_PROCESS"
        is_systemic = False

    systemic_recs: list[str] = []
    if classification == "SYSTEMIC":
        systemic_recs.append("Implement and verify permanent corrective action addressing the systemic policy/procedure.")
    elif classification == "HUMAN_INDIVIDUAL":
        systemic_recs.append("Drill down past individual error to identify management system, training, or poka-yoke root cause.")
    else:
        systemic_recs.append("Investigate process design, tooling maintenance, or operating parameters to establish systemic prevention.")

    systemic_assessment = SystemicAssessment(
        classification=classification,
        is_systemic=is_systemic,
        terminal_cause=terminal_explanation,
        systemic_factors=systemic_factors,
        recommendations=systemic_recs,
    )

    # --------------------------------------------------------------------------
    # 5. Reversibility Scoring & Verdict Determination
    # --------------------------------------------------------------------------
    reversibility_score = round(sum(step_scores) / total_steps, 4) if total_steps > 0 else 0.0

    has_hard_antipattern = any(
        p.code in ("CIRCULAR_REASONING", "BLAME_TERMINAL_OPERATOR_ERROR") for p in anti_patterns
    )

    if has_hard_antipattern or reversibility_score < 0.50:
        verdict: Literal["ACCEPT", "WARNING", "REJECT"] = "REJECT"
        valid = False
    elif reversibility_score >= 0.80 and not has_hard_antipattern:
        verdict = "ACCEPT"
        valid = True
    else:
        verdict = "WARNING"
        valid = True

    # --------------------------------------------------------------------------
    # 6. Overall Recommendation Synthesis
    # --------------------------------------------------------------------------
    recommendations = []
    seen: set[str] = set()
    for rec in [ap.recommendation for ap in anti_patterns] + systemic_recs:
        if rec and rec not in seen:
            seen.add(rec)
            recommendations.append(rec)

    if valid and is_systemic and "Causal chain is logically sound, reversible, and terminates at a systemic root cause." not in seen:
        recommendations.insert(0, "Causal chain is logically sound, reversible, and terminates at a systemic root cause.")

    return FiveWhyValidationResult(
        basis=_STANDARDS_BASIS,
        valid=valid,
        verdict=verdict,
        reversibility_score=reversibility_score,
        problem_statement=effective_problem,
        root_cause=effective_root_cause,
        total_steps=total_steps,
        link_evaluations=link_evaluations,
        anti_patterns=anti_patterns,
        systemic_assessment=systemic_assessment,
        recommendations=recommendations,
        leg_type=leg_type,
    )
