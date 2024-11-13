import subprocess
import time

def process_isbn_file(filename, delay_seconds=2):
    # Open isbn.txt and iterate over each line
    with open(filename, 'r', encoding='utf-8') as file:
        for line in file:
            # Strip any extra whitespace or newline characters
            isbn_value = line.strip()
            if isbn_value:  # Ensure the line isn't empty
                # Run the command: python api/index.py --isbn <isbn_value>
                command = ["python", "api/index.py", "--isbn", isbn_value, "--verbose"]
                try:
                    subprocess.run(command, check=True)
                    print(f"Successfully processed ISBN: {isbn_value}")
                    # Add a delay between requests to avoid overwhelming the servers
                    time.sleep(delay_seconds)
                except subprocess.CalledProcessError as e:
                    print(f"Error processing ISBN {isbn_value}: {e}")

if __name__ == "__main__":
    # Define the path to isbn.txt
    isbn_file_path = "isbn.txt"
    
    # Process the ISBN file
    process_isbn_file(isbn_file_path)