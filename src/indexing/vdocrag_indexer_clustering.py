from indexing.vdocrag_indexer_extract_attributes import FileAttributes
from util.llm_client import LLMClient
import json
import os

llm_client = LLMClient(json_format=True, temp=0.5)

def cluster_documentation(data_files: list[FileAttributes]):
    # cluster similar documentations based on their description
    system_prompt = """
                    You are an intelligent assistant specialized in clustering categories based on their name, description and filename.
                    You will be provided with a list of categories, each containing a name and a description. Your task is to group these categories based on their content similarity, considering the topic and the general description. 
                    **Ignore any versioning information in the descriptions, as it should not contribute to the clustering.**  

                    1. Each category has a "name" and a "description". You should focus on the main topic and theme of the description to group similar categories.
                    2. For each resulting cluster, generate a:
                    - **"cluster_name"**: a short, representative title of the cluster.
                    - **"cluster_description"**: a summary of what the grouped categories have in common.
                    - **"category_indices"**: an array of integers representing the indices of the grouped categories.
                    3. The output must be a **JSON array**, where each item represents a cluster with a name, a description, and a list of indices.
                    4. Do not include any additional explanation or text outside the JSON.
                    5. Ignore any versioning or version-related text in the descriptions.
                    6. Treat categories that focus on the same core subject as belonging to the same cluster, even if their descriptions vary slightly in wording or emphasis.
                    7. Use semantic similarity between both the name and the description to identify near-duplicates or closely related entries.

                    **Output format (example):**
                    ```json
                    {
                        "clusters": [
                            {
                            "cluster_name": "Authentication Services",
                            "cluster_description": "Categories related to user authentication, login systems, and identity verification.",
                            "category_indices": [0, 2, 5]
                            },
                            {
                            "cluster_name": "Authentication Errors",
                            "cluster_description": "Categories covering payment gateways, transaction APIs, and financial services.",
                            "category_indices": [1, 3]
                            }
                        ]
                    }"""
    sorted_data_files = sorted(data_files, key=lambda x: os.path.basename(x.data_file).lower())
    all_categories_with_description = "\n".join(
        f"{i} documentation name: {data_file.documentation}\n {i} description: {data_file.description}\n {i} filename: {os.path.basename(data_file.data_file)}"
        for i, data_file in enumerate(sorted_data_files)
    )
    all_categories_with_description = "\n".join(f"{i} documentation name: {data_file.documentation}\n {i} description: {data_file.description}\n {i} filename: {os.path.basename(data_file.data_file)}" for i, data_file in enumerate(data_files))
    response = llm_client.generate(system_prompt=system_prompt, user_prompt=all_categories_with_description)
    response = response.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(response)
        parsed_result = data.get("clusters", [])
    except:
        raise ValueError(f"error during clustering result parsing {response}")
    
    for cluster in parsed_result:
        cluster_name = cluster["cluster_name"]
        cluster_description = cluster["cluster_description"]
        indices = cluster["category_indices"]
        for i, sub_data_file_index in enumerate(indices):
            # set same documentation to sub data files in same cluster
            data_files[sub_data_file_index].documentation = cluster_name
            data_files[sub_data_file_index].description = cluster_description
            print("updated documentation for file in cluster")
                
def cluster_categories(documentations: list):
    # group similar documentations based on their names and description into categories
    system_prompt = """
            You are an AI assistant specialized in categorizing and clustering documentation files based on their names and descriptions.

            ## Task
            You will receive a list of documentation entries, each containing:
            - "name": The title of the document.
            - "description": A brief summary of the document’s content.

            ## Your Goal
            1. Identify meaningful categories by grouping similar documentation entries based on their names and descriptions.
            2. Assign each documentation entry to exactly one category that best represents its topic.
            3. Generate a clear and concise category title in the same language as the majority of the document names in that category.

            ## Important Guidelines
            - Categories should be broad but specific enough to group related documents meaningfully.
            - Release Notes should be categorized into separate categories **if they relate to different technologies**.
            - Ignore minor variations in phrasing—focus on the core subject.
            - The category title must be in the same language as the documentation names in that category.
            - The category title must be descriptive yet concise (maximum 5 words).
            - Ensure every document is assigned to exactly one category.
            - Merge very similar categories into one.
            - Output must be valid JSON and ready for parsing.

            ## Output Format
            Return a single JSON object with the following structure:

            ```json
            {
            "categories": [
                {
                "name": "Release Notes Apache",
                "documents": [
                    "Meldeverfahren zur Sozialversicherung",
                    "Sozialversicherungsanmeldung"
                ]
                },
                {
                "name": "Release Notes DEÜV",
                "documents": [
                    "IT-Sicherheitsrichtlinie",
                    "Datenschutzbestimmungen"
                ]
                }
            ]
            }
   """
    all_documentations_with_description = "\n".join(f"{i} documentation name: {documentation['name']}\n{i} description: {documentation['description']}\n" for i, documentation in enumerate(documentations))
    print(all_documentations_with_description)
    max_attempts = 3
    for attempt in range(max_attempts):
        response = llm_client.generate(system_prompt=system_prompt, user_prompt=all_documentations_with_description)
        response = response.replace("```json", "").replace("```", "").strip()
        try:
            data = json.loads(response)
            return data.get("categories", [])
        except json.JSONDecodeError:
            if attempt >= max_attempts:
                raise ValueError(f"Error during clustering result parsing after {max_attempts} attempts: {response}")
    