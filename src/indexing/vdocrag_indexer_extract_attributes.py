from enum import Enum
from util.llm_client import LLMClient
from util.chunker import Chunker
import json
import re
import PyPDF2

llm_client = LLMClient(json_format=True, temp=0.0)
chunker = Chunker()

class FileType(Enum):
    WithoutChangelog = 1
    Changelog = 2
    
class FileAttributes:
    def __init__(self, data_file: str, type: FileType, documentation: str, description: str, version: str, additional_attributes: list):
        self.data_file = data_file
        self.type = type
        self.documentation = documentation
        self.description = description
        self.version = version
        self.additional_attributes = additional_attributes
        
    def __str__(self):
        return (f"File: {self.data_file}\n"
                f"File Type: {self.type.name}\n"
                f"Documentation: {self.documentation}\n"
                f"Description: {self.description}\n"
                f"Version: {self.version}\n"
                f"Additional Attributes:\n" +
                (
                    "\n".join([f"  - {attr}: {value}" for attr, value in self.additional_attributes.items()])
                    if self.additional_attributes else "  - None"
                ))

def extract_attributes_from_file(data_file) -> FileAttributes:
    print(f"extract attributes from file {data_file}")
    first_text_short = ""
    first_text_long = ""
    if data_file.lower().endswith(".pdf"):
        # extract pages from pdf
        page_count = get_page_count(data_file)
        if page_count == 0:
            raise ValueError(f"file is empty: {data_file}")
        print(f"page count {page_count}")
        
        chunks = chunker.chunk_document(data_file=data_file, page_to=1)
        first_text_short = "\n".join(chunk.chunk for chunk in chunks if chunk.chunk)
        chunks = chunker.chunk_document(data_file=data_file, page_to=min(page_count, 10))
        first_text_long = "\n".join(chunk.chunk for chunk in chunks if chunk.chunk)
    elif data_file.lower().endswith(".md"):
        # extract chunks from markdown
        chunks = chunker.chunk_document(data_file=data_file)
        chunk_count = len(chunks)
        if chunk_count == 0:
            raise ValueError(f"file is empty: {data_file}")
        print(f"chunk count {chunk_count}")
        # Kombiniere alle Chunks zu einem durchgehenden Text
        full_text = "".join(chunk.chunk for chunk in chunks if chunk.chunk)

        # Schneide die ersten 200 bzw. 500 Zeichen aus dem kombinierten Text
        first_text_short = full_text[:200]
        first_text_long = full_text[:300]
    else:
        raise ValueError(f'unsupported file type {data_file}')
    
    first_page_attributes = extract_attributes_from_first_page(first_text_short)
    file_type = extract_file_type_from_pages(first_text_long)

    return FileAttributes(data_file=data_file,
                          type=file_type, 
                          documentation=first_page_attributes["topic"], 
                          description=first_page_attributes["description"],
                          version=clean_version_string(first_page_attributes["version"]),
                          additional_attributes=first_page_attributes.get("additional_attributes"))

def get_page_count(data_file):
    with open(data_file, "rb") as file:
        pdfReader = PyPDF2.PdfReader(file)
        return len(pdfReader.pages)
    raise ValueError(f"unable to read page count from file: {data_file}")
    
def clean_version_string(version_str):
    """Keep only numbers, dashes, and dots from the version string."""
    return re.sub(r'[^0-9\-.]', '', version_str)

def extract_attributes_from_first_page(first_page_content):
    system_prompt_first_page = """
    You are an intelligent assistant specialized in extracting structured information from documents.  
    Your task is to analyze the first page of a given PDF and extract the following details in a structured JSON format. 
    Always answer in English.
    Do not add JSON comments to the output.

    1 **"topic"**: The main subject of the document.  
    - Provide a short, clear, and descriptive title (max. 10 words).  
    - Do not include any version reference in the title.
    - If no clear topic is found, return `"unknown"`.  
    
    2 **"description"**: A brief summary of the document based on the first page without explicit version-naming.
    - Summarize the content in 1-3 sentences.  
    - **Preserve the original language.**  
    - If no meaningful description is available, return `"unknown"`.
    
    3 **version**: The document’s version (this field can also contain a date if no version number is found).
	- Extract version identifiers such as 1.0, v2, Rev. 3, Edition B, Release 2024-A.
    - Do not include any other characters than numbers or dots or dashes in the version.
     - If a version identifier is found, use it. Even if version dates are present.
	-	If a date is stored as a version, always use the format 'dd-MM-yyyy'.
	-	If no version or date is found, return "unknown".
 
    **Output format (JSON example):**  
    ```json
    {
        "topic": "Node.js Assertion Module",
        "description": "The document provides information about the assert module in Node.js, detailing its functions and strict assertion mode, including examples of usage and error messaging.",
        "version": "17.9.1"
    }
    """

    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            first_page_response = llm_client.generate(system_prompt=system_prompt_first_page, user_prompt=first_page_content)

            # Convert JSON string to a Python dictionary
            first_page_response = first_page_response.replace("```json", "").replace("```", "").strip()
            data = json.loads(first_page_response)
            # Ensure at least one of "version" or "version_date" is present
            if data["version"] == "unknown":
                raise ValueError("Error: 'version' must be provided. ")
            return data
        except Exception as e:
            print(f"error during extraction: {e}")
            if attempt >= max_attempts:
                raise ValueError(f"Error: failed to parse llm response:\n response: {first_page_response}\n input:{first_page_content}")
    raise ValueError(f"unable to extract attributes from first page\n first page: {first_page_content}")

def extract_file_type_from_pages(pages_content):
    system_prompt_file_type = """
    You are an intelligent assistant specialized in analyzing document content.

    You will receive the first few chunks of a document (representing its beginning). Your task is to determine whether the document is a **changelog** or a general document.

    Return **only** a valid JSON object in the following format:  
    { "answer": 1 } or { "answer": 2 }

    ### Classification rules:

    1. **1** = WithoutChangelog  
        → The document does **not** contain a changelog in the provided chunks.  
        → These are general documents (e.g., manuals, specifications, reports) **without** a focus on version updates or modifications.  
        → Even if the document mentions changes or has some update history, **if it is not focused on listing changes**, classify it as **1**.

    2. **2** = Changelog  
        → The document **is a changelog** or **release/update log**.  
        → It is specifically focused on listing **changes**, updates, or version history. It includes terms like `Change`, `Revision`, `Modification`, `Amendment`, `Update`, etc.  
        → The document must be **dedicated to listing changes** and not just mention them casually.

    ### Notes:
    - Use only the given text chunks to make your decision.
    - If the type is unclear or you're unsure, return **1** as a safe default.
    - Return **only** the JSON object – no extra text or formatting.
    """
    max_attempts = 5

    for attempt in range(max_attempts):
        try:
            response = llm_client.generate(system_prompt=system_prompt_file_type, user_prompt=pages_content)
            data = json.loads(response) 
            answer = data.get("answer")
            if answer is not None and str(answer).isdigit():
                return FileType(int(answer))
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Attempt {attempt + 1} failed: {e}")

    raise ValueError('Unable to extract file type from file')

