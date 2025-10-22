import random
import requests
from datetime import datetime                
from pathlib import Path
import streamlit as st

from pages.helpers.create_new_analysis import user_inits_analysis, get_paper_display_name, user_uploads_pdfs, user_uploads_abstracts_via_scopus_exports, get_papers_to_download, download_fulltexts, configure_analysis
from pages.helpers.get_config import CONFIG, API_BASE_URL



DASHBOARD_CONFIG = CONFIG["analyses_dashboard"]
CURRENT_YEAR = datetime.now().year  

# Split the page into two columns.
getting_started_column, docs_column = st.columns([0.4, 0.6], gap="large")

def devide_sections():
    st.markdown('---')

with getting_started_column:
    
    maintenance_active = False
    if maintenance_active:
        # Show maintenance message
        st.markdown(
            """
            <div style="background-color: #f9f9f9; padding: 10px; border-radius: 5px;">
                <h3 style="color: #ff0000;">🚧 Maintenance 🚧</h3>
                <p>The application is currently undergoing maintenance. Please check back later.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


    def check_api_status():
        endpoint = API_BASE_URL + "is_alive/services"
        response = requests.get(endpoint)        
        if response.status_code == 200:
            services = response.json().get("detail", {})
            return services.get("api", False), services.get("parsing", False), services.get("extraction", False), services.get("bulk_extraction", False)
        else:            
            return False, False, False, False        

    # Check if the API is running.
    demo_although_services_down = False
    if demo_although_services_down:
        # Simulate API status for demo purposes
        api_good = True
        parsing_good = True
        extraction_good = True
        bulk_extraction_good = True
    else:
        api_good, parsing_good, extraction_good, bulk_extraction_good = check_api_status()

    st.markdown("# Get started")
    

    ##########################################################################

    st.markdown("### :rainbow-background[Test quinex by entering some text]")
    with st.container(border=True):        
        if not extraction_good:
            st.error("The extraction service is currently not available. Please try again later or contact the admin.")
        
        text_demo_placeholders = DASHBOARD_CONFIG.get("text_demo_placeholders", ["The quick brown fox has an eigenfrequency of 5 Hz."])
        if "text_demo_placeholder" not in st.session_state:
            st.session_state.text_demo_placeholder = random.choice(text_demo_placeholders)

        text = st.text_area("Enter text", st.session_state.text_demo_placeholder, disabled=not extraction_good)
        skip_imprecise_quantities = not st.checkbox("Include imprecise quantities", value=True, disabled=not extraction_good)
        if st.button("Analyze 🪄", disabled=not extraction_good):
            # Send annotation job to the quinex API
            endpoint = API_BASE_URL + f"text/annotate?skip_imprecise_quantities={skip_imprecise_quantities}&add_curation_fields=false"

            with st.spinner("Processing..."):
                response = requests.post(endpoint, json=text)
                response_json = response.json()

            # Display the json response
            st.write("Result:")
            st.json(response_json)
        
    ##########################################################################

    st.markdown("### :rainbow-background[Analyze scientific articles]")
    with st.container(border=True):
        st.markdown("#### Check out the results")
        st.markdown(
            """            
            To see what the results of an analysis look like and to 
            learn what quinex can and can't do, **check out the demos below**. 
            Note that they contain some errors which are fixed in the current version of quinex.
            """
        )        
        for example_analysis in DASHBOARD_CONFIG.get("example_analyses", []):
            st.link_button(example_analysis["name"], url=example_analysis["url"])
        
        st.markdown("")
        st.markdown("#### View results of your analysis")        
        st.markdown("You can **view the results of your own analysis** by entering its name below and clicking 'View Results'.")        
        results_analysis_name = st.text_input("Analysis name", value="", key="results_analysis_name")
        
        # Create a link to the results page within the multipage app
        if results_analysis_name:
            results_url = f"/results?analysis={results_analysis_name}"
            st.link_button("View Results", url=results_url, disabled=False)
        else:
            st.link_button("View Results", url="#", disabled=True)


    ##########################################################################

    bulk_analysis_disabled = not all([api_good, parsing_good, extraction_good])
    with st.container(border=True): 
        allow_submit = False

        st.markdown("#### Create a new analysis")
        st.markdown(
            """
            To create a new analysis, enter a name, select the papers to be analyzed, and click submit.
            The analysis will only be visible for people that know the analysis name.
            """
        )                   
        
        if bulk_analysis_disabled:
            st.error("The services necessary to run a bulk analysis are currently not available. Please try again later or contact the admin. If you are the admin, make sure the parsing and extraction services are running.")
        else:
            devide_sections()
            analysis_name = user_inits_analysis()
            if analysis_name != None:
                # There are three options to select the papers to be analyzed:
                # Use a search query or upload a files or upload a csv with DOIs.
                devide_sections()
                st.markdown("##### 2. Select papers to be analyzed")
                st.markdown("Do you want to analyze full texts or only abstracts (if available)? Analyzing only abstracts is faster but less comprehensive.")
                fulltext = not st.checkbox("Only process abstracts", value=False, disabled=not st.session_state.analysis_initiated_flag or st.session_state.processing)
                if fulltext:
                    valid_paper_selection_methods = ["Search query (not recommended)", "List of DOIs", "Upload PDFs", "Upload Scopus export"]
                else:
                    valid_paper_selection_methods = ["Upload Scopus export (only process abstracts)"]
                    st.write("Make sure to include the following fields when configuring the Scopus results export: DOI, Title, Source title, Year, Abstract.")

                paper_selection_method = st.selectbox(
                    "Choose a method to define which papers to analyze. You will still be able to add and remove papers afterwards.",
                    valid_paper_selection_methods,             
                    index=None,
                    disabled=not st.session_state.analysis_initiated_flag or st.session_state.processing,
                    on_change=lambda: st.session_state.update(
                        {
                            "search_result_papers": [], 
                            "search_done": False, 
                            "papers_downloaded": [], 
                            "papers_uploaded": [], 
                            "papers_uploaded_flag": False, 
                            "papers_downloaded_flag" : False
                        }
                    ),
                )

                no_fulltext_download_methods = ["Upload PDFs", "Upload Scopus export (only process abstracts)"]
                if st.session_state.analysis_initiated_flag and paper_selection_method in valid_paper_selection_methods:

                    if paper_selection_method in no_fulltext_download_methods:
                        
                        if paper_selection_method == "Upload PDFs":
                            # Selected papers are those uploaded by the user.
                            uploaded_files = user_uploads_pdfs(analysis_name)
                        elif paper_selection_method == "Upload Scopus export (only process abstracts)":
                            uploaded_files = user_uploads_abstracts_via_scopus_exports(analysis_name)

                        # Nothing to select and download. Set corresponding variables to empty lists.
                        papers_meta = []
                        successfully_downloaded = []
                        failed_to_download = []
                    else:
                        # Selected papers are those specified by the user and which could be downloaded.
                        papers_meta = get_papers_to_download(paper_selection_method)
                        if papers_meta != []:
                            # Try to download the papers.

                            devide_sections()
                            successfully_downloaded, failed_to_download = download_fulltexts(papers_meta, analysis_name)
                            
                            if st.session_state.papers_downloaded_flag:
                                # Optionally, add further papers.
                                devide_sections()
                                st.markdown("##### 4. Optionally, add papers by file upload")
                                uploaded_files = user_uploads_pdfs(analysis_name)

                            # if len(successfully_downloaded) > 0 or len(uploaded_files) > 0:
                                # allow_submit = True

                    papers_selected = st.session_state.papers_uploaded_flag if paper_selection_method in no_fulltext_download_methods else st.session_state.papers_downloaded_flag
                    allow_submit = st.session_state.analysis_initiated_flag and papers_selected    
                    if allow_submit:

                        ##########################################################################
                        
                        devide_sections()
                        overview_header = f"##### 3. Overview" if paper_selection_method in no_fulltext_download_methods else f"##### 5. Overview"
                        st.markdown(overview_header)
                        st.write("The following are all papers that will be processed as part of this analysis. You can still deselect papers that you do not want to be analyzed.")
                        if paper_selection_method not in no_fulltext_download_methods:
                            st.markdown("**Selected and downloaded based on bibliographic services:**")
                            if len(st.session_state.papers_downloaded) == 0:
                                st.write("No papers added using bibliographic services.")
                            else:
                                for i, paper in enumerate(st.session_state.papers_downloaded):
                                    paper["selected"] = st.checkbox(get_paper_display_name(paper["title"], paper["publication_year"], paper["doi"]), value=paper["selected"], disabled=st.session_state.processing, key=f"select_papers_downloaded_{i}")

                            st.markdown("**User uploaded PDFs:**")

                        
                        if len(st.session_state.papers_uploaded) == 0:
                            st.write("No papers added using file upload.")
                        else:
                            for i, paper in enumerate(st.session_state.papers_uploaded):
                                paper["selected"] = st.checkbox(get_paper_display_name(paper["title"]), value=paper["selected"], disabled=st.session_state.processing, key=f"select_papers_uploaded_{i}")
                        
                        selected_downloaded_papers = [paper for paper in st.session_state.papers_downloaded if paper["selected"]]
                        selected_uploaded_papers = [paper for paper in st.session_state.papers_uploaded if paper["selected"]]
                        papers_to_process = selected_downloaded_papers + selected_uploaded_papers

                        ##########################################################################

                        nbr_papers = len(papers_to_process)
                        devide_sections()
                        configure_analysis_header = "##### 4. Configure analysis" if paper_selection_method in no_fulltext_download_methods else "##### 6. Configure analysis"
                        number_of_gpus, skip_imprecise_quantities, in_the_meantime = configure_analysis(nbr_papers, configure_analysis_header)

                        ##########################################################################
                        
                        devide_sections()
                        submit_header = f"##### 5. Click submit and {in_the_meantime}" if paper_selection_method in no_fulltext_download_methods else f"##### 7. Click submit and {in_the_meantime}"
                        st.markdown(submit_header)
                        if nbr_papers < 30:
                            model_init_duration_warning = "Note that analyzing only a handful of papers takes disproportionately longer because the time to load the models into GPU memory is the same regardless of the number of papers."
                        else:
                            model_init_duration_warning = ""

                        st.markdown(f"**If you click submit, the {nbr_papers} selected papers will be analyzed.** " + model_init_duration_warning)

                        if st.button("Submit 🪄", disabled=not allow_submit or st.session_state.processing):
                            st.session_state.processing = True                        
                            with st.spinner("Processing..."):    
                                # Send the analysis to the quinex API                                
                                st.warning(f"Please wait until the current analysis is finished. After your analysis is finished, you will be able to view the results [here](./results?analysis={st.session_state.analysis_name}).")
                                endpoint = API_BASE_URL + f"bulk_analysis/{st.session_state.analysis_name}/process?skip_imprecise_quantities={skip_imprecise_quantities}&gpu_count={number_of_gpus}"
                                response = requests.post(endpoint, json={"paper_ids": [paper["id"] for paper in papers_to_process]})

                                # Check if the analysis was successful
                                if response.status_code == 200:                                    
                                    st.success(f"All papers successfully analyzed")
                                    st.link_button("See results", url=f"/results?analysis={st.session_state.analysis_name}")                                    
                                else:
                                    st.error("An error occurred. Please try again later.")
                            
                        st.session_state.processing = False

                devide_sections()

    ##########################################################################
    st.markdown("### :rainbow-background[Annotate text using the API]")
    with st.container(border=True):           
        st.markdown(
            """
            To annotate text using the quinex API, you can use the following code snippet:
            """
        )                
        st.code(
            f"""
            import requests                        

            QUINEX_API = "{API_BASE_URL}" 
            endpoint = QUINEX_API + "text/annotate?skip_imprecise_quantities=true"

            text = "The 5 MW power plant is located in Germany."

            response = requests.post(endpoint, json=text)
            if response.status_code == 200:
                predictions = response.json()["predictions"]
            else:
                ...
            """
        )
        st.markdown("Or use the command line:")
        st.code(f"curl -X 'POST' '{API_BASE_URL}/text/annotate?skip_imprecise_quantities=true' -H 'accept: application/json' -H 'Content-Type: application/json' -d '\"The 5 MW power plant is located in Germany.\"'")



    st.markdown("\nTo use quinex as a Python library, check out the [quinex repo](https://github.com/FZJ-IEK3-VSA/quinex).") 
    

with docs_column:
    
    # Show README in the right column.
    app_dir = Path(__file__).resolve().parents[1]
    with open(app_dir / "static" / "docs.md", "r") as f:
        docs_md = f.read()
    
    st.markdown(docs_md)
