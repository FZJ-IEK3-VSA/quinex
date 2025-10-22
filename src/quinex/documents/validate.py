import os
from requests.models import Response
from wasabi import msg



def has_valid_extension(file_path: str, extensions: list[str]=["json"]) -> bool:
    """Check if file has valid extension. Matching is case-insensitive.

    Args:
        file_path (str): Path to file.
        extension (list[str], optional): File extension. Defaults to "json".
    
    Returns:
        bool: True if file has valid extension, else False.
    """

    if type(file_path) != str:
        # File path is not a string.        
        raise TypeError(f"file_path must be a string, but is {type(file_path)}")
    elif any(file_path.lower().endswith(f'.{extension.lower()}') for extension in extensions):        
        return True
    else:
        # File path has wrong extension.
        return False


def is_valid_tei(tei_path):
    """Check if TEI file is valid."""
    
    if not has_valid_extension(tei_path, extensions=["tei.xml"]):
        msg.fail(f"tei-file has wrong extension for {tei_path}")
        return False
    elif not os.path.isfile(tei_path):        
        msg.fail(f"tei-file not found for {tei_path}")
        return False
    else:
        # Read TEI file.        
        with open(tei_path, "r", encoding="utf8") as f:
            tei_content = f.read()

        # Check if TEI content is empty or an error message.
        if tei_content in ["",
            "[NO_BLOCKS] PDF parsing resulted in empty content",
            "[BAD_INPUT_DATA] PDF to XML conversion failed with error code: 1",
        ]:
            msg.fail(f"tei-file is empty for {tei_path}")
            return False
        else:            
            return True
        

def content_is_pdf(response: Response) -> bool:
    # Check if response content is PDF based on headers or content.
    return response.headers["Content-Type"] == "application/pdf" or response.content[0:5] == b'%PDF-'