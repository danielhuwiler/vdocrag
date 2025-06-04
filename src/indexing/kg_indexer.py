import os
from indexing.base_indexer import BaseIndexer
import asyncio
import time
import neo4j
from neo4j_graphrag.experimental.components.text_splitters.fixed_size_splitter import FixedSizeSplitter
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
from neo4j_graphrag.llm import OpenAILLM
from dotenv import load_dotenv
from util.groq_llm_client import GROQLLM
from util.constants import LLM_MODE, EMBEDDING_MODEL

load_dotenv()

prompt_template = '''
You are a intelligent agent tasks with extracting information from papers 
and structuring it in a property graph to inform further and research Q&A.

Extract the entities (nodes) and specify their type from the following Input text.
Also extract the relationships between these nodes. the relationship direction goes from the start node to the end node. 


Return result as JSON using the following format:
{{"nodes": [ {{"id": "0", "label": "the type of entity", "properties": {{"name": "name of entity" }} }}],
  "relationships": [{{"type": "TYPE_OF_RELATIONSHIP", "start_node_id": "0", "end_node_id": "1", "properties": {{"details": "Description of the relationship"}} }}] }}

- Use only the information from the Input text. Do not add any additional information.  
- If the input text is empty, return empty Json. 
- Make sure to create as many nodes and relationships as needed to offer rich context for further research.
- An AI knowledge assistant must be able to read this graph and immediately understand the context to inform detailed research questions. 
- Multiple documents will be ingested from different sources and we are using this property graph to connect information, so make sure entity types are fairly general. 
- Do **not** use "id" as a property name. It is not allowed to use "id" as a property name.

Use only fhe following nodes and relationships (if provided):
{schema}

Assign a unique ID (string) to each node, and reuse it to define relationships.
Do respect the source and target node types for relationship and
the relationship direction.

Do not return any additional information other than the JSON in it.

Examples:
{examples}

Input text:

{text}
'''



class KnowledgeGraphIndexer(BaseIndexer):
    def __init__(self):
        super().__init__()
        self.driver = neo4j.GraphDatabase.driver(os.getenv("NEO4J_URI_AURA"),
                                          auth=(os.getenv("NEO4J_USERNAME_AURA"), os.getenv("NEO4J_PASSWORD_AURA")))
        
        if LLM_MODE == 'openai':
            self.llm = OpenAILLM(
                model_name='gpt-4o-mini',
                model_params={
                    'response_format': {'type': 'json_object'},
                    'temperature': 0
                }
            )
        elif LLM_MODE == 'groq':
            self.llm = GROQLLM(temp=0.0, response_format_json=True)
        else:
            print("no offline mode defined")

        self.embedder = OpenAIEmbeddings(model=EMBEDDING_MODEL)

        self.kg_builder_pdf = SimpleKGPipeline(
                llm=self.llm,
                driver=self.driver,
                text_splitter=FixedSizeSplitter(chunk_size=512, chunk_overlap=100),
                embedder=self.embedder,
                prompt_template=prompt_template,
                from_pdf=True
        )
        
        self.kg_builder = SimpleKGPipeline(
                llm=self.llm,
                driver=self.driver,
                text_splitter=FixedSizeSplitter(chunk_size=512, chunk_overlap=100),
                embedder=self.embedder,
                prompt_template=prompt_template,
                from_pdf=False
        )

    def index_data(self, data_files=None):
        first_file = data_files[0]
        data_dir = os.path.dirname(os.path.abspath(first_file))
        print(f"📁 Automatically set data_dir to: {data_dir}")
        
        if not os.path.isdir(data_dir):
            raise FileNotFoundError(f"Directory {data_dir} does not exist.")
        
        print(f"Reading documents from: {data_dir}")
        
        for data_file in data_files:
            print(f"Indexing {data_file}")
            attempts = 3
            for attempt in range(1, attempts + 1):
                try:
                    if data_file.lower().endswith(".pdf"):
                        pdf_result = asyncio.run(self.kg_builder_pdf.run_async(file_path=data_file))
                    else:
                        with open(data_file, "r", encoding="utf-8") as f:
                            md_text = f.read()
                            pdf_result = asyncio.run(self.kg_builder.run_async(text=md_text))
                    print(f"Result: {pdf_result}")
                    break  # success, exit retry loop
                except Exception as e:
                    print(f"[Attempt {attempt}/{attempts}] Error processing {data_file}: {e}")
                    if attempt == attempts:
                        print(f"Failed to process {data_file} after {attempts} attempts.")
                    else:
                        time.sleep(2)  # optional delay before retrying
            time.sleep(2)  # delay between files

        print("✅ Indexing complete.")
