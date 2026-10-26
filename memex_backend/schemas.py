from pydantic import BaseModel, Field


class DocumentIn(BaseModel):
    path: str = Field(min_length=1)
    content: str
    hash: str = Field(min_length=1)


class DocumentResult(BaseModel):
    status: str
    chunks: int | None = None


class SearchIn(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=100)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class SearchResult(BaseModel):
    score: float
    path: str
    heading: str | None
    chunk_index: int
    text: str


class SearchOut(BaseModel):
    results: list[SearchResult]


class Source(BaseModel):
    path: str
    chunks: int


class SourcesOut(BaseModel):
    sources: list[Source]


class StatusOut(BaseModel):
    model: str
    vector_dimension: int
    collection: str
    document_count: int
    chunk_count: int

