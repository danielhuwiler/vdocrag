import pymupdf4llm
from markdown_chunker import MarkdownChunkingStrategy

class Chunk:
    def __init__(self, chunk: str, page: int):
         self.chunk = chunk
         self.page = page

class Chunker:
    def __init__(self): 
        self.strategy = MarkdownChunkingStrategy(min_chunk_len=512,    # Minimum chunk size (default: 512)
                                                soft_max_len=800,       # Preferred maximum chunk size (default: 1024)
                                                hard_max_len=1024,      # Absolute maximum chunk size (default: 2048)
                                                detect_headers_footers=False,   # Detect and remove repeating headers/footers
                                                remove_duplicates=False,        # Remove duplicate chunks
                                                add_metadata=False,             # Add metadata in each chunk as YAML front matter,
                                                parallel_processing=True,
                                                max_workers=4
                                                )

    def chunk_document(self, data_file, page_to=None) -> list[Chunk]:
        if data_file.lower().endswith(".md"):
            with open(data_file, "r", encoding="utf-8") as f:
                md_text = f.read()
        else:
            # docling is not able to serialize links so we use pymupdf4llm
            if page_to:
                md_text = pymupdf4llm.to_markdown(doc=data_file, pages=(0, page_to-1))
            else:
                md_text = pymupdf4llm.to_markdown(doc=data_file)
        results = []
        chunks = self.strategy.chunk_markdown(md_text)
        for i, chunk in enumerate(chunks):
            results.append(Chunk(chunk=str(chunk), page=-1)) # page ignored for now
        return results