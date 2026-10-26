from functools import cached_property


class Embedder:
    def __init__(self, model_name: str, device: str = "auto") -> None:
        self.model_name = model_name
        self.device = device

    @cached_property
    def model(self):
        from sentence_transformers import SentenceTransformer

        kwargs = {} if self.device == "auto" else {"device": self.device}
        return SentenceTransformer(self.model_name, **kwargs)

    @property
    def dimension(self) -> int:
        return int(self.model.get_sentence_embedding_dimension())

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return vectors.tolist()

    def embed_query(self, query: str) -> list[float]:
        model = self.model
        if hasattr(model, "encode_query"):
            vector = model.encode_query(query, normalize_embeddings=True, convert_to_numpy=True)
        else:
            vector = model.encode(
                query,
                prompt="Instruct: Retrieve relevant notes for this query\nQuery: ",
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        return vector.tolist()
