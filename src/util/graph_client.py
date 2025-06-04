from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
load_dotenv()

class GraphClient:
    def __init__(self):
        URI = os.getenv("NEO4J_URI")
        AUTH = (os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
        self.driver = GraphDatabase.driver(URI, auth=AUTH) 
        self.driver.verify_connectivity()
        
    def session(self):
        return self.driver.session()
    
    def getDriver(self):
        return self.driver