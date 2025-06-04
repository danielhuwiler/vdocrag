from retrieval.vdocrag_retriever_db import RetrievalParam, RetrievalType
from util.llm_client import LLMClient
import json

system_prompt = """
            You are an advanced AI assistant specializing in query classification and parameter extraction.
            Your task is to determine which of the following query retrieval types best fits the user’s question, based solely on the question content.
            Then, extract the relevant parameters required for that retrieval type.

            ### **Query Retrieval Types and Expected Parameters**
            1. **VersionRetrieval** → `{ "category": "<category_name>" (required), "documentation": "<documentation_name>" (optional) }`  
            2. **ChangeRetrieval** → `{ "query": "<query>" (required), "category": "<category_name>" (required), "documentation": "<documentation_name>" (required), "version": "<version_number>" (optional) }`  
            3. **ContentRetrieval** → `{ "query": "<query>" (required), "category": "<category_name>" (optional), "documentation": "<documentation_name>" (optional), "version": "<version_number>" (optional) }`  

            ### **Output Format (Valid JSON only)**  
            The response must be formatted as a **valid JSON object** containing:  
            - `"retrieval"`: The determined query retrieval mode.  
            - `"parameters"`: A dictionary containing the extracted parameters and at least the required parameters for the retrieval type.

            ### **Example Outputs**  

            1.	User Query: “Show me all changes in version 2.0 of API documentation in the Software category.”
            Output:
            {
            "retrieval": "ChangeRetrieval",
            "parameters": { "query": "all changes in version 2.0 of API documentation in the Software category", "category": "Software", "documentation": "API", "version": "2.0" }
            }
            
            ### **Descriptions of different Retrieval Types**
            - VersionRetrieval: Retrieves all available versions in a category optionally filtered by a single documentation.
            - ChangeRetrieval: Retrieves all changes made in specific category and documentation, optionally filtered by a specific version.
            - ContentRetrieval: Retrieves all content optionally filtered by category, documentation or version.

            Important Guidelines
            - Ensure the response is always valid JSON, suitable for direct parsing in Python.
            - Do not assume information that is not explicitly stated in the query.
            - The available categories and documentations are listed in the user query as context.
            - When adding a documentation as parameter, only use documentations which are in the selected category.
            - Allowed retrieval modes are VersionRetrieval, ChangeRetrieval, ContentRetrieval
            - Only the specified parameters are allowed. Required parameters must be extracted. Optional parameters have to be extracted if present.
            - If the query does not fit into any category, the default is ContentRetrieval.
        """

class VDocRAGRetrieverParser:
    def __init__(self, database):
        self.database = database
        self.llm_client = LLMClient(json_format=True, temp=0.0)

    def parse_retrieval_mode(self, query) -> RetrievalParam:
        user_query = f"Available categories: {self.database.retrieve_categories()}\nAvailable documentations: {self.database.retrieve_documentations()}\nUser query: {query}"
        max_attempts = 5
        
        parsed_result = None
        for attempt in range(max_attempts):
            response = self.llm_client.generate(system_prompt=system_prompt, user_prompt=user_query)
            response = response.replace("```json", "").replace("```", "").strip()
            try:
                parsed_result = json.loads(response)
                break
            except json.JSONDecodeError as e:
                if attempt >= max_attempts:
                    raise ValueError(f"Error parsing JSON response: {e}")

        print(f"retrieval mode: {parsed_result}")
        parsed_retrieval_type = parsed_result["retrieval"]
        parsed_params = parsed_result["parameters"]
        retrieval_type = RetrievalType[parsed_retrieval_type]
        return RetrievalParam(retrieval_type=retrieval_type, params=parsed_params)