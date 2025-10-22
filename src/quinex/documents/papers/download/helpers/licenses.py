
# TODO: CC BY 3.0 vs 4.0
LICENSE_MAP = {
    'http://creativecommons.org/licenses/by/3.0/': "cc-by",
    'http://creativecommons.org/licenses/by-nc/3.0/': "cc-by-nc",
    'http://creativecommons.org/licenses/by-nc-nd/3.0/': "cc-by-nc-nd",
    'http://creativecommons.org/licenses/by-nc-sa/3.0/': "cc-by-nc-sa",
    'http://creativecommons.org/licenses/by-nd/3.0/': "cc-by-nd",            
    'http://creativecommons.org/licenses/by-sa/3.0/': "cc-by-sa",
    'http://creativecommons.org/licenses/by/4.0/': "cc-by",
    'http://creativecommons.org/licenses/by-nc/4.0/': "cc-by-nc",
    'http://creativecommons.org/licenses/by-nc-nd/4.0/': "cc-by-nc-nd",
    'http://creativecommons.org/licenses/by-nc-sa/4.0/': "cc-by-nc-sa",
    'http://creativecommons.org/licenses/by-nd/4.0/': "cc-by-nd",
    'http://creativecommons.org/licenses/by-sa/4.0/': "cc-by-sa",
}

def license_allows_republication(license: str):
    """Check if license allows publication."""
    if license in ["public-domain", "cc-by", "cc-by-sa", "cc-by-nc", "cc-by-nc-sa"]:
        publish_allowed = True
    elif license in ["cc-by-nc-nd", "cc-by-nd"]:
        publish_allowed = False
    elif license in [None, "publisher-specific-oa"]:
        publish_allowed = None
    else:        
        print(f"Unknown license: {license}")
        publish_allowed = None

    return publish_allowed

    
def license_allows_commercial_use(license: str):
    """Check if license allows commercial use."""
    if license in ["public-domain", "cc-by", "cc-by-nd", "cc-by-sa"]:
        commercial_use_allowed = True
    elif license in ["cc-by-nc", "cc-by-nc-nd", "cc-by-nc-sa"]:
        commercial_use_allowed = False
    elif license in [None, "publisher-specific-oa"]:
        commercial_use_allowed = None
    else:
        print(f"Unknown license: {license}")
        commercial_use_allowed = None

    return commercial_use_allowed