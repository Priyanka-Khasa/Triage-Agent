import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class RetrievalAgent:
    """RetrievalAgent uses local corpus embeddings to return relevant support text chunks."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.chunks = []
        self.vectorizer = TfidfVectorizer(stop_words='english', lowercase=True)
        self.tfidf_matrix = None

    def _chunk_text(self, text: str, filepath: str):
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        max_chunk_size = 1000

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            if len(current_chunk) + len(paragraph) > max_chunk_size:
                if current_chunk:
                    chunks.append({
                        "text": current_chunk.strip(),
                        "filepath": filepath,
                        "company": self._infer_company(filepath)
                    })
                current_chunk = paragraph
            else:
                current_chunk = f"{current_chunk}\n\n{paragraph}" if current_chunk else paragraph

        if current_chunk.strip():
            chunks.append({
                "text": current_chunk.strip(),
                "filepath": filepath,
                "company": self._infer_company(filepath)
            })

        return chunks

    def _infer_company(self, filepath: str) -> str:
        # Use relative path to avoid matching parent directories
        rel_path = os.path.relpath(filepath, self.data_dir).lower()
        if 'hackerrank' in rel_path:
            return 'HackerRank'
        if 'claude' in rel_path:
            return 'Claude'
        if 'visa' in rel_path:
            return 'Visa'
        return 'None'

    def build_index(self):
        for root, _, files in os.walk(self.data_dir):
            for file in files:
                if file.endswith('.md'):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            text = f.read()
                            self.chunks.extend(self._chunk_text(text, filepath))
                    except Exception as e:
                        print(f"Error reading {filepath}: {e}")

        if not self.chunks:
            raise ValueError("No markdown files found in the data directory.")

        corpus = [chunk['text'] for chunk in self.chunks]
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def retrieve(self, query: str, top_k: int = 5, threshold: float = 0.15):
        if self.tfidf_matrix is None:
            raise RuntimeError("Index not built. Call build_index() first.")

        if not query or not query.strip():
            return {
                "results": [],
                "retrieval_confidence": 0.0,
                "escalate": True
            }

        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        top_indices = similarities.argsort()[-top_k:][::-1]

        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            results.append({
                "text": self.chunks[idx]["text"],
                "filepath": self.chunks[idx]["filepath"],
                "company": self.chunks[idx]["company"],
                "score": score
            })

        retrieval_confidence = float(max(similarities)) if len(similarities) > 0 else 0.0
        should_escalate = retrieval_confidence < threshold

        return {
            "results": results,
            "retrieval_confidence": retrieval_confidence,
            "escalate": should_escalate
        }
