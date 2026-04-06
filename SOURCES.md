# Course Material Sources

All textbooks used in this project are sourced from [OpenStax](https://openstax.org) and are freely available
under the **Creative Commons Attribution 4.0 International License (CC BY 4.0)**.

© 1999–2026 Rice University. Textbook content produced by OpenStax is licensed under a
[Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/).

*Advanced Placement® and AP® are trademarks registered and/or owned by the College Board,
which is not affiliated with, and does not endorse, this site.*

---

## Textbooks

| # | Title | Authors | URL | License |
|---|-------|---------|-----|---------|
| 1 | Introduction to Computer Science | OpenStax | [add URL from your browser] | CC BY 4.0 |
| 2 | Introductory Statistics, 2nd Edition | OpenStax | [add URL from your browser] | CC BY 4.0 |
| 3 | Principles of Data Science | OpenStax | [add URL from your browser] | CC BY 4.0 |
| 4 | Python Programming | OpenStax | [add URL from your browser] | CC BY 4.0 |

---

## How These Materials Are Used

The PDF files are loaded via LangChain's `PyPDFLoader`, split into 800-character chunks
with 100-character overlap using `RecursiveCharacterTextSplitter`, embedded with
OpenAI `text-embedding-3-small`, and stored in a persistent ChromaDB vector database.
They are used exclusively for Retrieval-Augmented Generation (RAG) to provide
contextually accurate answers to student queries.

No modifications were made to the original text content.
