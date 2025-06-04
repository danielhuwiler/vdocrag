import csv
import openai
from dotenv import load_dotenv
load_dotenv()

RELATIVE_TEST_DIR_PATH = "../data/test/"

EVALUATION_LLM = "gpt-4.1"

SYSTEM_PROMPT = """You are a strict but fair evaluation judge for AI-generated answers.
Your task is to compare the model’s answer to the reference answer, and decide whether the model’s answer is factually correct (1) or incorrect (0).
		•	The reference answer represents the factual truth.
	•	The model’s answer must include all key facts and meaning from the reference.
	•	It is acceptable if the model adds extra relevant details, as long as the reference content is accurately and clearly expressed.
	•	The answer must be semantically correct, complete, and not contradict the reference.
	•	Slight rewording is allowed if the truth of the reference answer remains fully preserved.
	•	Do not give credit for partial correctness or vague overlap — the model must clearly and truthfully answer the original question in line with the reference.

	Only output the digit 1 or 0. Do not explain your reasoning.
"""

client = openai.OpenAI()

def llm_score(question, reference_answer, model_answer):
    if model_answer is None or model_answer == "":
        return 0

    user_prompt = f"""Question: {question}
Reference Answer: {reference_answer}
Model Answer: {model_answer}
Score:"""
    try:
        response = openai.responses.create(
            model=EVALUATION_LLM,
            instructions=SYSTEM_PROMPT,
            input=user_prompt,
            temperature=0,
            max_output_tokens=16,
        )
        score = response.output[0].content[0].text.strip()
        print(f"llm judge score {score}")
        return int(score)
    except Exception as e:
        print("Error during scoring:", e)
        return 0

def judge_csv_file(filename):
    file_path = f"{RELATIVE_TEST_DIR_PATH}{filename}"
    rows = []
    with open(file_path, mode='r', encoding='utf-8', newline='') as infile:
        reader = csv.DictReader(infile, delimiter=';')
        for row in reader:
            question = row['Question']
            answer = row['Answer']

            row['Score_Baseline'] = llm_score(question, answer, row.get('Response_Baseline', ''))
            row['Score_GraphRAG'] = llm_score(question, answer, row.get('Response_GraphRAG', ''))
            row['Score_VDocRAG'] = llm_score(question, answer, row.get('Response_VDocRAG', ''))

            rows.append(row)

    # Add new fields to the output
    fieldnames = list(rows[0].keys())

    # Write results to a new CSV file
    output_path = file_path.replace('.csv', '_scored.csv')
    with open(output_path, mode='w', encoding='utf-8', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(rows)

    print(f"Scored file saved to: {output_path}")