from enum import Enum
from util.llm_client import LLMClient
from util.chunker import Chunker, Chunk
import json
from pdfminer.high_level import extract_text
from deepdiff import DeepDiff
import time

llm_client = LLMClient(json_format=True, temp=0.0)
chunker = Chunker()

class ChangeOrigin(Enum):
    Extraction = 1
    Differ = 2
    
class Change:
    def __init__(self, documentation: str, version: str, name: str, description: str, source_file: str, source_page_nr: int, origin: ChangeOrigin):
        self.documentation = documentation
        self.version = version
        self.name = name
        self.description = description
        self.source_file = source_file
        self.source_page_nr = source_page_nr
        self.origin = origin

def extract_changes_from_changelog(changelog_content) -> list[Change]:
    system_prompt="""
                   You are an assistant. Extract structured changes from changelog text chunks.

                    - Return a JSON object with a key "changes" (an array).
                    - Each change must have:
                    - "name": short title (string)
                    - "description": detailed explanation including any ticket numbers or IDs from the text (string)
                    - Use the original language.
                    - If no changes are found, return: { "changes": [] }
                    - Return only a valid JSON object. Do not include any other text, explanation, or formatting.

                    Example:
                    {
                    "changes": [
                        {
                        "name": "Login Retry Updated",
                        "description": "The login retry logic now includes exponential backoff and lockout timing (Ticket #12345)."
                        },
                        {
                        "name": "Encryption Standards Added",
                        "description": "New section for encryption standards introduced, including AES-256 and RSA (ID-4567)."
                        }
                    ]
                    }
                                   """
    changelog_file = changelog_content["file"]
    chunks = chunker.chunk_document(data_file=changelog_file)
    def merge_chunks(chunks, group_size=2):
        merged_texts = []
        for i in range(0, len(chunks), group_size):
            group = chunks[i:i + group_size]
            merged = "\n\n".join(chunk.chunk for chunk in group)
            merged_texts.append(merged)
        return merged_texts
    chunks = merge_chunks(chunks)
    # formatted_chunks_per_page = group_chunks_per_page(chunks=chunks)
    # todo: withChangelog content is probably way too much.. prework needed (what pages are interesting... or only first 10 pages?)
    # todo: json format nicht ganz zuverlässig, zu csv wechseln maybe?
    print(f"generate changes from changelog {changelog_file}")
    print(f"groups count {len(chunks)}")
    extracted_changes_raw = []
    max_attempts = 3
    for chunk in chunks:
        for attempt in range(max_attempts):
            try:
                response = llm_client.generate(system_prompt=system_prompt, user_prompt=chunk)
                response = response.replace("```json", "").replace("```", "").replace("\n", "").strip()
                data = json.loads(response)
                extracted_changes_raw_page = data.get("changes", [])
                extracted_changes_raw.extend(extracted_changes_raw_page)
                break
            except Exception as e:
                print(f"failed: {e}")
                if attempt >= max_attempts - 1:
                    raise ValueError(f"Error: failed to parse llm response:\n response: {response}")
    
    extracted_changes = []
    for extracted_change_raw in extracted_changes_raw:
        page_number = -1
        if hasattr(extracted_change_raw, "page_number"):
            page_number = extracted_change_raw["page_number"]
                
        extracted_changes.append(Change(documentation=changelog_content["documentation"],
                                        version=changelog_content["version"],
                                        name=extracted_change_raw["name"],
                                        description=extracted_change_raw["description"],
                                        source_file=changelog_content["file"],
                                        source_page_nr=page_number,
                                        origin=ChangeOrigin.Extraction
                                        ))
    return extracted_changes


# todo: put into own py file
def generate_changes_from_diff(contents_to_diff) -> list[Change]:
    system_prompt = """You are an intelligent assistant tasked with creating a structured and comprehensive change log based on a list of document changes.

                        ### Your Role:
                        - Extract and structure **only meaningful content changes** such as:
                        - Added, removed, or modified **fields**, **sections**, or **values**
                        - Substantial text edits (e.g., reworded definitions, updated parameter values)
                        - **Ignore non-substantive changes**, including:
                        - Layout, formatting, style, punctuation, page numbers, font, and spacing
                        - Header capitalization, whitespace or markdown syntax changes that don’t affect meaning

                        ### Language and Style:
                        - Always return output in the **original language** of the input.
                        - Your descriptions must be **clear, complete, and precise**.
                        - If fields or parameters are added/removed/modified, **explicitly list them all.**
                        - Do not summarize or use vague terms like "etc." or "various fields"
                        - Specify: field names, their types, default values, and descriptions, if available
                        - If multiple items changed, separate them clearly

                        ### Output Rules:
                        - If **no relevant content changes** are found, return an empty list: `[]`
                        - Each meaningful change should include:
                        - `"name"`: A short, specific title summarizing the change
                        - `"description"`: A detailed explanation of exactly what changed, including field names and values if applicable
                        - `"status"`: One of `"added"`, `"removed"`, or `"modified"`

                        ### Output Format:
                        ```json
                        {
                        "changes": [
                            {
                            "name": "New Logging Fields Added",
                            "description": "Added the following fields to the logging configuration section:\n- logLevel <string> Default: 'info' – Specifies the logging verbosity.\n- logToFile <boolean> Default: false – Enables file logging.\n- logFilePath <string> – Path where the log file is written.",
                            "status": "added"
                            },
                            {
                            "name": "Removed Deprecated Parameters",
                            "description": "Removed these deprecated fields from the API config:\n- enableBetaMode <boolean>\n- useLegacyCache <boolean>",
                            "status": "removed"
                            },
                            {
                            "name": "Updated Timeout Defaults",
                            "description": "Modified default values for the following fields:\n- requestTimeout: changed from 30s to 60s\n- retryInterval: changed from 5s to 10s",
                            "status": "modified"
                            }
                        ]
                        }
                        """

    def read_file_content(filepath):
        if filepath.lower().endswith(".pdf"):
            return extract_text(filepath)
        else:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
 
    extracted_changes = []
    for content_to_diff in contents_to_diff:
        print("generate changes from diff")

        file1 = content_to_diff["file1"]
        file2 = content_to_diff["file2"]

        file1_content = read_file_content(file1)
        file2_content = read_file_content(file2)

        diff = DeepDiff(file1_content.splitlines(), file2_content.splitlines(), verbose_level=2, ignore_order=True)
        diff_json = diff.to_json(indent=2)
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = llm_client.generate(system_prompt=system_prompt, user_prompt=diff_json)
                response = response.replace("```json", "").replace("```", "").strip()
                data = json.loads(response)
                extracted_changes_raw = data.get("changes", [])
                if extracted_changes_raw:
                    extracted_changes.extend(extract_generated_changes_from_output(content_to_diff, extracted_changes_raw))
                break
            except:
                print(f"Error parsing JSON (Attempt {attempt+1}/3).")
                time.sleep(1)  # small delay for next request
    return extracted_changes

def extract_generated_changes_from_output(content_to_diff, extracted_changes_raw):    
    extracted_changes = []
    for extracted_change_raw in extracted_changes_raw:
        extracted_changes.append(Change(documentation=content_to_diff["documentation"],
                                version=content_to_diff["version2"],
                                name=extracted_change_raw["name"],
                                description=extracted_change_raw["description"],
                                source_file=content_to_diff["file2"],
                                source_page_nr=-1,
                                origin=ChangeOrigin.Differ
                                ))
    return extracted_changes

def group_chunks_per_page(chunks: list[Chunk]):
    chunks.sort(key=lambda x: x.page)
    results = []
    results_page = []
    current_page = None
    for chunk in chunks:
        if chunk.page != current_page:
            if current_page is not None:
                results.append(f"\nPage {current_page}\n" + "\n".join(content for content in results_page))
            results_page = []
            current_page = chunk.page
        results_page.append(chunk.chunk)
    if current_page and len(results_page) > 0:
        results.append(f"\nPage {current_page}\n" + "\n".join(content for content in results_page))
    return results