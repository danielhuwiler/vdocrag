import os
import time
from dotenv import load_dotenv
from pymilvus import MilvusClient
from pymilvus.model.dense import OpenAIEmbeddingFunction
from util.constants import MILVUS_DB_PATH, MILVUS_META_ATTRIBUTE_TEXT, MILVUS_META_ATTRIBUTE_PAGE, MILVUS_META_ATTRIBUTE_FILE, MILVUS_META_ATTRIBUTE_CATEGORY, MILVUS_META_ATTRIBUTE_DOCUMENTATION, MILVUS_META_ATTRIBUTE_VERSION, MILVUS_META_ATTRIBUTE_TYPE, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS
from util.chunker import Chunker, Chunk

load_dotenv()

class BaseIndexer:
    def __init__(self):
        self.embedding_fn = OpenAIEmbeddingFunction(model_name=EMBEDDING_MODEL, dimensions=EMBEDDING_DIMENSIONS)
        self.client = None
        self.chunker = Chunker()
        
    def index_data(self, data_files):
        raise NotImplementedError("Subclasses must implement this method.")
    
    def createCollectionIfRequired(self, collection_name):
        if self.client is None:
            self.client = MilvusClient(MILVUS_DB_PATH)
        
        if not self.client.has_collection(collection_name=collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                dimension=EMBEDDING_DIMENSIONS,
            )
    
    def index_file(self, data_file, collection_name, category="", documentation="", version=""):
        data_file_name = os.path.basename(data_file)
        print(f"Indexing: {data_file_name}")

        chunks = self.chunker.chunk_document(data_file=data_file)
        self.index(chunks=chunks, collection_name=collection_name, data_file=data_file, category=category, documentation=documentation, version=version, type="file")
        print(f"Indexed: {data_file_name} ({len(chunks)} chunks)")
        
    def index_chunk(self, chunk:Chunk, collection_name, category, documentation, version, type, file):
        self.index(chunks=[chunk], collection_name=collection_name, category=category, documentation=documentation, version=version, type=type, data_file=file)
        
    def index(self, chunks, collection_name, data_file="", category="", documentation="", version="", type=""):
        chunk_texts = [chunk.chunk for chunk in chunks]
        batch_size = 100

        for i in range(0, len(chunk_texts), batch_size):
            batch = chunk_texts[i:i + batch_size]
            batch_vectors = self.embedding_fn.encode_documents(batch)
            data = [
                {"id": i, 
                "vector": batch_vectors[i],
                MILVUS_META_ATTRIBUTE_TEXT: chunks[i].chunk, 
                MILVUS_META_ATTRIBUTE_PAGE: chunks[i].page, 
                MILVUS_META_ATTRIBUTE_FILE: data_file,
                MILVUS_META_ATTRIBUTE_CATEGORY: category,
                MILVUS_META_ATTRIBUTE_DOCUMENTATION: documentation,
                MILVUS_META_ATTRIBUTE_VERSION: version,
                MILVUS_META_ATTRIBUTE_TYPE: type}
                for i in range(len(batch_vectors))
            ]
            self.client.insert(collection_name=collection_name, data=data)
            time.sleep(1)

    