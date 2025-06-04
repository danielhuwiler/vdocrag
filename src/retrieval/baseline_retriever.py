from retrieval.base_retriever import BaseRetriever, RetrievedData
from pymilvus import MilvusClient
from pymilvus.model.dense import OpenAIEmbeddingFunction
from util.constants import MILVUS_DB_PATH, MILVUS_COLLECTION_NAME_BASELINE, MILVUS_META_ATTRIBUTE_TEXT, MILVUS_META_ATTRIBUTE_PAGE, MILVUS_META_ATTRIBUTE_FILE, MILVUS_BASELINE_SOURCE_COUNT, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS
from dotenv import load_dotenv
load_dotenv()

class BaselineRetriever(BaseRetriever):
    def __init__(self):
        self.embedding_fn = OpenAIEmbeddingFunction(model_name=EMBEDDING_MODEL, dimensions=EMBEDDING_DIMENSIONS)
        self.client = None
        super().__init__()

    def retrieve(self, query):
        if self.client is None:
            self.client = MilvusClient(MILVUS_DB_PATH)
        
        query_vectors = self.embedding_fn.encode_queries([query])

        res = self.client.search(
            collection_name=MILVUS_COLLECTION_NAME_BASELINE,  # target collection
            data=query_vectors,  # query vectors
            limit=MILVUS_BASELINE_SOURCE_COUNT,  # number of returned entities
            output_fields=[MILVUS_META_ATTRIBUTE_TEXT, MILVUS_META_ATTRIBUTE_PAGE, MILVUS_META_ATTRIBUTE_FILE],  # specifies fields to be returned
        )

        results = res[0]
        chunks = [hit["entity"][MILVUS_META_ATTRIBUTE_TEXT] for hit in results]
        page_nrs = [hit["entity"][MILVUS_META_ATTRIBUTE_PAGE] for hit in results]
        source_files = [hit["entity"][MILVUS_META_ATTRIBUTE_FILE] for hit in results]
        
        return RetrievedData(chunks, page_nrs, source_files)