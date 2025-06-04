from indexing.base_indexer import BaseIndexer
from util.constants import MILVUS_COLLECTION_NAME_BASELINE

class BaselineIndexer(BaseIndexer):
    def index_data(self, data_files):
        print("Indexing data using Baseline Indexer.")
        
        self.createCollectionIfRequired(MILVUS_COLLECTION_NAME_BASELINE)
        for data_file in data_files:
            self.index_file(data_file, MILVUS_COLLECTION_NAME_BASELINE)