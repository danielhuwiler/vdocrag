from retrieval.base_retriever import BaseRetriever
from retrieval.vdocrag_retriever_db import VDocRAGRetrieverDatabase
from retrieval.vdocrag_retriever_parser import VDocRAGRetrieverParser

class VDocRAGRetriever(BaseRetriever):
    def __init__(self):
        self.database = VDocRAGRetrieverDatabase()
        self.parser = VDocRAGRetrieverParser(self.database)
        super().__init__()
        
    def retrieve(self, query: str):
        retrieval_param = self.parser.parse_retrieval_mode(query=query)
        retrieval = self.database.retrieve(params=retrieval_param)
        return retrieval