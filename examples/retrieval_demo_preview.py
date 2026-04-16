"""Preview BM25 workspace retrieval against the bookstore example.

Run this from the repo root after `pip install -e .`:

    python examples/retrieval_demo_preview.py
    python examples/retrieval_demo_preview.py --top-k 5
    python examples/retrieval_demo_preview.py --query "add two-factor enrollment endpoint"

The script iterates over a set of representative task queries, runs the BM25
retriever against ``examples/retrieval_demo/`` and prints the ranking. Each
query ships with a list of files we *expect* to rank highly - the script
reports precision-at-k so you can see how parameter or tokenization changes
affect retrieval quality.
"""

import argparse
from pathlib import Path

from rank_bm25 import BM25Okapi

from devteam.utils.retriever import _tokenize, _read_documents


WORKSPACE = Path(__file__).parent / 'bookstore_flask'


# Each entry is (query, set of file paths that SHOULD appear in the top-k).
# Expected files are hand-picked by a human - adjust them if you change the
# example workspace.
QUERIES: list[tuple[str, set[str]]] = [
    (
        'Add rate limiting to login and two-factor verification endpoints to prevent brute-force attacks',
        {
            'src/auth/login.py',
            'src/auth/two_factor.py',
            'src/api/auth_routes.py',
            'src/auth/session.py',
            'tests/test_auth.py',
        },
    ),
    (
        'Show personalised book recommendations on the homepage for returning customers',
        {
            'src/services/recommendations.py',
            'src/api/recommendation_routes.py',
            'src/models/book.py',
            'src/models/order.py',
            'tests/test_recommendations.py',
        },
    ),
    (
        'Send an order confirmation email after a successful Stripe charge',
        {
            'src/services/email.py',
            'src/services/payment.py',
            'src/api/order_routes.py',
            'src/models/order.py',
        },
    ),
    (
        'Validate ISBN format before accepting a new book into the catalog',
        {
            'src/utils/validators.py',
            'src/models/book.py',
            'src/api/book_routes.py',
        },
    ),
    (
        'Enable TOTP two-factor enrollment from the user profile page',
        {
            'src/auth/two_factor.py',
            'src/models/user.py',
            'src/api/auth_routes.py',
            'src/auth/session.py',
        },
    ),
]


def rank(documents: list[tuple[str, str]], query: str) -> list[tuple[str, float]]:
    """Return (path, score) pairs sorted by BM25 relevance to the query."""
    corpus = [_tokenize(f"{path} {content}") for path, content in documents]
    tokens = _tokenize(query)
    if not tokens:
        return [(path, 0.0) for path, _ in documents]
    scores = BM25Okapi(corpus).get_scores(tokens)
    return sorted(
        ((documents[i][0], float(scores[i])) for i in range(len(documents))),
        key=lambda pair: pair[1],
        reverse=True,
    )


def precision_at_k(ranked: list[tuple[str, float]], expected: set[str], k: int) -> float:
    """Fraction of the top-k ranked files that appear in the expected set."""
    if not expected:
        return 0.0
    top_paths = {path for path, _ in ranked[:k]}
    return len(top_paths & expected) / min(k, len(expected))


def print_ranking(query: str, expected: set[str], documents: list[tuple[str, str]], top_k: int) -> None:
    ranked = rank(documents, query)
    print(f"\n=== QUERY: {query}")
    print(f"    expected top files ({len(expected)}): {sorted(expected)}")
    print(f"    precision@{top_k}: {precision_at_k(ranked, expected, top_k):.2f}")
    print(f"    top-{top_k} ranking:")
    for position, (path, score) in enumerate(ranked[:top_k], start=1):
        marker = '*' if path in expected else ' '
        print(f"      {position:>2}. {marker} {path}  (score={score:.3f})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--top-k', type=int, default=10, help='Number of files to treat as the retrieved set')
    parser.add_argument('--query', type=str, default=None, help='Run a single custom query instead of the built-in set')
    args = parser.parse_args()

    documents = _read_documents(str(WORKSPACE))
    print(f"Loaded {len(documents)} files from {WORKSPACE}")

    if args.query:
        print_ranking(args.query, set(), documents, args.top_k)
        return

    for query, expected in QUERIES:
        print_ranking(query, expected, documents, args.top_k)


if __name__ == '__main__':
    main()
