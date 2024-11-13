import os
import json
import csv
import argparse
from datetime import datetime

def process_json_files(directory, output_file):
    # Define headers and set up a list to hold processed data rows
    headers = [
        "ISBN", 
        "ARK_TITLE", "ARK_PRICE", "ARK_URL", 
        "NORLI_TITLE", "NORLI_PRICE", "NORLI_URL",
        "ADLIBRIS_TITLE", "ADLIBRIS_PRICE", "ADLIBRIS_URL",
        "TIMESTAMP"
    ]
    data_rows = []

    # Loop through JSON files in the specified directory
    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            file_path = os.path.join(directory, filename)
            with open(file_path, 'r', encoding='utf-8') as file:
                try:
                    # Load JSON data and extract values with defaults if missing
                    data = json.load(file)
                    isbn = data.get("ISBN", "")
                    timestamp = data.get("TIMESTAMP", "")

                    # Get site data with defaults
                    sites = data.get("SITES", {})

                    # ARK details
                    ark_data = sites.get("ark.no", {})
                    ark_title = ark_data.get("TITLE", "")
                    ark_price = ark_data.get("PRICE", "")
                    ark_url = ark_data.get("PRODUCT_URL", "")

                    # NORLI details
                    norli_data = sites.get("norli.no", {})
                    norli_title = norli_data.get("TITLE", "")
                    norli_price = norli_data.get("PRICE", "")
                    norli_url = norli_data.get("PRODUCT_URL", "")

                    # ADLIBRIS details
                    adlibris_data = sites.get("adlibris.no", {})
                    adlibris_title = adlibris_data.get("TITLE", "")
                    adlibris_price = adlibris_data.get("PRICE", "")
                    adlibris_url = adlibris_data.get("PRODUCT_URL", "")

                    # Append extracted data as a new row
                    data_rows.append([
                        isbn, 
                        ark_title, ark_price, ark_url,
                        norli_title, norli_price, norli_url,
                        adlibris_title, adlibris_price, adlibris_url,
                        timestamp
                    ])
                except json.JSONDecodeError:
                    print(f"Error decoding JSON in file: {filename}")
                except KeyError as e:
                    print(f"Missing key {e} in file: {filename}")

    # Write data rows to a TSV file
    with open(output_file, 'w', newline='', encoding='utf-8') as tsv_file:
        writer = csv.writer(tsv_file, delimiter='\t')
        writer.writerow(headers)
        writer.writerows(data_rows)

    print(f"Data successfully written to {output_file}")

# Set up argument parsing for optional filename input
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process JSON files and export to TSV format.")
    parser.add_argument("--export", type=str, default="entries.tsv", help="Output file name for the TSV file")
    args = parser.parse_args()

    # Directory containing JSON files
    json_directory = "./isbn"
    output_filename = args.export

    # Process files and write to output
    process_json_files(json_directory, output_filename)