def count_words_in_file(filename):
    """
    Counts the total number of words in a given file.

    Args:
        filename (str): The name of the file to read from.

    Returns:
        int: The total number of words in the file.
    """
    try:
        with open(filename, 'r') as file:
            text = file.read()
            words = text.split()
            return len(words)
    except FileNotFoundError:
        print(f"File '{filename}' not found.")
        return None

def main():
    filename = input("Enter the name of the file: ")
    word_count = count_words_in_file(filename)
    if word_count is not None:
        print(f"The file '{filename}' contains {word_count} words.")

if __name__ == "__main__":
    main()