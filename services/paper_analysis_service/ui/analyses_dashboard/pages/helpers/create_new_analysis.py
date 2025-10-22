import re
import requests
from datetime import datetime                
import pandas as pd
from werkzeug.utils import secure_filename
import streamlit as st
from .get_config import API_BASE_URL



CURRENT_YEAR = datetime.now().year  
DOI_PATTERN = re.compile(r"^(https?://doi.org/)?10\.\d{4,9}/[\-\._;\(\)/:<>a-zA-Z0-9]+$")

def get_paper_display_name(title, year=None, doi="", highlight=True, highlight_color="blue"):
    if year and doi:
        display_name = f"_{title}_ ({year}). doi:{doi}"
    elif year:    
        display_name = f"_{title}_ ({year})"
    else:    
        display_name = f"_{title}_"
    
    if highlight:
        display_name = f":{highlight_color}-background[{display_name}]"
    
    return display_name


def validate_analysis_name(analysis_name, verbose=True):
    """
    Validate the analysis name. It must be not empty, a valid filename, and not already taken.
    """    
    valid = False
    if analysis_name == "":
        if verbose:
            st.error("Please enter an analysis name.")        
    elif analysis_name != secure_filename(analysis_name):
        if verbose:
            st.error("The analysis name must be a valid filename. Please only use letters, numbers, and underscores.")
    else:
        # Check if the analysis name is already taken.            
        endpoint = API_BASE_URL + f"bulk_analysis/{analysis_name}"
        response = requests.get(endpoint)
        if response.status_code != 200:
            valid = True
        
    return valid


def get_valid_placeholder(add_date=False):
    """
    Get a valid placeholder for the analysis name.
    """

    # Test some default placeholders.
    current_date = datetime.now().strftime("%Y-%m-%d")
    technology_options = ["carbon_capture_technologies", "deap_sea_mining", "direct_air_capture", "energy_storage", "hydrogen_technologies", "nuclear_fusion", "nuclear_power", "solar_power", "wind_power"]
    is_valid = False
    for option in technology_options:
        
        if add_date:
            placeholder_candidate = f"{option}_{current_date}"
        else:
            placeholder_candidate = option
        
        is_valid = validate_analysis_name(placeholder_candidate, verbose=False)
        if is_valid:
            break
            
    # If no success yet, iterate until a valid placeholder is found.
    if not is_valid:                        
        for i in range(100):
            
            if add_date:
                placeholder_candidate = f"my_analysis_{i}_{current_date}"
            else:
                placeholder_candidate = f"my_analysis_{i}"

            is_valid = validate_analysis_name(placeholder_candidate, verbose=False)
            if is_valid:
                break

        if not is_valid:
            st.error("Could not find a valid placeholder for the analysis name. Please contact the admin.")

    return placeholder_candidate
    

def get_analysis_name(analyis_name_topic_str_placeholder="my_analysis_about_solar_power"):
    """
    Get the analysis name from the user and validate it. The placeholder is assumed to be valid.
    """
    st.markdown("##### 1. Choose analysis name")            
    analyis_name_topic_str = st.text_input("Choose a name for the analysis and **press enter**.", analyis_name_topic_str_placeholder, disabled=st.session_state.processing)
    user = st.text_input("Enter your user name and **press enter**. It will be attached to the analysis name together with the current date.", "j-doe", disabled=st.session_state.processing)
    today = datetime.now().strftime("%Y-%m-%d")
    analysis_name = secure_filename(analyis_name_topic_str + "_" + user.replace(".","-") + "_" + today)    

    st.write(f"The full analysis name is **`{analysis_name}`** and will be used to identify your analysis. **Please remember it, as it will be needed to access the analysis later.**")
    valid = True

    return valid, analysis_name, analyis_name_topic_str


def init_analysis(analysis_name: str):
    endpoint = API_BASE_URL + f"bulk_analysis/{analysis_name}"
    response = requests.post(endpoint)
    if response.status_code == 200:
        return True
    else:
        st.error(f"Failed to create the analysis with name {analysis_name}. Please try again.")
        return False


def user_inits_analysis():
    
    # Init session state.
    if "analysis_initiated_flag" not in st.session_state:
        st.session_state.analysis_initiated_flag = False
        st.session_state.processing = False

    # Get placeholder.
    if st.session_state.analysis_initiated_flag:
        analyis_name_topic_str_placeholder = st.session_state.analysis_name_topic_str

    else:
        analyis_name_topic_str_placeholder = get_valid_placeholder()
        st.session_state.analysis_name_topic_str = analyis_name_topic_str_placeholder
    
    # Get name.
    valid, analysis_name, analyis_name_topic_str = get_analysis_name(analyis_name_topic_str_placeholder)

    # Initiate the analysis.                        
    if not st.session_state.analysis_initiated_flag or st.session_state.analysis_name != analysis_name:        

        # st.session_state.papers_to_process = []        
        st.session_state.search_done = False    
        st.session_state.search_result_papers = []
        st.session_state.papers_uploaded_flag = False
        st.session_state.papers_uploaded = []
        st.session_state.papers_downloaded_flag = False        
        st.session_state.papers_downloaded = []
    
        if st.button("Init analysis", disabled=not valid):
            # Check if the analysis name is valid.
            if not validate_analysis_name(analysis_name, verbose=True):
                st.markdown(":red[The analysis name is already taken. Please choose another one.]")
            else:
                # Initialize the analysis.
                analysis_init_successfull = init_analysis(analysis_name)            
                if not analysis_init_successfull:
                    st.error(f"Coudn't create analysis {analysis_name}. Please try again.")                          
                else:
                    st.session_state.analysis_initiated_flag = True
                    st.session_state.analysis_name = analysis_name
                    st.session_state.analysis_name_topic_str = analyis_name_topic_str
                

    # Show search_result_papers message.
    if st.session_state.analysis_initiated_flag and st.session_state.analysis_name == analysis_name:
        st.success(f"Analysis \"{st.session_state.analysis_name}\" successfully initiated.")

    return analysis_name


def save_scopus_csvs_at_backend(analysis_name: str, uploaded_files: list):
    """
    Send the uploaded Scopus export CSV files to the backend for storage in the analysis folder.
    """

    endpoint = API_BASE_URL + f"bulk_analysis/{analysis_name}/papers/scopus_export/"

    # Create payload.
    files = []
    for file in uploaded_files:
        filename = secure_filename(file.name)
        files.append(('files', (filename, file, 'application/csv')))
    
    # Send the request.
    response = requests.post(endpoint, files=files)    
    if response.status_code == 200:    
        data = response.json()
        paper_ids = data.get("paper_ids", [])  
        paper_titles = data.get("paper_titles", [])      
        successfully_added_papers = data.get("successfully_added_papers", [])
        already_exists_therefore_ignored = data.get("already_exists_therefore_ignored", [])        
        st.success(f"Successfully uploaded {len(uploaded_files)} Scopus export CSV files.")
        return True, paper_ids, paper_titles, successfully_added_papers, already_exists_therefore_ignored
    else:
        print(response.status_code)
        print(response.text)
        st.error(f"Failed to upload the Scopus export CSV files. Please try again.")
        return False, [], [], [], []


def save_pdfs_at_backend(analysis_name: str, uploaded_files: list):
    """
    Send the uploaded PDFs to the backend for storage in the analysis folder.
    """

    endpoint = API_BASE_URL + f"bulk_analysis/{analysis_name}/papers/pdf/"
    
    # The PDF files are send to the API which recieves them as "files: list[UploadFile]"
    # Using curl the request would look like this:
    # -H 'Content-Type: multipart/form-data' \
    # -F 'files=@some_paper.pdf;type=application/pdf' \
    # -F 'files=@some_other_paper.pdf;type=application/pdf'

    # Create payload.
    files = []
    for file in uploaded_files:
        filename = secure_filename(file.name)
        files.append(('files', (filename, file, 'application/pdf')))
    
    # Send the request.    
    response = requests.post(endpoint, files=files)    
    if response.status_code == 200:    
        data = response.json()
        paper_ids = data.get("paper_ids", [])  
        paper_filenames = data.get("paper_filenames", [])      
        successfully_added_papers = data.get("successfully_added_papers", [])
        already_exists_therefore_ignored = data.get("already_exists_therefore_ignored", [])        
        st.success(f"Successfully uploaded {len(uploaded_files)} PDFs.")
        return True, paper_ids, paper_filenames, successfully_added_papers, already_exists_therefore_ignored
    else:        
        print(response.status_code)
        print(response.text)
        st.error(f"Failed to upload the PDFs. Please try again.")
        return False, [], [], [], []


def user_uploads_abstracts_via_scopus_exports(analysis_name: str):
    """
    Upload Scopus Export files for the analysis.
    """

    if "papers_uploaded_flag" not in st.session_state:
        st.session_state.papers_uploaded_flag = False
        st.session_state.papers_uploaded = []

    uploaded_files = st.file_uploader("Upload Scopus Export CSV", type=["csv"], accept_multiple_files=True, disabled=st.session_state.processing, on_change=lambda: st.session_state.update({"papers_uploaded_flag": False}))
        
    if not st.session_state.papers_uploaded_flag and len(uploaded_files) > 0:
        # Send CSVs to backend.
        success, paper_ids, paper_titles, successfully_added_papers, already_exists_therefore_ignored = save_scopus_csvs_at_backend(analysis_name, uploaded_files)
        if success:
            uploaded_and_stored = []
            for paper_id, filename in zip(paper_ids, paper_titles):
                paper_dict = {"id": paper_id, "title": filename, "publication_year": "N/A", "doi": "N/A", "selected": True}
                uploaded_and_stored.append(paper_dict)                                                

            st.session_state.papers_uploaded_flag = True
            st.session_state.papers_uploaded = uploaded_and_stored
            
        else:
            st.error("Failed to upload the PDFs. Please try again.")
            st.session_state.papers_uploaded_flag = False
            st.session_state.papers_uploaded = []                                  
        
    return uploaded_files


def user_uploads_pdfs(analysis_name: str):
    """
    Upload PDFs for the analysis.
    """

    if "papers_uploaded_flag" not in st.session_state:
        st.session_state.papers_uploaded_flag = False
        st.session_state.papers_uploaded = []

    uploaded_files = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True, disabled=st.session_state.processing, on_change=lambda: st.session_state.update({"papers_uploaded_flag": False}))
        
    if not st.session_state.papers_uploaded_flag and len(uploaded_files) > 0:
        # Send PDFs to backend.        
        success, paper_ids, paper_filenames, successfully_added_papers, already_exists_therefore_ignored = save_pdfs_at_backend(analysis_name, uploaded_files)                
        if success:
            uploaded_and_stored = []
            for paper_id, filename in zip(paper_ids, paper_filenames):
                paper_dict = {"id": paper_id, "title": filename, "publication_year": "N/A", "doi": "N/A", "selected": True}
                uploaded_and_stored.append(paper_dict)                                                

            st.session_state.papers_uploaded_flag = True
            st.session_state.papers_uploaded = uploaded_and_stored
            
        else:
            st.error("Failed to upload the PDFs. Please try again.")
            st.session_state.papers_uploaded_flag = False
            st.session_state.papers_uploaded = []                                  
        
    return uploaded_files


def get_papers_to_download_by_search_query():
    """
    Find papers in bibliographic database based on a search query.
    """
    with st.container(border=True):
        st.write("""
            :red[Note: The search query must be a valid query for the OpenAlex API. 
            The search queries are similar to those used in Scopus, but differ. 
            If you are unsure, you can test your query [here](https://openalex.org/).]
            """)
        search_query = st.text_input("Enter a search query", '( "Direct Air Capture" OR "DAC" ) AND ( "CO2 capture" OR "carbon capture" )')
        # Run the search query, and display the results
        limit = st.number_input("Limit", 1, 1_000_000, 3)
        pub_year_range = st.slider("Publication year range", 1950, CURRENT_YEAR + 1, (2010, CURRENT_YEAR + 1))
        pub_year_range_str = f"{pub_year_range[0]}-{pub_year_range[1]}"
        only_open_access = st.checkbox("Only open access", value=True)
        only_english = st.checkbox("Only English (only English text is supported for now)", value=True, disabled=True)                            

        if st.button("Search"):
            with st.spinner("Searching..."):
                endpoint = API_BASE_URL + f"bibliographic_metadata/search/query?search_query={search_query}&only_open_access={only_open_access}&only_english={only_english}&pub_year={pub_year_range_str}&limit={limit}"
                response = requests.get(endpoint)
            
            if response.status_code == 200:
                st.session_state.search_result_papers = response.json().get("papers")
                st.session_state.search_done = True
            else:
                st.error("Failed to find papers in the database. Please try again.")
                st.session_state.search_result_papers = []
                st.session_state.search_done = False

        if st.session_state.search_done:
            st.success(f"The query returned {len(st.session_state.search_result_papers)} papers.")

        return st.session_state.search_result_papers


def find_papers_in_database_based_on_dois(dois: list[str]):    
                                       
    with st.spinner("Searching..."):
        endpoint = API_BASE_URL + "bibliographic_metadata/search/dois"        
        response = requests.post(endpoint, json={"dois": dois})
        
    if response.status_code == 200:
        papers_in_db = response.json().get("papers")
        if papers_in_db is None:            
            st.error("Failed to find papers in the database. Unexpected response format.")
            st.session_state.search_result_papers = []
            st.session_state.search_done = False
        else:            
            st.session_state.search_result_papers = papers_in_db
            st.session_state.search_done = True
            
            if len(papers_in_db) == len(dois):
                st.success(f"Found {len(papers_in_db)} of {len(dois)} papers.")
            elif len(papers_in_db) > 0:
                st.warning(f"Found {len(papers_in_db)} of {len(dois)} papers. Some DOIs might not be valid.")
            else:
                st.error(f"Found {len(papers_in_db)} of {len(dois)} papers. None of the DOIs are valid.")
    else:
        st.error(f"Failed to find papers in the database. Please try again.")
        st.write(response.status_code)
        st.write(response.text)
        st.session_state.search_result_papers = []
        st.session_state.search_done = False

    return st.session_state.search_result_papers


def get_papers_to_download_based_on_list_of_dois():
    """
    Find papers in bibliographic database based on a list of DOIs.
    """    
    dois = st.text_area("Enter the DOIs separated by newlines", "10.1016/j.joule.2021.07.007\n10.7717/peerj.4375")
    download_papers = st.button("Find papers in bibliographic database")    
    if download_papers:
        dois = list(set([doi.strip() for doi in dois.split("\n") if doi.strip()]))        
        return find_papers_in_database_based_on_dois(dois)        
    else:
        return st.session_state.search_result_papers


def get_papers_to_download_based_on_scopus_export():
    st.write("Go to [Scopus](https://www.scopus.com/search/form.uri?display=basic#basic) build your search query and export the results as a CSV file. Make sure to include the DOIs in the export.")
    # st.markdown(":red[Note only papers with DOIs will be included in the analysis.]")
    scopus_csv = st.file_uploader("Upload Scopus export", type=["csv"], accept_multiple_files=False)    
    if scopus_csv:
        # Get DOIs from the Scopus export
        df = pd.read_csv(scopus_csv)
        if "DOI" not in df.columns:
            st.error("The Scopus export must contain a column named 'DOI'.")
            return []
        else:            
            dois = df["DOI"].astype(str).replace("nan", None).tolist()            

            # Remove empty DOIs.
            nbr_rows = len(dois)
            dois = [doi for doi in dois if doi not in [None, ""]]

            if len(dois) == 0:
                st.error("The Scopus export does not contain any DOIs.")
                return []
            else:

                # Validate DOIs                
                valid_dois = []
                invalid_dois = []
                for doi in dois:
                    if DOI_PATTERN.match(doi):
                        valid_dois.append(doi)
                    else:
                        invalid_dois.append(doi)
                                                            
                st.success(f"Found {len(dois)} valid DOIs in the Scopus export.")
                if nbr_rows > len(valid_dois):
                    st.warning(f"{nbr_rows - len(dois)} rows were ignored because they did not contain a DOI.")
                if len(invalid_dois) > 0:
                    invalid_dois_list = "\n * " +  "  \n * ".join(invalid_dois)
                    st.warning(f"The following DOIs are invalid and will also be ignored. If you think they are valid, please contact the admin. {invalid_dois_list}")

                return find_papers_in_database_based_on_dois(valid_dois)
    else:
        return st.session_state.search_result_papers



def get_papers_to_download(paper_selection_method):
    """
    Get the papers to be downloaded for the analysis.
    """
    if "search_result_papers" not in st.session_state:
        st.session_state.search_result_papers = []
        st.session_state.search_done = False
    
    if paper_selection_method == "Search query (not recommended)":
        papers_meta = get_papers_to_download_by_search_query()
    elif paper_selection_method == "List of DOIs":
        papers_meta = get_papers_to_download_based_on_list_of_dois()
    elif paper_selection_method == "Upload Scopus export":
        papers_meta = get_papers_to_download_based_on_scopus_export()
    else:
        st.error("Invalid paper selection method.")

    # Shorten OpenAlex IDs.
    for paper in papers_meta:
        paper["id"] = paper["id"].removeprefix("https://openalex.org/")
    
    
    if len(papers_meta) > 0:
        allow_selection = paper_selection_method == "Search query (not recommended)"
        
        # Add field "selected" to each paper.
        for paper in papers_meta:
            if "selected" not in paper:
                paper["selected"] = True

        if allow_selection:
            # Show the title of each paper in table and allow to deselect it from being analyzed.
            st.write("Select the papers to be included in the analysis:")
            for paper in papers_meta:
                paper["selected"] = st.checkbox(get_paper_display_name(paper["title"], paper["publication_year"]), value=paper["selected"])

            # st.session_state.papers_selected = True
            papers_meta = [paper for paper in papers_meta if paper["selected"]]
            st.info(f"Selected {len(papers_meta)} papers.")
        else:            
            paper_display_names = [get_paper_display_name(p["title"], p["publication_year"]) for p in papers_meta]
            papers_list_str = "  \n * ".join(paper_display_names)
            st.markdown("**Selected papers**: \n  * " + papers_list_str)

    if st.session_state.search_done:
        return papers_meta
    else:
        return []


def download_fulltext(doi, analysis_name):
    """
    Download the fulltext of the paper.
    """
    with st.spinner("Downloading..."):
        endpoint = API_BASE_URL + f"bulk_analysis/{analysis_name}/papers/doi/?doi={doi}"
        response = requests.post(endpoint)
        if response.status_code == 200:            
            return True
        else:            
            return False


def download_fulltexts(papers_meta, analysis_name):
    """
    Attempt to download the fulltexts of the papers.
    """
    st.markdown("##### 3. Get full texts")
    st.write("Now that you have selected the papers, we attempt to automatically obtain the full texts of the papers. For papers that are not available, you can upload them manually later.")
    if "papers_downloaded" not in st.session_state:
        st.session_state.papers_downloaded_flag = False
        st.session_state.papers_downloaded = []
    
    successfully_downloaded = []
    failed_to_download = []
    if st.button("Request the full texts of the selected papers", disabled=st.session_state.processing):
        progress_bar_desc = "Downloading papers..."
        progress_bar = st.progress(0, text=progress_bar_desc)
        for i, paper in enumerate(papers_meta):
            # Download the fulltext of the paper.
            doi = paper.get("doi")            
            success = download_fulltext(doi, analysis_name)
            paper_display_name = get_paper_display_name(paper["title"], paper["publication_year"], doi=doi)
            if success:
                successfully_downloaded.append(paper)                
                st.success(f"Successfully downloaded \"{paper_display_name}\".")
            else:
                failed_to_download.append(paper)
                st.error(f"Failed to download \"{paper_display_name}\".")
            progress_bar.progress(i / len(papers_meta), text=progress_bar_desc)

        st.session_state.papers_downloaded_flag = True
        st.session_state.papers_downloaded = successfully_downloaded
        
        progress_bar.empty()

    return successfully_downloaded, failed_to_download


def estimate_execution_time(nbr_papers, number_of_gpus, skip_imprecise_quantities, execution_time_per_paper_lb=30, execution_time_per_paper_ub=120, share_of_imprecise_quantities=0.25, model_loading_time=100):
    """
    Estimate the execution time of the analysis.
    """
    eta_min_in_s = model_loading_time + execution_time_per_paper_lb * nbr_papers / number_of_gpus
    eta_max_in_s = model_loading_time + execution_time_per_paper_ub * nbr_papers / number_of_gpus                        
    if skip_imprecise_quantities:
        eta_min_in_s = eta_min_in_s * (1-share_of_imprecise_quantities)
        eta_max_in_s = eta_max_in_s * (1-share_of_imprecise_quantities)
    
    
    def seconds_to_hours_minutes(seconds: int) -> tuple[int, int]:
        """Format duration in seconds to a tuple of (hours, minutes)."""
        hours, minutes = divmod(seconds, 3600)
        minutes, seconds = divmod(minutes, 60)
        if seconds >= 30:
            minutes += 1
        return int(hours), int(minutes)
    
    eta_min_h_min = seconds_to_hours_minutes(eta_min_in_s)
    eta_max_h_min = seconds_to_hours_minutes(eta_max_in_s)

    return eta_min_in_s, eta_max_in_s, eta_min_h_min, eta_max_h_min


def configure_analysis(nbr_papers, header, max_gpus: int=6):
    st.markdown(header)
    st.write("Configure the analysis by selecting the options below.")
    skip_imprecise_quantities = not st.checkbox("Include imprecise quantities such as 'several', 'few', etc.", value=True, disabled=st.session_state.processing)
        
    default_gpu_count = min(max_gpus, nbr_papers // 30 + 1)
    number_of_gpus = st.number_input("Select the number of GPUs to use", 1, max_gpus, default_gpu_count, disabled=st.session_state.processing)
                                    
    eta_min_in_s, eta_max_in_s, (eta_min_hours, eta_min_minutes), (eta_max_hours, eta_max_minutes) = estimate_execution_time(nbr_papers, number_of_gpus, skip_imprecise_quantities)
    if eta_max_in_s < 15*60:
        in_the_meantime = "get a coffee"
    elif eta_max_in_s < 45*60:
        in_the_meantime = "go for a walk"
    else:
        in_the_meantime = "check back later"

    if eta_min_hours == 0 and eta_max_hours == 0:
        st.info(f"Estimated execution time is {eta_min_minutes} to {eta_max_minutes} minutes.")
    else:
        st.info(f"Estimated execution time is {eta_min_hours} hours and {eta_min_minutes} minutes to {eta_max_hours} hours and {eta_max_minutes} minutes.")
    
    return number_of_gpus, skip_imprecise_quantities, in_the_meantime

