import csv
from retrieval.baseline_retriever import BaselineRetriever
from retrieval.vdocrag_retriever import VDocRAGRetriever
from retrieval.kg_retriever import KnowledgeGraphRetriever
from generation.baseline_generator import BaselineGenerator
from generation.vdocrag_generator import VDocRAGGenerator
from generation.kg_generator import KnowledgeGraphGenerator
from indexing.kg_indexer import KnowledgeGraphIndexer
from util.constants import AVAILABLE_MODELS, BASELINE_MODEL, KG_MODEL
import os

RELATIVE_TEST_DIR_PATH = "../data/test/"

def load_evaluation_set(file_name):
    """
    Loads the evaluation data from the CSV file.

    Args:
        file_name (str): Name of the CSV file.

    Returns:
        list of dict: A list of dictionaries containing the evaluation data.
    """
    evaluation_data = []
    with open(f"{RELATIVE_TEST_DIR_PATH}{file_name}", mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file, delimiter=',')
        for row in reader:
            evaluation_data.append(row)
    return evaluation_data

def generate_answers(evaluation_data, retriever, generator, model):
    """
    Generates answers for each query in the evaluation data.

    Args:
        evaluation_data (list of dict): The evaluation data.
        retriever: The retriever used to fetch relevant data.
        generator: The generator used to create answers.

    Returns:
        list of dict: The evaluation data with generated answers and source files.
    """
    print(f"start evaluation of {model}")
    limit = len(evaluation_data)
    for i, row in enumerate(evaluation_data):
        query = row['Question']
        retrieved_data = retriever.retrieve(query)  # Retrieve relevant data
        response = generator.generate(retrieved_data, query)  # Generate answer
        row[f'Response_{model}'] = response.answer
        print(f"{i+1}/{limit}")
    return evaluation_data

def save_results_for_column(evaluation_data, output_filename, model_column):
    """
    Saves or updates the results in the CSV file, updating only the given model column.

    Args:
        evaluation_data (list of dict): The evaluation data with generated answers.
        output_filename (str): Name of the output CSV file.
        model_column (str): The column name to update (e.g. 'Response_Baseline').
    """
    output_path = f"{RELATIVE_TEST_DIR_PATH}{output_filename}"
    existing_data = []

    if os.path.exists(output_path):
        with open(output_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file, delimiter=',')
            existing_data = list(reader)

    question_to_row = {row['Question']: row for row in existing_data} if existing_data else {}

    for new_row in evaluation_data:
        question = new_row['Question']
        if question in question_to_row:
            question_to_row[question][model_column] = new_row.get(model_column, "")
        else:
            question_to_row[question] = new_row

    merged_rows = list(question_to_row.values())

    all_fieldnames = set()
    for row in merged_rows:
        all_fieldnames.update(row.keys())

    with open(output_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=all_fieldnames, delimiter=';', extrasaction='ignore')
        writer.writeheader()
        writer.writerows(merged_rows)

def evaluate(input_filename, output_filename, model_choice):
    evaluation_data = load_evaluation_set(input_filename)
    
    if model_choice == "All":
        for model in AVAILABLE_MODELS:
            updated = generate(model, evaluation_data)
            save_results_for_column(updated, output_filename, model_column=f"Response_{model}")
    else:
        updated = generate(model_choice, evaluation_data)
        save_results_for_column(updated, output_filename, model_column=f"Response_{model_choice}")

    print(f"Evaluation results saved to {output_filename}")
        
def generate(model_choice, evaluation_data):
    if model_choice == BASELINE_MODEL:
        retriever = BaselineRetriever()
        generator = BaselineGenerator()
    elif model_choice == KG_MODEL:
        retriever = KnowledgeGraphRetriever()
        generator = KnowledgeGraphGenerator()
    else:
        retriever = VDocRAGRetriever()
        generator = VDocRAGGenerator()

    # Generate answers for each query
    return generate_answers(evaluation_data, retriever, generator, model_choice)
    