import os
import re
import neo4j
from dotenv import load_dotenv

from retrieval.base_retriever import BaseRetriever, RetrievedData
from util.constants import LLM_MODE, EMBEDDING_MODEL
from util.groq_llm_client import GROQLLM

from neo4j_graphrag.indexes import create_vector_index, create_fulltext_index
from neo4j_graphrag.retrievers import HybridCypherRetriever
from neo4j_graphrag.llm import OpenAILLM as LLM
from neo4j_graphrag.generation import RagTemplate
from neo4j_graphrag.generation.graphrag import GraphRAG
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings

# Load environment variables
load_dotenv()

# Constants
FULLTEXT_INDEX_NAME = "fulltext-index-name"
VECTOR_INDEX_NAME = "text_embeddings"
VECTOR_DIMENSIONS = 1536


class KnowledgeGraphRetriever(BaseRetriever):
    def __init__(self):
        self.driver = neo4j.GraphDatabase.driver(
            os.getenv("NEO4J_URI_AURA"),
            auth=(os.getenv("NEO4J_USERNAME_AURA"), os.getenv("NEO4J_PASSWORD_AURA"))
        )

        # Create indexes
        create_vector_index(
            self.driver,
            name=VECTOR_INDEX_NAME,
            label="Chunk",
            embedding_property="embedding",
            dimensions=VECTOR_DIMENSIONS,
            similarity_fn="cosine"
        )

        create_fulltext_index(
            self.driver,
            FULLTEXT_INDEX_NAME,
            label="Chunk",
            node_properties=["text"],
            fail_if_exists=False
        )

        # Set embedder and LLM
        self.embedder = OpenAIEmbeddings(model=EMBEDDING_MODEL)

        if LLM_MODE == 'openai':
            self.llm = LLM(model_name="gpt-4o-mini")
        elif LLM_MODE == 'groq':
            self.llm = GROQLLM()
        else:
            print("LLM missing in offline mode")

        # Hybrid retriever configuration
        self.hc_retriever = HybridCypherRetriever(
            self.driver,
            VECTOR_INDEX_NAME,
            FULLTEXT_INDEX_NAME,
            retrieval_query="""
                // 1) Go out 2-3 hops in the entity graph and get relationships
                WITH node AS chunk
                MATCH (chunk)<-[:FROM_CHUNK]-()-[relList:!FROM_CHUNK]-{0,1}()
                UNWIND relList AS rel

                // 2) Collect relationships and text chunks
                WITH collect(DISTINCT chunk) AS chunks,
                     collect(DISTINCT rel) AS rels

                // 3) Format and return context
                RETURN '=== text ===\\n' + apoc.text.join([c IN chunks | c.text], '\\n---\\n') +
                       '\\n\\n=== kg_rels ===\\n' +
                       apoc.text.join([
                           r IN rels | startNode(r).name + ' - ' + type(r) + '(' +
                           coalesce(r.details, '') + ') -> ' + endNode(r).name
                       ], '\\n---\\n') AS info
            """,
            embedder=self.embedder,
        )

        # Prompt template
        #self.rag_template = RagTemplate(
        #    template=(
        #        "Answer the Question using the following Context. "
        #        "Only respond with information mentioned in the Context. "
        #        "Do not inject any speculative information not mentioned.\n\n"
        #        "# Question:\n{query_text}\n\n# Context:\n{context}\n\n# Answer:"
        #    ),
        #    expected_inputs=['query_text', 'context']
        #)

        # GraphRAG setup
        #self.v_rag = GraphRAG(
        #    llm=self.llm,
        #    retriever=self.hc_retriever,
        #    prompt_template=self.rag_template
        #)

        super().__init__()

    def retrieve(self, query):
        return self.safe_search(query=query, initial_top_k=10, min_top_k=1)

    def safe_search(self, query, initial_top_k=3, min_top_k=1):
        top_k = initial_top_k
        escaped_query = self.escape_lucene_special_chars(query)

        while top_k >= min_top_k:
            try:
                return self.hc_retriever.search(query_text=query, top_k=top_k)
            except Exception as e:
                top_k -= 1  # Reduce top_k and try again

        raise RuntimeError("Search failed even with reduction of top_k")

    @staticmethod
    def escape_lucene_special_chars(text):
        return re.sub(r'([+\-!(){}\[\]^"~*?:\\/])', r'\\\1', text)