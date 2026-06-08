# Safety Knowledge Corpus

本目录存放 RAG 制度/规范 Markdown 分块语料（Phase 3-C）。

- 运行时由 `backend/scripts/seed_rag_corpus.py` 读取并写入 Milvus `safety_knowledge` collection；
- 默认租户 `CSCEC`；
- 禁止写入身份证、体检明细、人脸原图等敏感信息。
