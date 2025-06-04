from indexing.base_indexer import BaseIndexer
from indexing.vdocrag_indexer_graph import VDocRAGIndexerGraph
from indexing.vdocrag_indexer_extract_attributes import extract_attributes_from_file
from indexing.vdocrag_indexer_clustering import cluster_documentation
from util.chunker import Chunk
from util.constants import MILVUS_COLLECTION_NAME_VDOCRAG

class VDocRAGIndexer(BaseIndexer):
    def __init__(self):
        self.graph = VDocRAGIndexerGraph()
        super().__init__()
         
    def index_data(self, data_files):
        # extract attributes for all data_files
        files_with_extracted_attributes = self.extract_attributes(data_files)
        print(f"extracted attributes from {len(files_with_extracted_attributes)} files")
                
        # cluster documentations
        cluster_documentation(files_with_extracted_attributes)
        print("clustered documentations")
            
        # basic graph structure
        self.graph.generate_basic_graph(files_with_extracted_attributes)
        print("basic graph generated")
            
        # change level construction
        self.graph.generate_change_level()
        print("change level constructed")
        
        # content indexing
        content_nodes = self.graph.get_all_content_nodes_with_context()
        change_nodes = self.graph.get_all_change_nodes_with_context()
        self.index_content(content_nodes=content_nodes, change_nodes=change_nodes)
        print("content indexed")
            
    def index_content(self, content_nodes: list, change_nodes: list):
        self.createCollectionIfRequired(MILVUS_COLLECTION_NAME_VDOCRAG)
        
        for content_node in content_nodes:
            self.index_file(data_file=content_node["file"], 
                            collection_name=MILVUS_COLLECTION_NAME_VDOCRAG, 
                            category=content_node["category"],
                            documentation=content_node["documentation"],
                            version=content_node["version"])
        
        for change_node in change_nodes:
            chunk_text = change_node["name"]
            description = change_node.get("description")
            if description:
                chunk_text += "\n" + description
            self.index_chunk(chunk=Chunk(chunk=chunk_text, page=-1),
                             collection_name=MILVUS_COLLECTION_NAME_VDOCRAG, 
                             category=change_node["category"],
                             documentation=change_node["documentation"],
                             version=change_node["version"],
                             file=change_node["file"],
                             type="change")
            
    def extract_attributes(self, data_files):
        files_with_extracted_attributes = []
        for data_file in data_files:
            try:
                attributes = extract_attributes_from_file(data_file=data_file)
                print(attributes)
                files_with_extracted_attributes.append(attributes)
            except Exception as e:
                raise ValueError(f"attribute extraction of file {data_file} failed: {e}")
        return files_with_extracted_attributes
        
            