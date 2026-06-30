import json
import logging
import re
import uuid
from typing import Dict, List, Optional, Set, Tuple

import yaml
from langchain_text_splitters import (
    Language,
    RecursiveCharacterTextSplitter,
)

from app.rag_components.config import ChunkingConfig
from app.rag_components.models import (
    ChunkMetadata,
    ChunkType,
    ContentType,
    DocumentChunk,
    RawDocument,
)

logger = logging.getLogger(__name__)


CODE_LANG_MAP: Dict[str, Language] = {
    "python": Language.PYTHON,
    "javascript": Language.JS,
    "typescript": Language.TS,
    "go": Language.GO,
    "rust": Language.RUST,
    "java": Language.JAVA,
}

EXT_TO_LANG: Dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".sh": "bash",
    ".bash": "bash",
    ".dockerfile": "dockerfile",
    ".tf": "terraform",
    ".tfvars": "terraform",
    ".hcl": "terraform",
}


class StructureAwareChunker:
    def __init__(self, config: Optional[ChunkingConfig] = None):
        self.config = config or ChunkingConfig()
        self._init_splitters()

    def _init_splitters(self):
        cfg = self.config.by_type.code
        self.code_splitters: Dict[str, RecursiveCharacterTextSplitter] = {}

        for lang_str in cfg.languages:
            lang = CODE_LANG_MAP.get(lang_str)
            if lang is not None:
                self.code_splitters[lang_str] = RecursiveCharacterTextSplitter.from_language(
                    language=lang,
                    chunk_size=cfg.chunk_size,
                    chunk_overlap=cfg.chunk_overlap,
                )
            else:
                self.code_splitters[lang_str] = RecursiveCharacterTextSplitter(
                    chunk_size=cfg.chunk_size,
                    chunk_overlap=cfg.chunk_overlap,
                    separators=[
                        "\n\n",
                        "\n",
                        ";",
                        ".",
                        " ",
                        "",
                    ],
                )

        self.yaml_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.default.chunk_size,
            chunk_overlap=self.config.default.chunk_overlap,
            separators=["\n---\n", "\n\n", "\n", " ", ""],
        )

        self.generic_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.default.chunk_size,
            chunk_overlap=self.config.default.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        logger.debug(
            "Initialized splitters: %d languages, default_size=%d, overlap=%d",
            len(self.code_splitters), self.config.default.chunk_size, self.config.default.chunk_overlap,
        )

    def chunk(self, doc: RawDocument, metadata: ChunkMetadata) -> List[DocumentChunk]:
        content_type = self._detect_content_type(doc)
        content = doc.content.strip()

        if not content:
            logger.warning("Empty content for: %s", doc.file_name)
            return []

        if content_type == ContentType.CODE:
            chunks = self._chunk_code(content, doc, metadata)
        elif content_type == ContentType.YAML:
            chunks = self._chunk_yaml(content, doc, metadata)
        elif content_type == ContentType.JSON:
            chunks = self._chunk_json(content, doc, metadata)
        elif content_type == ContentType.LOGS:
            chunks = self._chunk_logs(content, doc, metadata)
        elif content_type == ContentType.MARKDOWN_CODE:
            chunks = self._chunk_markdown(content, doc, metadata)
        else:
            chunks = self._chunk_generic(content, doc, metadata)

        logger.info(
            "Chunked %s — content_type=%s, chunks=%d",
            doc.file_name, content_type.value, len(chunks),
        )
        return chunks

    def chunk_batch(
        self, docs: List[RawDocument], metadatas: List[ChunkMetadata]
    ) -> List[List[DocumentChunk]]:
        return [self.chunk(d, m) for d, m in zip(docs, metadatas)]

    def _detect_content_type(self, doc: RawDocument) -> ContentType:
        ext = doc.file_extension.lower()
        name = doc.file_name

        if ext in (".yaml", ".yml"):
            return ContentType.YAML
        if ext == ".json":
            return ContentType.JSON
        if ext == ".log":
            return ContentType.LOGS
        if ext in (".md", ".markdown"):
            if self._has_code_fences(doc.content):
                return ContentType.MARKDOWN_CODE
            return ContentType.GENERIC
        if ext in EXT_TO_LANG:
            return ContentType.CODE
        if name == "Dockerfile":
            return ContentType.CODE

        return ContentType.GENERIC

    def _has_code_fences(self, content: str) -> bool:
        return bool(re.search(r"```", content))

    def _make_chunk_id(
        self, doc: RawDocument, chunk_type: ChunkType, symbol: Optional[str] = None
    ) -> str:
        base = doc.file_path.replace("://", "_").replace("/", "_").replace("\\", "_")
        if symbol:
            return f"{base}::{chunk_type.value}_{symbol}"
        return f"{base}::{chunk_type.value}_{uuid.uuid4().hex[:8]}"

    def _build_chunks(
        self,
        texts: List[str],
        chunk_type: ChunkType,
        doc: RawDocument,
        base_metadata: ChunkMetadata,
        symbols: Optional[List[Optional[str]]] = None,
        language: Optional[str] = None,
    ) -> List[DocumentChunk]:
        if symbols is None:
            symbols = [None] * len(texts)

        result: List[DocumentChunk] = []
        for i, (text, symbol) in enumerate(zip(texts, symbols)):
            meta = base_metadata.model_copy(deep=True)
            meta.chunk_type = chunk_type.value
            meta.chunk_symbol = symbol
            meta.chunk_language = language or meta.chunk_language
            meta.chunk_index = i
            meta.total_chunks = len(texts)

            chunk_id = self._make_chunk_id(doc, chunk_type, symbol)
            result.append(DocumentChunk(id=chunk_id, content=text, metadata=meta))

        return result

    # --- Code chunking ---

    def _get_code_language(self, doc: RawDocument) -> Optional[str]:
        if doc.file_name == "Dockerfile":
            return "dockerfile"
        return EXT_TO_LANG.get(doc.file_extension.lower())

    def _chunk_code(
        self, content: str, doc: RawDocument, metadata: ChunkMetadata
    ) -> List[DocumentChunk]:
        lang_str = self._get_code_language(doc)
        splitter = self.code_splitters.get(lang_str, self.generic_splitter)
        texts = splitter.split_text(content)

        symbols = []
        for t in texts:
            sym = self._extract_code_symbol(t, lang_str)
            symbols.append(sym)

        logger.debug("Code chunked: lang=%s, chunks=%d", lang_str, len(texts))
        return self._build_chunks(
            texts=texts,
            chunk_type=ChunkType.FUNCTION,
            doc=doc,
            base_metadata=metadata,
            symbols=symbols,
            language=lang_str,
        )

    def _extract_code_symbol(self, text: str, language: Optional[str]) -> Optional[str]:
        if not language:
            return None

        patterns = {
            "python": [r"^(?:async\s+)?def\s+(\w+)", r"^class\s+(\w+)"],
            "bash": [r"^function\s+(\w+)", r"^(\w+)\s*\(\)"],
            "dockerfile": [r"^FROM\s+(\S+)"],
            "javascript": [
                r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)",
                r"^(?:export\s+)?class\s+(\w+)",
                r"^(?:export\s+)?const\s+(\w+)\s*=",
            ],
            "typescript": [
                r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)",
                r"^(?:export\s+)?class\s+(\w+)",
                r"^(?:export\s+)?(?:interface|type)\s+(\w+)",
            ],
            "go": [
                r"^func\s+(\w+)",
                r"^type\s+(\w+)\s+struct",
            ],
            "rust": [
                r"^fn\s+(\w+)",
                r"^struct\s+(\w+)",
                r"^impl\s+(\w+)",
            ],
            "java": [
                r"^class\s+(\w+)",
                r"^(?:public|private|protected)\s+\w+\s+(\w+)\s*\(",
            ],
        }

        for line in text.split("\n"):
            stripped = line.strip()
            for pat in patterns.get(language, []):
                m = re.match(pat, stripped)
                if m:
                    return m.group(1)
        return None

    # --- YAML chunking ---

    def _chunk_yaml(
        self, content: str, doc: RawDocument, metadata: ChunkMetadata
    ) -> List[DocumentChunk]:
        try:
            docs = list(yaml.safe_load_all(content))
        except yaml.YAMLError as e:
            logger.warning("YAML parse error for %s: %s", doc.file_name, e)
            return self._chunk_generic(content, doc, metadata)
        except Exception as e:
            logger.warning("YAML load error for %s: %s", doc.file_name, e)
            return self._chunk_generic(content, doc, metadata)

        if not docs:
            logger.debug("Empty YAML documents for: %s", doc.file_name)
            return self._chunk_generic(content, doc, metadata)

        max_depth = self.config.by_type.yaml.max_depth
        texts: List[str] = []
        symbols_raw: List[Optional[str]] = []

        for data in docs:
            if not isinstance(data, dict):
                flat = yaml.dump(data, default_flow_style=False) if data else ""
                if flat.strip():
                    texts.append(flat)
                    symbols_raw.append(None)
                continue

            for key, value in data.items():
                depth = self._yaml_value_depth(value)
                if depth <= max_depth:
                    chunk_yaml = yaml.dump(
                        {key: value}, sort_keys=False, default_flow_style=False
                    )
                    texts.append(chunk_yaml)
                    symbols_raw.append(str(key))
                else:
                    flat = yaml.dump({key: value}, default_flow_style=False)
                    texts.append(flat)
                    symbols_raw.append(str(key))

        if not texts:
            logger.debug("No YAML keys to chunk for: %s", doc.file_name)
            return self._chunk_generic(content, doc, metadata)

        # Deduplicate symbols by adding index to duplicates
        symbol_counts: Dict[str, int] = {}
        symbols: List[Optional[str]] = []
        for sym in symbols_raw:
            if sym is None:
                symbols.append(None)
            else:
                count = symbol_counts.get(sym, 0)
                symbol_counts[sym] = count + 1
                symbols.append(f"{sym}_{count}" if count > 0 else sym)

        logger.debug("YAML chunked: chunks=%d", len(texts))
        return self._build_chunks(
            texts=texts,
            chunk_type=ChunkType.YAML_KEY,
            doc=doc,
            base_metadata=metadata,
            symbols=symbols,
            language="yaml",
        )

    def _yaml_value_depth(self, value, current_depth: int = 0) -> int:
        if isinstance(value, dict):
            if not value:
                return current_depth
            return max(
                self._yaml_value_depth(v, current_depth + 1) for v in value.values()
            )
        if isinstance(value, list):
            if not value:
                return current_depth
            return max(
                self._yaml_value_depth(v, current_depth + 1) for v in value
            )
        return current_depth

    # --- JSON chunking ---

    def _chunk_json(
        self, content: str, doc: RawDocument, metadata: ChunkMetadata
    ) -> List[DocumentChunk]:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning("JSON parse error for %s: %s", doc.file_name, e)
            return self._chunk_generic(content, doc, metadata)

        texts: List[str] = []
        symbols_raw: List[Optional[str]] = []
        max_items = self.config.by_type.json_config.max_array_items

        if isinstance(data, dict):
            for key, value in data.items():
                text = json.dumps({key: value}, indent=2)
                texts.append(text)
                symbols_raw.append(str(key))

        elif isinstance(data, list):
            for i, item in enumerate(data[:max_items]):
                text = json.dumps(item, indent=2)
                texts.append(text)
                symbols_raw.append(f"[{i}]")

        else:
            texts.append(content)
            symbols_raw.append(None)

        if not texts:
            logger.debug("No JSON items to chunk for: %s", doc.file_name)
            return self._chunk_generic(content, doc, metadata)

        # Deduplicate symbols by adding index to duplicates
        symbol_counts: Dict[str, int] = {}
        symbols: List[Optional[str]] = []
        for sym in symbols_raw:
            if sym is None:
                symbols.append(None)
            else:
                count = symbol_counts.get(sym, 0)
                symbol_counts[sym] = count + 1
                symbols.append(f"{sym}_{count}" if count > 0 else sym)

        logger.debug("JSON chunked: chunks=%d", len(texts))
        return self._build_chunks(
            texts=texts,
            chunk_type=ChunkType.JSON_OBJECT if isinstance(data, dict) else ChunkType.JSON_ARRAY_ITEM,
            doc=doc,
            base_metadata=metadata,
            symbols=symbols,
            language="json",
        )

    # --- Logs chunking ---

    def _chunk_logs(
        self, content: str, doc: RawDocument, metadata: ChunkMetadata
    ) -> List[DocumentChunk]:
        config = self.config.by_type.logs
        pattern = re.compile(config.timestamp_pattern, re.MULTILINE)

        matches = list(pattern.finditer(content))
        logger.debug("Log chunking: %s — %d timestamp matches", doc.file_name, len(matches))
        if len(matches) <= 1:
            return self._build_chunks(
                texts=[content],
                chunk_type=ChunkType.LOG_BLOCK,
                doc=doc,
                base_metadata=metadata,
                symbols=[self._extract_timestamp(content, config.timestamp_pattern)],
                language="logs",
            )

        block_starts = [m.start() for m in matches]
        blocks: List[str] = []

        for i, start in enumerate(block_starts):
            end = block_starts[i + 1] if i + 1 < len(block_starts) else len(content)
            block = content[start:end].strip()
            if block:
                if len(block) > config.chunk_size:
                    sub_split = self.generic_splitter.split_text(block)
                    blocks.extend(sub_split)
                else:
                    blocks.append(block)

        if not blocks:
            blocks = [content]

        symbols = [
            self._extract_timestamp(b, config.timestamp_pattern) for b in blocks
        ]

        return self._build_chunks(
            texts=blocks,
            chunk_type=ChunkType.LOG_BLOCK,
            doc=doc,
            base_metadata=metadata,
            symbols=symbols,
            language="logs",
        )

    def _extract_timestamp(
        self, text: str, timestamp_pattern: str
    ) -> Optional[str]:
        m = re.match(timestamp_pattern, text.strip())
        return m.group(0) if m else None

    def _merge_small_chunks(
        self, chunks: List[str], chunk_size: int, overlap: int
    ) -> List[str]:
        if not chunks:
            return []

        merged: List[str] = []
        buffer = ""

        for chunk in chunks:
            if not buffer:
                buffer = chunk
            elif len(buffer) + len(chunk) + 1 <= chunk_size:
                buffer += "\n" + chunk
            else:
                merged.append(buffer)
                overlap_lines = self._get_overlap(buffer, overlap)
                if overlap_lines:
                    buffer = overlap_lines + "\n" + chunk
                else:
                    buffer = chunk

        if buffer:
            merged.append(buffer)

        return merged or chunks

    def _get_overlap(self, text: str, overlap_chars: int) -> str:
        lines = text.split("\n")
        result: List[str] = []
        char_count = 0
        for line in reversed(lines):
            if char_count + len(line) + 1 > overlap_chars:
                break
            result.insert(0, line)
            char_count += len(line) + 1
        return "\n".join(result)

    # --- Markdown chunking ---

    def _chunk_markdown(
        self, content: str, doc: RawDocument, metadata: ChunkMetadata
    ) -> List[DocumentChunk]:
        code_blocks: List[Tuple[str, int, int]] = []
        processed = content
        offset = 0

        for m in re.finditer(r"```(\w*)\n.*?```", content, re.DOTALL):
            placeholder = f"__CODE_BLOCK_{len(code_blocks)}__"
            start = m.start() + offset
            end = m.end() + offset
            code_blocks.append((m.group(0), start, end))
            processed = processed[:start] + placeholder + processed[end:]
            offset += len(placeholder) - (end - start)

        h_config = self.config.by_type.markdown_code
        header_specs = [
            (tag, name) for tag, name in h_config.headers_to_split_on
        ]

        sections_raw = self._split_on_headers(processed, header_specs)
        logger.debug("Markdown sections: %d raw sections from %s", len(sections_raw), doc.file_name)

        texts: List[str] = []
        for section in sections_raw:
            restored = self._restore_code_blocks(section, code_blocks)
            if not restored.strip():
                continue
            texts.append(restored)

        if not texts:
            logger.debug("No markdown sections for: %s", doc.file_name)
            return self._chunk_generic(content, doc, metadata)

        symbols = []
        symbol_counts: Dict[str, int] = {}
        for t in texts:
            first_line = t.split("\n")[0].strip().rstrip("#").strip()
            base_symbol = first_line if first_line else None

            if base_symbol:
                count = symbol_counts.get(base_symbol, 0)
                symbol_counts[base_symbol] = count + 1
                symbols.append(f"{base_symbol}_{count}" if count > 0 else base_symbol)
            else:
                symbols.append(None)

        logger.debug("Markdown chunked: chunks=%d", len(texts))
        return self._build_chunks(
            texts=texts,
            chunk_type=ChunkType.MARKDOWN_SECTION,
            doc=doc,
            base_metadata=metadata,
            symbols=symbols,
            language="markdown",
        )

    def _split_on_headers(
        self, content: str, header_specs: List[Tuple[str, str]]
    ) -> List[str]:
        pattern_parts = []
        for tag, _ in header_specs:
            escaped = re.escape(tag)
            pattern_parts.append(f"^{escaped} .*$")

        if not pattern_parts:
            return [content]

        combined = "|".join(pattern_parts)
        matches = list(re.finditer(combined, content, re.MULTILINE))

        if not matches:
            return [content]

        sections: List[str] = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section = content[start:end].strip()
            if section:
                sections.append(section)

        return sections

    def _restore_code_blocks(
        self, text: str, code_blocks: List[Tuple[str, int, int]]
    ) -> str:
        for i, (code, _, _) in enumerate(code_blocks):
            placeholder = f"__CODE_BLOCK_{i}__"
            if placeholder in text:
                text = text.replace(placeholder, code, 1)
        return text

    # --- Generic text chunking ---

    def _chunk_generic(
        self, content: str, doc: RawDocument, metadata: ChunkMetadata
    ) -> List[DocumentChunk]:
        texts = self.generic_splitter.split_text(content)
        logger.debug("Generic chunked: %s — chunks=%d", doc.file_name, len(texts))
        return self._build_chunks(
            texts=texts,
            chunk_type=ChunkType.SECTION,
            doc=doc,
            base_metadata=metadata,
        )
