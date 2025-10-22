

def shorten_doi(doi: str) -> str:
    """Shorten DOI to only include the ID."""
    return doi.removeprefix('https://doi.org/').removeprefix('http://doi.org/')



