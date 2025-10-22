import os
import re
import json
import time
import requests
from pathlib import Path


# TODO: Swith to geolocator?
# geolocator = Nominatim(user_agent="Python script to normalize location names (email address here)")
# location = geolocator.geocode("European-Mediterranean region")    

NOMINATIM_ENDPOINT = "https://nominatim.openstreetmap.org/search"

# Get email address for header in Nominatim API usage.
email = os.getenv("EMAIL_ADDRESS") 
if email is None:
    raise ValueError("Please set the EMAIL_ADDRESS environment variable to a valid email address for Nominatim API usage.")
else:
    # TODO: Validate email format
    # ...
    # Provide a valid HTTP Referer or User-Agent identifying the application by providing an email address.
    headers = {
        "User-Agent": "Python script to normalize location names",
        "From": email
    }

# Load static resources
STATIC_RESOURCES_DIR = Path(__file__).resolve().parent / "static_resources"
country_codes_mapping_path = STATIC_RESOURCES_DIR / "country_codes_mapping.json"
with open(country_codes_mapping_path, "r") as f:
    COUNTRY_CODES_MAPPING = json.load(f)["data"]

spatial_scope_normalization_mapping_path = STATIC_RESOURCES_DIR / "spatial_scope_normalization_mapping.json"
with open(spatial_scope_normalization_mapping_path, "r") as f:
    SPATIAL_SCOPE_NORMALIZATION_MAPPING = json.load(f)

mapping_size = len(SPATIAL_SCOPE_NORMALIZATION_MAPPING)
print("Number of spatial scope normalization mappings:", mapping_size)

# Normalize spatial scope using the Nominatim API (nominatim.openstreetmap.org)    
layer="address" 
accept_language = ["en"]
addressdetails = "1"
limit = "3"
COUNTRY_URL = NOMINATIM_ENDPOINT + f"?country={{spatial_scope_str}}&layer={layer}&addressdetails={addressdetails}&format=json&accept-language={','.join(accept_language)}&limit={limit}"
STATE_URL = COUNTRY_URL.replace("?country=", "?state=") 
COUNTY_URL = COUNTRY_URL.replace("?country=", "?county=")
CITY_URL = COUNTRY_URL.replace("?country=", "?city=")
FREE_FORM_URL = COUNTRY_URL.replace("?country=", "?q=").replace(f"&layer={layer}", "")

REGIONS = list(set([r["region"].lower() for r in COUNTRY_CODES_MAPPING if r["region"] != "" and r["region"] != None]))
SUBREGIONS = list(set([r["sub-region"].lower() for r in COUNTRY_CODES_MAPPING if r["sub-region"] != "" and r["sub-region"] != None]))
COUNTRIES = list(set([r["name"].lower() for r in COUNTRY_CODES_MAPPING if r["name"] != "" and r["name"] != None]))

# Sort from longest to shortest
REGIONS.sort(key=len, reverse=True)
SUBREGIONS.sort(key=len, reverse=True)
COUNTRIES.sort(key=len, reverse=True)

with open(STATIC_RESOURCES_DIR / "adjective_to_location.json", "r") as f:
    adj_to_location = json.load(f)

def clean_spatial_scope(spatial_scope):
    # TODO: split into individual locations e.g. "Denmark, Germany, Ireland, Norway, Sweden, United States) and the European Union"                
    garbage_prefixes = ["between", "the", "in"]
    garbage_substrings = ["located",  "location", "locations", "part of", "border between", "near", "typical", "airport", "rural area", "urban area", "carefully chosen locations", "hilly region", "rural areas", "provincial-level", "remote", "remote areas", "urban areas", "isolated community", "isolated communities", "along", "the", "in", "several", "multiple", "various", "different", "southernmost", "northernmost", "westernmost", "easternmost"]
    trash_keywords = ["in all other countries investigated", "real physical", "north", "selected sites next to mediterranean", "mediterranean climate", "jurisdictions excluding asia"]
    global_keywords = ["worldwide", "global", "world", "international"]
    direction_keywords = ["northern", "southern", "western", "eastern", "central"]
    region_keywords = list(set(["region", "province", "mega cities", "provincial-level divisions", "exclusive economic zone", "eez", "coastline", "offshore locations" "sites", "state", "city", "country", "countries", "area", "areas", "community", "communities", "district", "districts", "division", "divisions", "region", "regions", "province", "provinces", "state", "states", "city", "cities", "town", "towns", "village", "villages", "municipality", "municipalities", "county", "counties", "prefecture", "prefectures", "department", "departments", "territory", "territories", "island", "islands", "archipelago", "archipelagos", "peninsula", "peninsulas", "atoll", "atolls", "reef", "reefs", "cay", "cays", "cayes", "key", "keys", "islet", "islets", "rock", "rocks", "mountain", "mountains", "hill", "hills", "valley", "valleys", "plateau", "plateaus", "plain", "plains", "desert", "deserts", "oasis", "oases", "forest", "forests", "jungle", "jungles", "savannah", "savannahs", "grassland", "grasslands", "wetland", "wetlands", "swamp", "swamps", "marsh", "marshes", "bog", "bogs", "fen", "fens", "moor", "moors", "heath", "heaths", "tundra", "tundras", "taiga", "taigas", "rainforest", "rainforests", "temperate forest", "temperate forests", "boreal forest", "boreal forests", "tropical forest", "tropical forests", "coniferous forest", "coniferous forests", "deciduous forest", "deciduous forests", "mixed forest", "mixed forests", "woodland", "woodlands", "scrubland", "scrublands", "shrubland", "shrublands", "steppe", "steppes", "prairie", "prairies", "pampas", "pampas", "savanna"]))        
    number_keywords = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
    number_keywords += ["eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
    number_keywords += ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred"]

    spatial_scope_clean = spatial_scope.lower().strip()
    spatial_scope_clean = spatial_scope_clean.replace("’s", "").replace("'s", "").replace("’ ", " ").replace("' ", " ")
    spatial_scope_clean = spatial_scope_clean.replace(" (", ", ")
    spatial_scope_clean = spatial_scope_clean.replace(")", "")
    
    if spatial_scope in trash_keywords:
        return ""                
    elif spatial_scope in global_keywords:        
        return "worldwide"            
    else:        
        garbage_prefixes.sort(key=len, reverse=True)
        
        for prefix in garbage_prefixes:
            spatial_scope_clean = spatial_scope_clean.removeprefix(prefix + " ")

        # Remove directions        
        spatial_scope_clean = re.sub(r"\b(" + "|".join(direction_keywords) + r")\b", "", spatial_scope_clean)
        
        # Remove all digits
        spatial_scope_clean = re.sub(r"\d+", "", spatial_scope_clean)

        # Remove number words        
        spatial_scope_clean = re.sub(r"\b(" + "|".join(number_keywords) + r")\b", "", spatial_scope_clean)                    

        # Remove garbage substrings        
        garbage_substrings += region_keywords
        garbage_substrings.sort(key=len, reverse=True)
        for substring in garbage_substrings:
            # Check if the substring is in the spatial scope
            if substring in spatial_scope_clean:                            
                spatial_scope_clean = re.sub(r"\b" + re.escape(substring) + r"\b", "", spatial_scope_clean)

        # Expand abbreviations
        spatial_scope_clean = spatial_scope_clean.replace("u.s.", "united states").replace("u.k.", "united kingdom").replace("u.a.e.", "united arab emirates")

        # Remove multiple whitespaces
        spatial_scope_clean = re.sub(r"\s\s+", ", ", spatial_scope_clean)                                    

        # Remove leading and trailing whitespaces
        spatial_scope_clean = spatial_scope_clean.strip()

        # Remove reptitive commas
        spatial_scope_clean = re.sub(r",+", ",", spatial_scope_clean)

        spatial_scope_clean = spatial_scope_clean.replace(" at, ", ", ").replace(" in, ", ", ").replace(" on, ", ", ").replace(", of ", ", ").replace(", in ", ", ").replace(", on ", ", ").replace(", at ", ", ").replace(", the ", ", ")
        spatial_scope_clean = spatial_scope_clean.replace(" and, ", " and ")

        # Remove leading and trailing commas            
        spatial_scope_clean = spatial_scope_clean.removeprefix(", ").removesuffix(",") 

        # Remove directions with comma, e.g., in "nicosia, central, cyprus" or "southern, uttar pradesh, india"
        pattern = r"\b(" + "|".join(direction_keywords) + r"),\s?"
        spatial_scope_clean = re.sub(pattern, "", spatial_scope_clean) 

        # Map spatial scopes that could not be normalized with hard-coded dict
        hard_coded_mapping = {            
            "three egyptian ports": "egypt",        
            "abroad brazil": "brazil",
            "bay of bourgneuf on, french atlantic coast": "pays de retz, france",      
            "australian coastal": "australia",
            "hot springs cove, remote canadian": "hot springs cove, canada",                        
        }

        if spatial_scope_clean in hard_coded_mapping:
            spatial_scope_clean = hard_coded_mapping[spatial_scope_clean]        
        
        # European to Europe, French to France, etc.
        if spatial_scope_clean in adj_to_location:
            spatial_scope_clean = adj_to_location[spatial_scope_clean]  

        spatial_scope_clean = spatial_scope_clean.replace(" , ", ", ")
        
        if spatial_scope_clean in trash_keywords:
            return ""

        return spatial_scope_clean

assert clean_spatial_scope("in several European countries") == "europe"
assert clean_spatial_scope("in South Australia") == "south australia"
assert clean_spatial_scope("south spain, alboran sea, sardinia, sicily and malta, and south adriati") == "south spain, alboran sea, sardinia, sicily and malta, and south adriati"


def save_spatial_scope_normalization_mapping():   
    new_mapping_size = len(SPATIAL_SCOPE_NORMALIZATION_MAPPING)        
    print("Number of added spatial scope normalization mappings:", new_mapping_size-mapping_size)
    print(f"Saving spatial scope normalization mapping to {spatial_scope_normalization_mapping_path}")
    with open(spatial_scope_normalization_mapping_path, "w") as f:
        json.dump(SPATIAL_SCOPE_NORMALIZATION_MAPPING, f, indent=4, ensure_ascii=False) 

def get_location_from_nominatim(location_str, nice=3, verbose=False):
        # Request the API to check spatial scope is a COUNTRY
        api_request = COUNTRY_URL.format(spatial_scope_str=location_str)
        time.sleep(1*max(1, nice)) # Sleep for minimum of 1 second to avoid rate limiting
        if verbose:  
            print("Requesting Nominatim API with spatial scope: 📍", location_str)

        response = requests.get(api_request, headers=headers)

        result = []
        if response.status_code == 200:
            result = response.json()

        if len(result) == 0:
            # Request the API to check spatial scope is a STATE
            api_request = STATE_URL.format(spatial_scope_str=location_str)
            time.sleep(1*max(1, nice))
            response = requests.get(api_request, headers=headers)
            if response.status_code == 200:
                result = response.json()

        if len(result) == 0:
            # Request the API to check spatial scope is a COUNTY
            api_request = COUNTY_URL.format(spatial_scope_str=location_str)
            time.sleep(1*max(1, nice))
            response = requests.get(api_request, headers=headers)
            if response.status_code == 200:
                result = response.json()

        if len(result) == 0:
            # Request the API to check spatial scope is a natural feature like a mountain, lake, etc.
            # Somehow when setting layer=natural, the "north sea" etc. are not found. Therefore, use free_from_url.
            api_request = FREE_FORM_URL.format(spatial_scope_str=location_str)
            time.sleep(1*max(1, nice))
            response = requests.get(api_request, headers=headers)
            if response.status_code == 200:
                result = response.json()
            
            # Remove results that have a road associated with them
            result = [r for r in result if "road" not in r["address"] and 'town' not in r["address"]]

        if len(result) == 0:
            # Request the API to check spatial scope is a CITY
            api_request = CITY_URL.format(spatial_scope_str=location_str)
            time.sleep(1*max(1, nice))
            response = requests.get(api_request, headers=headers)
            if response.status_code == 200:
                result = response.json()

        if len(result) == 0:
            # Check if spatial scope includes a country, region, or subregion name.
            location_substr = None
            for country in COUNTRIES:
                if country in location_str:
                    location_substr = country
                    break

            if location_substr == None:
                for subregion in SUBREGIONS:
                    if subregion in location_str:
                        location_substr = subregion
                        break
            
            if location_substr == None:
                for region in REGIONS:
                    if region in location_str:
                        location_substr = region
                        break

            if location_substr != None:
                api_request = FREE_FORM_URL.format(spatial_scope_str=location_substr)
                time.sleep(1*max(1, nice))
                response = requests.get(api_request, headers=headers)
                if response.status_code == 200:
                    result = response.json()

        if len(result) == 1:
            normalized_location = result[0]
        elif len(result) > 1: 
            # Take most abstract result based on the bounding box information,
            # e.g., Scandinavia as a subregion of Northern Europe instead of a city in Wisconsin.
            bb_area = [abs(float(r["boundingbox"][1]) - float(r["boundingbox"][0])) * abs(float(r["boundingbox"][3]) - float(r["boundingbox"][2])) for r in result]
            normalized_location = result[bb_area.index(max(bb_area))]
        else:
            normalized_location = None

        if verbose:     
            if normalized_location != None:
                print("Result:", normalized_location["display_name"])
            else:
                print("No result found.")

        return normalized_location


def normalize_spatial_scope(qclaim, extend_geo_normalization_cache=True, nice=3):
    """Normalize the spatial scope to a common format."""

    spatial_scope = qclaim["qualifiers"]["spatial_scope"]["text"]

    # No spatial scope, nothing to do.
    if len(spatial_scope.strip()) == 0:
        normalized_spatial_scope = None
    else:
        # Clean spatial scope string.
        spatial_scope_clean = clean_spatial_scope(spatial_scope)

        # Normalize spatial scope.
        normalized_spatial_scope = SPATIAL_SCOPE_NORMALIZATION_MAPPING.get(spatial_scope_clean)
        if normalized_spatial_scope == None and extend_geo_normalization_cache \
            and not spatial_scope_clean in ["", "worldwide", "internationally", "international"] \
            and not spatial_scope_clean in SPATIAL_SCOPE_NORMALIZATION_MAPPING \
            and not " and " in spatial_scope_clean \
            and not " and, " in spatial_scope_clean:
                    
            # TODO: If "brack city, libya" fails at least "libya" should be returned
            # TODO: If multiple regions are given, split them and request them individually

            # Get normalized location from Nominatim API.
            try:
                normalized_spatial_scope = get_location_from_nominatim(spatial_scope_clean, nice=nice)
            except Exception as e:
                print("Error:", e)
                if spatial_scope_clean in SPATIAL_SCOPE_NORMALIZATION_MAPPING:
                    normalized_spatial_scope = SPATIAL_SCOPE_NORMALIZATION_MAPPING[spatial_scope_clean]
                else:
                    normalized_spatial_scope = None

            SPATIAL_SCOPE_NORMALIZATION_MAPPING[spatial_scope_clean] = normalized_spatial_scope

    # Transform normalized spatial scope to a output format.
    clean_normalized_spatial_scope = {}
    if normalized_spatial_scope == None:
        clean_normalized_spatial_scope["country"] = None
        clean_normalized_spatial_scope["country_code"] = None
        clean_normalized_spatial_scope["latitude"] = None
        clean_normalized_spatial_scope["longitude"] = None
        clean_normalized_spatial_scope["osm_place_id"] = None
    else: 
        clean_normalized_spatial_scope["country"] = normalized_spatial_scope.get("address", {}).get("country")
        clean_normalized_spatial_scope["country_code"] = normalized_spatial_scope.get("address", {}).get("country_code")
        clean_normalized_spatial_scope["latitude"] = normalized_spatial_scope.get("lat")
        clean_normalized_spatial_scope["longitude"] = normalized_spatial_scope.get("lon")
        clean_normalized_spatial_scope["osm_place_id"] = normalized_spatial_scope.get("place_id")

    return clean_normalized_spatial_scope 

