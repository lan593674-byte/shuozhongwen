#!/usr/bin/env python3
"""Chinese stylometry gauge for shuozhongwen (stdlib only, no network).

Measures the statistical signals Chinese AI-text detectors lean on, then combines
them with weights calibrated on a public-domain human corpus vs. AI samples
(see calibration/). It is a gauge, not an authorship verdict.

Signals:
- sentence-length variation (CV over 。！？… sentences, in Han characters)
- paragraph-length variation
- clauses per sentence (comma chains)
- connector density and connector-led paragraphs (首先/此外/总之 ...)
- adjacent sentences opening the same way
- format templating (headings, list items, bold lead-ins)
- character-bigram diversity (MATTR)
- AI-flavour phrase density, with the phrase list read from the skill's symptom dictionary

Exit code 1 when the score is at or above the threshold.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    classify_finding_confidence,
    emit_json,
    read_text_input,
)
from haohao_markers import load_markers  # noqa: E402

MODEL_PATH = Path(__file__).resolve().parent / "zh_model.json"
MIN_HAN = 150  # below this the statistics are noise
DEFAULT_THRESHOLD = 0.65

HAN_RE = re.compile(r"[一-鿿]")
CLAUSE_RE = re.compile(r"[，,；;：:、]")
FENCE_RE = re.compile(r"```.*?```", re.S)
# 【...】 panels (game/system prompts in web novels, UI text) are not the
# author's prose; they are dropped before measuring.
PANEL_RE = re.compile(r"【[^】\n]{0,200}】")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
URL_RE = re.compile(r"https?://\S+")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")
LIST_RE = re.compile(r"^\s*(?:[-*+•]|\d+[.、)）]|[一二三四五六七八九十]+、|（[一二三四五六七八九十\d]+）)\s*")
BOLD_LEAD_RE = re.compile(r"^\s*\*\*[^*]{1,30}\*\*")
CONNECTORS = (
    "首先", "其次", "再次", "最后", "此外", "另外", "同时", "因此", "所以", "然而",
    "但是", "不过", "总之", "总而言之", "综上所述", "综上", "一方面", "另一方面",
    "更为重要的是", "更重要的是", "值得注意的是", "与此同时", "换言之", "由此可见",
    "当然", "那么",
)
CONNECTOR_RE = re.compile("|".join(sorted(map(re.escape, CONNECTORS), key=len, reverse=True)))

FEATURES = (
    "sent_cv", "para_cv", "clauses_per_sent", "connector_per_k", "connector_para_lead",
    "start_repeat", "format_ratio", "bigram_mattr", "marker_per_k",
    "we_per_k", "de_per_k", "colon_per_k", "closer",
    "i_per_k", "quote_per_k", "ellipsis_per_k", "exclaim_per_k", "question_per_k", "dash_per_k",
)
CLOSERS = ("总之", "总而言之", "综上", "让我们", "希望", "愿", "未来")


@dataclass
class MarkerMatch:
    phrase: str
    count: int
    weight: float
    samples: list[str] = field(default_factory=list)
    spans: list[tuple[int, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"phrase": self.phrase, "count": self.count, "weight": self.weight,
                "samples": self.samples, "spans": self.spans}


@dataclass
class StylometryReport:
    path: str
    word_count: int  # Han characters (+ Latin words) — kept under the upstream field name
    sentence_count: int
    burstiness_cv: float | None
    lexical_diversity: float
    ai_ngram_density: float  # marker hits per 1000 Han characters
    matched_markers: list[dict[str, Any]]
    score: float | None
    confidence_level: str | None
    density_tier: str
    status: str
    features: dict[str, float | None] = field(default_factory=dict)
    contributions: dict[str, float] = field(default_factory=dict)
    human_percentile: int | None = None  # share (%) of held-out human chunks scoring lower
    findings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        r = lambda v: round(v, 4) if isinstance(v, float) else v  # noqa: E731
        return {
            "path": self.path,
            "language": "zh",
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "burstiness_cv": r(self.burstiness_cv),
            "lexical_diversity": r(self.lexical_diversity),
            "ai_ngram_density": r(self.ai_ngram_density),
            "matched_markers": self.matched_markers,
            "score": r(self.score),
            "confidence_level": self.confidence_level,
            "density_tier": self.density_tier,
            "status": self.status,
            "features": {k: r(v) for k, v in self.features.items()},
            "human_percentile": self.human_percentile,
            "contributions": {k: round(v, 3) for k, v in sorted(self.contributions.items(), key=lambda kv: -kv[1]) if v > 0.05},
            "findings": self.findings,
            "findings_confidence": [classify_finding_confidence(f) for f in self.findings],
            "notes": self.notes,
        }


def strip_code(text: str) -> str:
    text = FENCE_RE.sub("\n", text)
    text = PANEL_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    return URL_RE.sub("", text)


def han_len(s: str) -> int:
    return len(HAN_RE.findall(s)) + len(re.findall(r"[A-Za-z]+", s))


def split_paragraphs(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def split_sentences(paragraphs: list[str]) -> list[str]:
    out = []
    for p in paragraphs:
        if HEADING_RE.match(p):
            continue
        body = LIST_RE.sub("", p)
        # a sentence runs up to its ender plus any closing quotes/brackets
        parts = re.findall(r"[^。！？!?…]+[。！？!?…]*[”’」』）)]*", body)
        out.extend(s.strip() for s in parts if han_len(s) >= 2)
    return out


def cv(values: list[int]) -> float | None:
    if len(values) < 2:
        return None
    mean = statistics.fmean(values)
    return statistics.pstdev(values) / mean if mean else None


def compute_burstiness(sentences: list[str]) -> tuple[float, float, float | None]:
    lens = [han_len(s) for s in sentences]
    if not lens:
        return 0.0, 0.0, None
    return statistics.fmean(lens), (statistics.pstdev(lens) if len(lens) > 1 else 0.0), cv(lens)


def bigram_mattr(text: str, window: int = 200) -> float:
    chars = HAN_RE.findall(text)
    grams = [a + b for a, b in zip(chars, chars[1:])]
    if not grams:
        return 0.0
    if len(grams) <= window:
        return len(set(grams)) / len(grams)
    step = max(1, window // 4)
    vals = [len(set(grams[i:i + window])) / window for i in range(0, len(grams) - window + 1, step)]
    return statistics.fmean(vals)


def scan_markers(text: str, exclude: set[str]) -> tuple[list[MarkerMatch], str | None]:
    patterns, note = load_markers()
    found = []
    for pattern, label in patterns:
        if label in exclude:
            continue
        hits = list(re.finditer(pattern, text))
        if hits:
            found.append(MarkerMatch(label, len(hits), 1.0, [h.group(0) for h in hits[:3]],
                                     [(h.start(), h.end()) for h in hits[:10]]))
    return found, note


QUOTE_MAP = str.maketrans({"「": "“", "」": "”", "『": "‘", "』": "’"})


def extract_features(text: str, exclude: set[str] | None = None) -> tuple[dict[str, float | None], dict[str, Any]]:
    body = strip_code(text).translate(QUOTE_MAP)
    paras = split_paragraphs(body)
    sents = split_sentences(paras)
    n = sum(han_len(p) for p in paras)
    prose = [p for p in paras if not (HEADING_RE.match(p) or LIST_RE.match(p) or BOLD_LEAD_RE.match(p))]
    fmt = len(paras) - len(prose)
    starts = [re.sub(r"[^一-鿿]", "", s)[:2] for s in sents]
    rep = sum(1 for a, b in zip(starts, starts[1:]) if a and a == b)
    conn = len(CONNECTOR_RE.findall(body))
    lead = sum(1 for p in prose if CONNECTOR_RE.match(re.sub(r"^[\W_]+", "", p)))
    markers, note = scan_markers(body, exclude or set())
    k = n / 1000 if n else 1
    f = {
        "sent_cv": cv([han_len(s) for s in sents]),
        "para_cv": cv([han_len(p) for p in prose]),
        "clauses_per_sent": (statistics.fmean(len(CLAUSE_RE.findall(s)) + 1 for s in sents) if sents else None),
        "connector_per_k": conn / k,
        "connector_para_lead": lead / len(prose) if prose else 0.0,
        "start_repeat": rep / (len(sents) - 1) if len(sents) > 1 else 0.0,
        "format_ratio": fmt / len(paras) if paras else 0.0,
        "bigram_mattr": bigram_mattr(body),
        "marker_per_k": sum(m.count for m in markers) / k,
        "we_per_k": body.count("我们") / k,
        "de_per_k": body.count("的") / k,
        "colon_per_k": (body.count("：") + body.count(":")) / k,
        "i_per_k": (body.count("我") - body.count("我们")) / k,
        "quote_per_k": body.count("“") / k,
        "ellipsis_per_k": (body.count("……") + body.count("...")) / k,
        "exclaim_per_k": (body.count("！") + body.count("!")) / k,
        "question_per_k": (body.count("？") + body.count("?")) / k,
        "dash_per_k": body.count("——") / k,
        "closer": float(bool(prose) and any(re.sub(r"^[\W_]+", "", prose[-1]).startswith(c) for c in CLOSERS)),
    }
    meta = {"han": n, "sentences": len(sents), "markers": markers, "marker_note": note}
    return f, meta


def load_model() -> dict[str, Any] | None:
    try:
        return json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def contributions(features: dict[str, float | None], model: dict[str, Any]) -> dict[str, float]:
    """How far each feature pushes the log-odds toward AI (+) or human (-)."""
    out = {}
    for name in FEATURES:
        v = features.get(name)
        mean, sd = model["mean"][name], model["sd"][name]
        v = mean if v is None else v
        out[name] = model["weights"][name] * ((v - mean) / sd if sd else 0.0)
    return out


def combine(features: dict[str, float | None], model: dict[str, Any]) -> float:
    z = model["bias"] + sum(contributions(features, model).values())
    return 1 / (1 + math.exp(-z))


def classify(score: float, model: dict[str, Any]) -> tuple[str, str]:
    lo, hi = model["tiers"]["medium"], model["tiers"]["high"]
    if score >= hi:
        return "high", "HIGH"
    if score >= lo:
        return "medium", "MEDIUM"
    return "low", "LOW"


FINDING_TEXT = {
    "sent_cv": ("low", "句长过于均匀（sent_cv={:.2f}）"),
    "para_cv": ("low", "段落长度过于均匀（para_cv={:.2f}）"),
    "format_ratio": ("high", "标题/列表/加粗占比偏高（{:.0%}）"),
    "marker_per_k": ("high", "AI 味词句密度偏高（每千字 {:.1f} 处）"),
    "we_per_k": ("high", "“我们”用得偏多（每千字 {:.1f} 个）"),
    "colon_per_k": ("high", "冒号偏多（每千字 {:.1f} 个）"),
    "closer": ("high", "结尾用总结或号召收束"),
    "exclaim_per_k": ("low", "几乎没有感叹、疑问、省略这类语气标点"),
    "bigram_mattr": ("high", "辞藻堆得太满：四字套语、同义换说、华丽形容词多（删套话，换成只属于这篇的具体细节；别靠重复用词压分）"),
    "connector_per_k": ("low", "句间几乎不用“因为、可是、所以”衔接，短句并排堆着（每千字 {:.1f} 个）"),
}


def score_text_stylometry(text: str, path: str = "<text>") -> StylometryReport:
    model = load_model()
    exclude = set(model.get("marker_exclude", [])) if model else set()
    feats, meta = extract_features(text, exclude)
    notes = ["Gauge only: calibrated Chinese stylometry, not an authorship verdict."]
    if meta["marker_note"]:
        notes.append(meta["marker_note"])
    markers = [m.to_dict() for m in meta["markers"]]
    base = dict(path=path, word_count=meta["han"], sentence_count=meta["sentences"],
                burstiness_cv=feats["sent_cv"], lexical_diversity=feats["bigram_mattr"],
                ai_ngram_density=feats["marker_per_k"], matched_markers=markers, features=feats)
    if feats["sent_cv"] is None:
        notes.append("burstiness unavailable: fewer than 2 sentences outside code")
    if meta["han"] < MIN_HAN:
        notes.append(f"Sample has {meta['han']} Han characters; below {MIN_HAN} the gauge is not calibrated, so no score")
        return StylometryReport(score=None, confidence_level=None, density_tier="uncalibrated",
                                status="insufficient_length", notes=notes, **base)
    if model is None:
        notes.append(f"No calibration model at {MODEL_PATH.name}; features reported without a score")
        return StylometryReport(score=None, confidence_level=None, density_tier="uncalibrated",
                                status="uncalibrated", notes=notes, **base)
    score = combine(feats, model)
    tier, level = classify(score, model)
    findings = []
    for name, (direction, fmt) in FINDING_TEXT.items():
        v = feats.get(name)
        ref = model["human_p90"].get(name) if direction == "high" else model["human_p10"].get(name)
        if v is None or ref is None:
            continue
        if (direction == "high" and v > ref) or (direction == "low" and v < ref):
            findings.append(fmt.format(v))
    base["contributions"] = contributions(feats, model)
    qs = model.get("human_score_quantiles")
    if qs:
        base["human_percentile"] = sum(1 for q in qs if q < score) - 1 if score > qs[0] else 0
    return StylometryReport(score=score, confidence_level=level, density_tier=tier,
                            status="ok", findings=findings, notes=notes, **base)


def print_human_stylometry_report(report: StylometryReport, explain: bool = False) -> None:
    print(f"=== 中文文体评分：{report.path} ===")
    print("仅作参考：统计文本特征，不判定作者身份。")
    print(f"状态：        {report.status}")
    print(f"评分：        {report.score:.3f}" if report.score is not None else "评分：        无（样本过短或未校准）")
    print(f"档位：        {report.density_tier}")
    print(f"汉字数：      {report.word_count}")
    print(f"句子数：      {report.sentence_count}")
    for k, v in report.features.items():
        print(f"  {k:<20}{'n/a' if v is None else f'{v:.3f}'}")
    if report.findings:
        print("\n发现：")
        for f in report.findings:
            print(f"  - {f}")
    if explain and report.matched_markers:
        print("\n命中的 AI 味词句（词表来自症状库）：")
        for m in report.matched_markers:
            print(f"  * {m['phrase']} ×{m['count']}  例：{m['samples'][0] if m['samples'] else ''}")
    for n in report.notes:
        print(f"* {n}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path", nargs="?", default="-", help="Text file to score ('-' for stdin)")
    p.add_argument("--threshold", type=float, default=None,
                   help="Score threshold for exit code 1 (default: the calibrated 'high' tier)")
    p.add_argument("--json", action="store_true", help="Emit JSON output")
    p.add_argument("--explain", action="store_true", help="List matched phrases")
    args = p.parse_args()
    text = read_text_input(args.path)
    report = score_text_stylometry(text, path="<stdin>" if args.path == "-" else args.path)
    if args.json:
        emit_json(report.to_dict())
    else:
        print_human_stylometry_report(report, explain=args.explain)
    model = load_model()
    threshold = args.threshold if args.threshold is not None else (
        model["tiers"]["high"] if model else DEFAULT_THRESHOLD)
    return 1 if report.score is not None and report.score >= threshold else 0


if __name__ == "__main__":
    sys.exit(main())
