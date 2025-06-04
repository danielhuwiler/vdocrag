from enum import Enum
from util.graph_client import GraphClient
from util.llm_client import LLMClient
from pymilvus import MilvusClient
from pymilvus.model.dense import OpenAIEmbeddingFunction
from retrieval.base_retriever import RetrievedData
from util.constants import MILVUS_DB_PATH, MILVUS_COLLECTION_NAME_VDOCRAG, MILVUS_META_ATTRIBUTE_TEXT, MILVUS_META_ATTRIBUTE_PAGE, MILVUS_META_ATTRIBUTE_FILE, MILVUS_META_ATTRIBUTE_CATEGORY, MILVUS_META_ATTRIBUTE_DOCUMENTATION, MILVUS_META_ATTRIBUTE_VERSION, MILVUS_META_ATTRIBUTE_TYPE, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS
from dotenv import load_dotenv
load_dotenv()

class RetrievalType(Enum):
    VersionRetrieval = 1
    ChangeRetrieval = 2
    ContentRetrieval = 3

class RetrievalParam:
    def __init__(self, retrieval_type: RetrievalType, params):
        self.retrieval_type = retrieval_type
        self.params = params

class VDocRAGRetrieverDatabase:
    def __init__(self):
        self.graph = GraphClient()
        self.llm_client = LLMClient()
        self.vdb = MilvusClient(MILVUS_DB_PATH)
        self.vdb_embedding = OpenAIEmbeddingFunction(model_name=EMBEDDING_MODEL, dimensions=EMBEDDING_DIMENSIONS)

    def retrieve(self, params: RetrievalParam) -> RetrievedData:
        self.preprocess_params(params=params)
        match params.retrieval_type:
            case RetrievalType.VersionRetrieval:
                return self.wrap("Retrieved availabe versions in system", self.retrieve_versions(params=params.params))
            case RetrievalType.ChangeRetrieval:
                return self.wrap("Retrieved available changes in system", self.retrieve_changes(params=params.params))
            case RetrievalType.ContentRetrieval:
                return self.wrap("Retrieved available content in system", self.retrieve_content(params=params.params))

    def wrap(self, prefix, output) -> RetrievedData:
        if not isinstance(output, RetrievedData):
            return RetrievedData(chunks=f"{prefix}:\n{output}")
        return output
            
    def preprocess_params(self, params: RetrievalParam):
        parameters = params.params
        category_name = parameters.get("category")
        if category_name:
            category_name = self.retrieve_category_name(category_name)
            
        documentation_name = parameters.get("documentation")
        if documentation_name:
            documentation_name = self.retrieve_documentation_name(category_name=category_name, documentation_input_name=documentation_name)

        version_name = parameters.get("version")
        if version_name:
            version_name = self.retrieve_version(category_name=category_name, documentation_name=documentation_name, version_input_name=version_name)

    def retrieve_categories(self):
        query = """
        MATCH (c:Category)
        RETURN c.name AS name, c.description AS description
        ORDER BY c.name
        """
        with self.graph.session() as session:
            result = session.run(query)
            categories = [record.data() for record in result]
            retrieval_string = "\n".join(
                f"{i}. Category Name: {cat['name']}\n"
                for i, cat in enumerate(categories)
            )
        return retrieval_string
    
    def retrieve_documentations(self, params=None):
        category_name = None
        if params:
            category_name = params.get("category")
        
        with self.graph.session() as session:
            if category_name:
                # Only documentations within category
                query = """
                MATCH (c:Category {name: $category_name})-[:CONTAINS]->(d:Documentation)
                RETURN d.name AS name, d.description AS description, c.name AS category
                """
                result = session.run(query, category_name=category_name)
            else:
                # All documentations
                query = """
                MATCH (d:Documentation)
                OPTIONAL MATCH (c:Category)-[:CONTAINS]->(d)
                RETURN d.name AS name, d.description AS description, c.name AS category
                """
                result = session.run(query)
            
            documentations = [record.data() for record in result]
            retrieval_string = "\n".join(
                f"{i}. Documentation Name: {doc['name']}\n{i}. Documentation description: {doc['description']}\n{i}. Documentation category: {doc['category']}\n"
                for i, doc in enumerate(documentations)
            )
            return retrieval_string
        
    def retrieve_versions(self, params):
        category_name = params.get("category")
        documentation_name = params.get("documentation")

        if not category_name:
            return "Error: Parameter 'category' is required for version retrieval."
        
        query = """
        MATCH (c:Category {name: $category_name})-[:CONTAINS]->(d:Documentation)
        """
        if documentation_name:
            query += " WHERE d.name = $documentation_name"
        query += """
        MATCH (d)-[:HAS_VERSION]->(v:Version)
        RETURN d.name AS documentation, v.version AS version
        ORDER BY d.name, v.version
        """
        
        with self.graph.session() as session:
            result = session.run(query, category_name=category_name, documentation_name=documentation_name)
            versions = [record.data() for record in result]

        if not versions:
            return "No versions found for given parameters."

        return "\n".join(f"{i}. Documentation: {entry['documentation']}\n   Version: {entry['version']}" for i, entry in enumerate(versions, 1))

    def retrieve_changes(self, params):
        category_name = params.get("category")
        documentation_name = params.get("documentation")
        version_name = params.get("version")

        if not category_name:
            return "Error: Parameter 'category' is required for change retrieval."
        
        if not documentation_name:
            return  "Error: Parameter 'documentation' is required for change retrieval."
        
        params["type"] = "change" # only retrieve from change nodes
        
        retrieved_content = self.retrieve_content(params=params, entity_limit=150)

        query = """
        MATCH (c:Category {name: $category_name})-[:CONTAINS]->(d:Documentation {name: $documentation_name})-[:HAS_VERSION]->(v:Version)
        """

        if version_name:
            query += "WHERE v.version STARTS WITH $version_number\n"

        query += """
        MATCH (v)-[:HAS_CHANGES]->(changes:Changes)-[:INCLUDES]->(ch:Change)
        RETURN v.version AS version, ch.name AS name, ch.description AS description, ch.source_file AS file
        ORDER BY v.version
        """

        query_params = {
            "category_name": category_name,
            "documentation_name": documentation_name,
        }

        if version_name:
            query_params["version_number"] = version_name

        with self.graph.session() as session:
            result = session.run(query, **query_params)
            changes = [record.data() for record in result]

        if not changes:
            return "No changes found."

        result_string = ""
        for i, ch in enumerate(changes, start=1):
            result_string += f"{i}. Version: {ch['version']}\n"
            result_string += f"   Name: {ch['name']}\n"
            result_string += f"   Description: {ch['description']}\n"
            result_string += f"   Source File: {ch['file']}\n\n"
        
        return f"retrieved content in changes: {retrieved_content}\nretrieved changes:{result_string.strip()}"
    
    def retrieve_content(self, params, entity_limit=15) -> RetrievedData:
        query = params.get("query")
        category = params.get("category")
        documentation = params.get("documentation")
        version = params.get("version")
        type = params.get("type")
        
        if not query:
            return "Error: Parameter 'query' is required for content retrieval."
        
        if not self.vdb.has_collection(collection_name=MILVUS_COLLECTION_NAME_VDOCRAG):
            return "no data indexed"
        
        # create vdb filter from params
        filters = []
        if category:
            filters.append(f'category == "{category}"')
        if documentation:
            filters.append(f'documentation == "{documentation}"')
        if version:
            filters.append(f'version like "{version}%"')
        if type:
            filters.append(f'type == "{type}"')
        filter_string = " and ".join(filters) if filters else ""

        query_vectors = self.vdb_embedding.encode_queries([query])

        res = self.vdb.search(
            collection_name=MILVUS_COLLECTION_NAME_VDOCRAG,
            data=query_vectors,
            limit=entity_limit,  # number of returned entities
            output_fields=[MILVUS_META_ATTRIBUTE_TEXT, 
                           MILVUS_META_ATTRIBUTE_PAGE, 
                           MILVUS_META_ATTRIBUTE_FILE, 
                           MILVUS_META_ATTRIBUTE_CATEGORY, 
                           MILVUS_META_ATTRIBUTE_DOCUMENTATION, 
                           MILVUS_META_ATTRIBUTE_VERSION, 
                           MILVUS_META_ATTRIBUTE_TYPE],
            filter=filter_string
        )

        results = res[0]
        chunks = [hit["entity"][MILVUS_META_ATTRIBUTE_TEXT] for hit in results]
        page_nrs = [hit["entity"][MILVUS_META_ATTRIBUTE_PAGE] for hit in results]
        source_files = [hit["entity"][MILVUS_META_ATTRIBUTE_FILE] for hit in results]
        versions = [hit["entity"][MILVUS_META_ATTRIBUTE_VERSION] for hit in results]
        return RetrievedData(chunks, page_nrs, source_files, versions)

    def retrieve_category_name(self, category_input_name):
        # get existing category name for input name
        if category_input_name is None or category_input_name == "":
            return ""
    
        system_prompt = f"""
        You are an intelligent assistant that matches a given input name to the most relevant category based on a provided list of category names and descriptions.
		- Analyze the input name and compare it to the category names and descriptions.
	    - Return only the exact name of the best matching category without \" or other special characters.
	    - If no suitable category is found, return an empty response (do not generate a default or approximate category).
	    - Ensure the output is a valid string that with no extra text or formatting.
        Available categories:
        {self.retrieve_categories()}
        """
        category = self.llm_client.generate(system_prompt=system_prompt, user_prompt=category_input_name)
        if category == "":
            return category_input_name
        return category
    
    def retrieve_documentation_name(self, category_name, documentation_input_name):
        if not documentation_input_name:
            return ""

        all_docs = self.retrieve_documentations(params={"category": category_name})
        if not all_docs:
            return ""

        system_prompt = f"""
        You are an intelligent assistant that matches a given input name to the most relevant documentation within a category, 
        based on a list of documentation names and their descriptions.

        Guidelines:
        - Analyze the input name and compare it to the documentation names and descriptions.
        - Return **only** the exact name of the best matching documentation.
        - Do not provide any reasoning in the output, only return the exact name.
        - If no suitable documentation is found, return an empty string.
        - Ensure the output is a valid string with no extra text or formatting.

        Available documentations in category '{category_name}':
        {all_docs}
        """

        documentation_name = self.llm_client.generate(
            system_prompt=system_prompt,
            user_prompt=documentation_input_name
        ).strip()

        if not documentation_name or documentation_name == "":
            return documentation_input_name
        return documentation_name
    
    def retrieve_version(self, category_name, documentation_name, version_input_name):
        if not version_input_name:
            return ""

        all_versions = self.retrieve_versions(params={"category": category_name, "documentation": documentation_name})
        if not all_versions:
            return ""

        system_prompt = f"""
        You are an intelligent assistant that identifies the most relevant version name from a list of available version identifiers, based on a user input.
        Guidelines:
        - Analyze the input string and compare it to the list of available versions.
        - Return only the **exact** version name that best matches the user input.
        - The exact version name has to be returned.
        - If no suitable version is found, return an empty string.
        - Ensure the output is a valid string with no extra text or formatting, just the version.
        Context:
        Category: '{category_name}'
        Documentation: '{documentation_name}'
        Available versions:
        {all_versions}
        """

        version_name = self.llm_client.generate(
            system_prompt=system_prompt,
            user_prompt=version_input_name
        )

        if not version_name.strip():
            return version_input_name
        return version_name.strip() 
            
