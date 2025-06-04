import os
from indexing.baseline_indexer import BaselineIndexer
from indexing.vdocrag_indexer import VDocRAGIndexer
from indexing.kg_indexer import KnowledgeGraphIndexer
from retrieval.baseline_retriever import BaselineRetriever
from retrieval.kg_retriever import KnowledgeGraphRetriever
from retrieval.vdocrag_retriever import VDocRAGRetriever
from generation.baseline_generator import BaselineGenerator
from generation.kg_generator import KnowledgeGraphGenerator
from generation.vdocrag_generator import VDocRAGGenerator
from evaluation.evaluation import evaluate
from evaluation.evaluation_llm import judge_csv_file
from util.constants import AVAILABLE_MODELS, BASELINE_MODEL, KG_MODEL, VDOCRAG_MODEL

def get_user_choice(prompt, options):
    """
    Helper function to get a choice from the user.
    """
    while True:
        print(prompt)
        for i, option in enumerate(options, 1):
            print(f"{i}. {option}")
        try:
            choice = int(input("Your choice: "))
            if 1 <= choice <= len(options):
                return options[choice - 1]
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a number.")

def get_files_from_directory(directory: str) -> list[str]:
    """
    Returns a list of absolute file paths for all files in the given directory,
    excluding hidden files (those starting with a dot).

    Args:
        directory (str): Path to the directory.

    Returns:
        list[str]: List of absolute file paths for non-hidden files.

    Raises:
        FileNotFoundError: If the specified directory does not exist.
        NotADirectoryError: If the specified path is not a directory.
    """
    if not os.path.exists(directory):
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not os.path.isdir(directory):
        raise NotADirectoryError(f"Path is not a directory: {directory}")

    file_paths = []
    for root, _, files in os.walk(directory):
        for file in files:
            # Skip hidden files (starting with dot)
            if not file.startswith('.'):
                abs_path = os.path.abspath(os.path.join(root, file))
                file_paths.append(abs_path)
    return file_paths

def run_console_mode():
    """
    Runs the application in console mode.
    """
    # Ask the user for the mode
    mode = get_user_choice("Please select the mode:", ["Indexing", "Retrieval", "Generation", "Evaluation", "Evaluation (LLM-Judge)", "Evaluation All"])

    # Ask the user for the model (if not in Evaluation mode)
    if mode != "Evaluation" and mode != "Evaluation (LLM-Judge)" and mode != "Evaluation All":
        model_choice = get_user_choice("Please select the model:", AVAILABLE_MODELS)
        # Initialize components based on the selected model
        if model_choice == BASELINE_MODEL:
            indexer = BaselineIndexer()
            retriever = BaselineRetriever()
            generator = BaselineGenerator()
        elif model_choice == KG_MODEL:
            indexer = KnowledgeGraphIndexer()
            retriever = KnowledgeGraphRetriever()
            generator = KnowledgeGraphGenerator()
        else:
            indexer = VDocRAGIndexer()
            retriever = VDocRAGRetriever()
            generator = VDocRAGGenerator()

    # Execute the selected mode
    if mode == "Indexing":
        # Get absolute file paths from the ../data/raw/ directory
        raw_data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
        file_paths = get_files_from_directory(raw_data_dir)
        
        # Pass the list of absolute file paths to the indexer
        indexer.index_data(file_paths)
    elif mode == "Retrieval":
        query = input("Enter your query: ")
        retrieved_data = retriever.retrieve(query)
        print(f"Retrieved Data: {retrieved_data}")
    elif mode == "Generation":
        while True:  # Loop to allow multiple questions
            query = input("\nEnter your question (or type 'quit' to quit): ")
            if query.lower() == 'quit':  # Exit condition
                print("Exiting the question loop. Goodbye!")
                break
            retrieved_data = retriever.retrieve(query)  # First retrieve relevant data
            response = generator.generate(retrieved_data, query)  # Generate response
            print(response)
    elif mode == "Evaluation":
        # Default input file
        default_input_file = "evaluation_set.csv"
        input_file = input(f"Enter the filename of the evaluation set CSV file located in data/test/ (default: {default_input_file}): ") or default_input_file

        # Ask for model choice
        model_choice = get_user_choice("Please select the model for evaluation:", [BASELINE_MODEL, KG_MODEL, VDOCRAG_MODEL, "All"])

        # Default output file based on model choice
        default_output_file = f"evaluation_out_{model_choice}.csv"
        output_file = input(f"Enter the filename to save the evaluation results in data/test/ (default: {default_output_file}): ") or default_output_file

        # Run evaluation
        evaluate(input_file, output_file, model_choice)
    elif mode == "Evaluation (LLM-Judge)":
        # Default input file
        default_input_file = "evaluation_out_All.csv"
        input_file = input(f"Enter the filename of the evaluation set CSV file located in data/test/ (default: {default_input_file}): ") or default_input_file
        judge_csv_file(input_file)
    elif mode == "Evaluation All":
        default_input_file = "evaluation_set.csv"
        input_file = input(f"Enter the filename of the evaluation set CSV file located in data/test/ (default: {default_input_file}): ") or default_input_file
        # Ask for model choice
        model_choice = get_user_choice("Please select the model for evaluation:", [BASELINE_MODEL, KG_MODEL, VDOCRAG_MODEL, "All"])
         # Default output file based on model choice
        default_output_file = f"evaluation_out_{model_choice}.csv"
        output_file = input(f"Enter the filename to save the evaluation results in data/test/ (default: {default_output_file}): ") or default_output_file
        evaluate(input_file, output_file, model_choice)
        judge_csv_file(output_file)

def main():
    run_console_mode()

if __name__ == "__main__":
    main()