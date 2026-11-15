"""Fixed product wording shared across the RAG pipeline."""

# Exact refusal sentence (product requirement). Every refusal is logged as an unanswered question.
REFUSAL_TEXT = (
    "I couldn't find sufficient information in your uploaded documents to answer this question "
    "reliably."
)
