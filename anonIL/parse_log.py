import re
import argparse

def parse_mpc_log(file_path):
    """
    Parses a log file to extract and sum up the time taken for each MPC summation.

    This function reads a file, finds all occurrences of the pattern "Time = X seconds",
    prints the time for each occurrence (which corresponds to an iteration/level),
    and finally prints the total sum of these times.

    Args:
        file_path (str): The path to the log file to be parsed.
    """
    try:
        # Open and read the entire content of the log file.
        with open(file_path, 'r') as f:
            log_content = f.read()

        # Use a regular expression to find all lines that match the time reporting format.
        # This will return a list of all matching time values as strings.
        # The regex looks for "Time = " followed by a number (integer or float) and " seconds".
        time_strings = re.findall(r"Time = ([\d.]+) seconds", log_content)

        # Check if any time values were found.
        if not time_strings:
            print(f"No 'Time =' entries found in the log file: {file_path}")
            return

        # Convert the list of time strings to a list of floats.
        time_values = [float(t) for t in time_strings]

        # --- Output the results ---

        print("--- MPC Summation Times Per Level ---")
        # Enumerate through the list of times to print each one with its level number.
        for i, time_val in enumerate(time_values):
            # Using f-string for formatted output. '.6f' formats the float to 6 decimal places.
            print(f"  Level {i} Time: {time_val:.6f} seconds")

        # Calculate the total time by summing all the extracted time values.
        total_time = sum(time_values)

        print("\n--- Total Execution Time ---")
        print(f"Total MPC summation time: {total_time:.6f} seconds")

    except FileNotFoundError:
        print(f"Error: The file at the specified path was not found: {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    # Set up an argument parser to handle command-line arguments.
    # This makes the script more flexible, allowing the user to specify the log file path.
    parser = argparse.ArgumentParser(description="Parse an MPC log file to extract and sum execution times.")
    
    # Add an argument for the file path.
    parser.add_argument(
        "file_path", 
        type=str, 
        nargs='?', 
        default='./Logs/mpc_run.log',
        help="The path to the log file. Defaults to './Logs/mpc_run.log' if not provided."
    )
    
    # Parse the arguments provided by the user.
    args = parser.parse_args()
    
    # Call the main function with the provided file path.
    parse_mpc_log(args.file_path)
