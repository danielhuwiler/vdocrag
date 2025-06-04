import os

class BaseRetriever:
    def retrieve(self, query: str):
        """
        Retrieves relevant data based on the query.

        Args:
            query: The user's question.

        Returns:
            A RetrievedData object containing the chunks and source files.
        """
        raise NotImplementedError("Subclasses must implement this method.")
    
class RetrievedData:
    def __init__(self, chunks, page_nrs=None, source_files=None, versions=None):
        """
        Represents the data retrieved by the retriever.

        Args:
            chunks (list of str): The retrieved data chunks.
            source_files (list of str): The corresponding source filenames.
        """
        self.chunks = chunks
        self.page_nrs = page_nrs
        self.source_files = source_files
        self.versions = versions
    
    def source_files_with_page_nr(self):
        """
        Combines source filenames with their corresponding page numbers.
        
        Returns:
            list of str: List of strings in format "filename (Page X)".
                        If page number is -1, returns just "filename".
        """
        combined = []
        for file, page in zip(self.source_files, self.page_nrs):
            filename = os.path.basename(file)
            if page != -1:
                combined.append(f"'{filename}' (Page {page})")
            else:
                combined.append(filename)
        return combined

    def __str__(self):
        """Returns a string representation of the retrieved data."""
        result = []
        if self.page_nrs is None or self.source_files is None:
            return self.chunks
    
        for chunk, page_nr, source_file, version in zip(self.chunks, self.page_nrs, self.source_files, self.versions or [None]*len(self.chunks)):
            # Extract the filename from the absolute path
            filename = os.path.basename(source_file)
            result_str = f"Source File: {filename} (Page {page_nr})\nChunk: {chunk}\n"
            if version:
                result_str += f"Version: {version}\n"
            result.append(result_str)
        return "\n".join(result)