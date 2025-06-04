import csv
import os

RELATIVE_TEST_DIR_PATH = "../../data/test/"

def manual_score(prompt, model_name, existing_score=None):
    if existing_score in ["0", "1"]:
        print(f"Existing score: {existing_score}")

    while True:
        user_input = input(f"New score for {model_name} (1=correct, 0=incorrect, ENTER=keep): ").strip()
        if user_input == "" and existing_score in ["0", "1"]:
            return int(existing_score)
        elif user_input in ["0", "1"]:
            return int(user_input)
        else:
            print("Invalid input. Please enter 1, 0, or press ENTER to keep existing score.")

def judge_csv_file_manually(filename, model_to_score):
    file_path = os.path.join(RELATIVE_TEST_DIR_PATH, filename)

    rows = []
    with open(file_path, mode='r', encoding='utf-8', newline='') as infile:
        reader = csv.DictReader(infile, delimiter=';')
        for index, row in enumerate(reader, 1):
            print(f"\n--- [{index}] ---")
            print(f"Question:\n{row['Question']}")
            print(f"Correct Answer:\n{row['Answer']}")

            response_key = f"Response_{model_to_score}"
            score_key = f"Score_{model_to_score}"

            response = row.get(response_key, '').strip()
            existing_score = row.get(score_key, '').strip()

            print(f"\n{model_to_score} Response:\n{response}")
            new_score = manual_score(response, model_to_score, existing_score)
            row[score_key] = new_score

            rows.append(row)

    output_path = file_path.replace(".csv", f"_{model_to_score}_human_scored.csv")
    fieldnames = list(rows[0].keys())

    with open(output_path, mode='w', encoding='utf-8', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ Scored file saved to: {output_path}")

if __name__ == "__main__":
    filename = input("Enter the CSV filename (inside ../data/test/): ").strip()
    model = input("Which model do you want to score? (Baseline, GraphRAG, VDocRAG): ").strip()

    if not filename.endswith(".csv"):
        print("Error: File must be a .csv file.")
    elif model not in ["Baseline", "GraphRAG", "VDocRAG"]:
        print("Error: Invalid model selected.")
    else:
        judge_csv_file_manually(filename, model)