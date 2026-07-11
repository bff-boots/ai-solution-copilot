"""知识库的数据清洗、分块、向量化、检索与重排序。"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import chromadb
except ImportError:  # 演示环境可先使用本地检索，部署时再安装完整向量库。
    chromadb = None

try:
    import dashscope
except ImportError:
    dashscope = None
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_DIR = ROOT / "chroma_db"
COLLECTION_NAME = "ai_solution_knowledge"
EMBEDDING_MODEL = "text-embedding-v4"


@dataclass
class Chunk:
    text: str
    metadata: dict[str, str]


def clean_text(text: str) -> str:
    """统一空白与常见特殊字符，保留句末标点以支持语义分块。"""
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"[\t\r\f\v]+", " ", text)
    text = re.sub(r"[ \n]+", " ", text)
    return re.sub(r"\s+([，。！？；：、])", r"\1", text).strip()


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[。！？；!?])\s*", text) if part.strip()]


def semantic_chunks(text: str, *, chunk_size: int = 420, overlap: int = 42) -> list[str]:
    """按句号/问号等边界合并为 300-500 字左右的片段，并保留约 10% 重叠。"""
    sentences = _sentences(clean_text(text))
    if not sentences:
        return []
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > chunk_size:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = tail + sentence
        else:
            current += sentence
    if current:
        chunks.append(current)
    return chunks


def load_documents(data_dir: Path = DATA_DIR) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(list(data_dir.glob("*.md")) + list(data_dir.glob("*.txt"))):
        raw = path.read_text(encoding="utf-8")
        title_match = re.search(r"^#\s+(.+)$", raw, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.stem
        for index, text in enumerate(semantic_chunks(raw), start=1):
            chunks.append(Chunk(text, {"title": title, "source": path.name, "chunk_id": f"{path.stem}-{index:03d}"}))
    return chunks


def _embed(texts: list[str]) -> list[list[float]]:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key or dashscope is None:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY，无法调用 text-embedding-v4。")
    dashscope.api_key = api_key
    response = dashscope.TextEmbedding.call(model=EMBEDDING_MODEL, input=texts, dimension=1024)
    if response.status_code != 200:
        raise RuntimeError(f"嵌入接口调用失败：{response.code} {response.message}")
    return [item["embedding"] for item in response.output["embeddings"]]


def build_vector_store(reset: bool = False) -> int:
    load_dotenv(ROOT / ".env")
    if chromadb is None:
        raise RuntimeError("未安装 chromadb；当前仍可使用本地关键词检索演示。")
    if reset and DB_DIR.exists():
        shutil.rmtree(DB_DIR)
    chunks = load_documents()
    if not chunks:
        raise RuntimeError("data 目录中没有 .md 或 .txt 知识文档。")
    client = chromadb.PersistentClient(path=str(DB_DIR))
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
    collection = client.get_or_create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    embeddings = _embed([chunk.text for chunk in chunks])
    collection.upsert(
        ids=[chunk.metadata["chunk_id"] for chunk in chunks],
        documents=[chunk.text for chunk in chunks],
        metadatas=[chunk.metadata for chunk in chunks],
        embeddings=embeddings,
    )
    return len(chunks)


def _keyword_score(query: str, text: str) -> int:
    terms = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]+", query.lower()))
    lowered = text.lower()
    return sum(lowered.count(term) for term in terms)


def _domain_score(query: str, text: str) -> int:
    """为中文业务词补充可解释的轻量匹配，保证无模型演示也能按场景返回资料。"""
    keywords = ["机器人", "售后", "工单", "传感器", "设备", "算力", "数据中心", "光模块", "互连", "云", "知识库", "检索", "RAG", "销售", "客户", "预算"]
    return sum(3 for word in keywords if word in query and word in text)


def _local_search(query: str, limit: int) -> list[dict]:
    candidates = load_documents()
    ranked = sorted(candidates, key=lambda item: _keyword_score(query, item.text) + _domain_score(query, item.text), reverse=True)
    return [{"content": item.text, "metadata": item.metadata, "score": float(_keyword_score(query, item.text) + _domain_score(query, item.text))} for item in ranked[:limit]]


def retrieve_and_rerank(query: str, *, candidates: int = 12, limit: int = 4) -> list[dict]:
    """先做向量检索，再用轻量词项相关度重排；无密钥时降级为本地检索。"""
    load_dotenv(ROOT / ".env")
    if chromadb is None or dashscope is None or not os.getenv("DASHSCOPE_API_KEY") or not DB_DIR.exists():
        return _local_search(query, limit)
    client = chromadb.PersistentClient(path=str(DB_DIR))
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        return _local_search(query, limit)
    count = collection.count()
    if count == 0:
        return _local_search(query, limit)
    # Chroma 不允许请求数量超过集合中的实际记录数。
    result = collection.query(
        query_embeddings=_embed([query]),
        n_results=min(candidates, count),
        include=["documents", "metadatas", "distances"],
    )
    hits = [
        {"content": document, "metadata": metadata, "score": 1 - float(distance)}
        for document, metadata, distance in zip(result["documents"][0], result["metadatas"][0], result["distances"][0])
    ]
    for hit in hits:
        hit["rerank_score"] = hit["score"] + 0.08 * _keyword_score(query, hit["content"])
    return sorted(hits, key=lambda item: item["rerank_score"], reverse=True)[:limit]
