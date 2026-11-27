"""Local, versioned policy retrieval. Example policies are never labelled approved."""
import json
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def retrieve_policy(query, top_k=2):
    rows = json.loads((Path(__file__).resolve().parents[1] / "policies" / "support.json").read_text())
    if not rows:
        return []
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform([r["text"] for r in rows])
    scores = cosine_similarity(vectorizer.transform([query]), matrix).ravel()
    return [dict(rows[i], similarity=round(float(scores[i]), 3)) for i in scores.argsort()[::-1][:top_k] if scores[i] > 0]
