from wasabi import msg
from pymongo import MongoClient
from fastapi import HTTPException
from bson.objectid import ObjectId
from manage_analyses_api.config.get_config import CONFIG


##############################################
#          Get database connection.          #
##############################################
db_client = MongoClient(f'mongodb://{CONFIG["manage_analyses_api"]["mongo_db"]["host"]}:{CONFIG["manage_analyses_api"]["mongo_db"]["port"]}/')
db = db_client.papers
PAPER_COLLECTION = db.papers


def add_paper_dict_to_db(paper_dict, overwrite=False):
    """Add paper to MongoDB database."""

    print("###############################################")
    print("###             ADD PAPER TO DB             ###")
    print("###############################################")

    # Check if paper already exists in database.    
    existing_paper = PAPER_COLLECTION.find_one({"paper_id": paper_dict["paper_id"]})

    if existing_paper is None:
        # Paper does not exist in database. Inserting it.              
        result = PAPER_COLLECTION.insert_one(paper_dict)
        operation = "INSERT"
    elif overwrite:        
        # Paper does exist in database. Updating it.
        result = PAPER_COLLECTION.update_one({"paper_id": paper_dict["paper_id"]}, {"$set": paper_dict})
        operation = "UPDATE"
    else:
        # Paper does exist in database but updating it is not allowed. Do nothing.
        operation = None
    
    # Get success and paper ID.
    if operation is not None and result.acknowledged:                
        msg.good(f"Successfull {operation} of paper {paper_dict['paper_id']} into database.")     
        success = True                                        
        paper_id = result.inserted_id if operation == "INSERT" else result.upserted_id
        if paper_id is None and operation == "UPDATE":
            print("No update had to be performed. Paper was already up-to-date.")
            paper_id = existing_paper["_id"]
        paper_id = str(paper_id)
    else:
        paper_id = None
        raise HTTPException(f"Failed to add paper {paper_dict['paper_id']} to database.")
            
    return {'operation': operation, "_id": paper_id}


def get_all_papers_from_db():
    # Find all papers in MongoDB.
    cursor = PAPER_COLLECTION.find({}, {
        "paper_id": 1, 
        "header": {"date_generated": 1},                 
        "title": 1, 
        "authors": 1,
        "year": 1,
        "venue": 1,
        "identifiers": 1,
        "citation_string": 1,
        }) 
    
    def prepare_author_information(x):
        # TODO: Implement this function.
        return x
        
    # Condense the information per paper.
    papers = []
    for paper in cursor:
        paper["_id"] = str(paper["_id"])
        paper["authors"] = prepare_author_information(paper["authors"])
        paper["date_generated"] = paper.pop("header")["date_generated"]
        papers.append(paper)       

    return papers

def get_paper_from_db(paper_id: str):
    paper = PAPER_COLLECTION.find_one({"_id": ObjectId(paper_id)})
    if paper != None:
        paper["_id"] = str(paper["_id"])

    return paper

def delete_paper_from_db(paper_id: str):
    
    result = PAPER_COLLECTION.delete_one( {"_id": ObjectId(paper_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(f"Failed to delete paper {paper_id} from database.")

    return {'success': result.acknowledged}

def check_paper_exists_in_db_by_hash(hash: str):
    """Get paper by ID from MongoDB.

    Args:
        PAPER_COLLECTION(MongoDB collection): MongoDB collection for papers.
        hash (str): The sha256 hash of the paper PDF.

    Returns:
        exist (boolean): Whether the paper exists or not.
    """    
    paper = PAPER_COLLECTION.find_one({"paper_id": hash}, {"paper_id": 1, "title": 1, "header": {"date_generated": 1}})    

    if paper != None:
        metadata = {"_id": str(paper["_id"]), "title": paper["title"], "date_generated": paper["header"]["date_generated"]}
        exist = True
    else:          
        metadata = {}
        exist = False

    return exist, metadata