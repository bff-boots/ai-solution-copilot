"""构建校园知识库的命令行入口。"""
import argparse

from app.knowledge import build_vector_store


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="清洗文档并使用 text-embedding-v4 写入 ChromaDB")
    parser.add_argument("--reset", action="store_true", help="删除旧向量库后重新构建")
    args = parser.parse_args()
    count = build_vector_store(reset=args.reset)
    print(f"建库完成：已写入 {count} 个知识块。")

