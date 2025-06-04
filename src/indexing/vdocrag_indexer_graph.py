from indexing.vdocrag_indexer_extract_attributes import FileAttributes, FileType
from indexing.vdocrag_indexer_extract_changes import Change, extract_changes_from_changelog, generate_changes_from_diff
from indexing.vdocrag_indexer_clustering import cluster_categories
from util.graph_client import GraphClient

class VDocRAGIndexerGraph():      
    def __init__(self):
        self.graph = GraphClient()
        
    def generate_basic_graph(self, files_with_attributes: list[FileAttributes]):
        with self.graph.session() as session:
            for i, file_with_attributes in enumerate(files_with_attributes):
                print(f"add documentation to graph {file_with_attributes}")
                session.execute_write(self.documentation_version_content_tx, file_with_attributes)
            session.execute_write(self.link_versions_tx)
            session.execute_write(self.cluster_categories_tx)
    
    def documentation_version_content_tx(self, tx, file: FileAttributes):
        tx.run("""
            MERGE (d:Documentation {name: $name})
            SET d.description = $description
            RETURN d.name AS name, d.description AS description
            """, 
            name=file.documentation, 
            description=file.description
        )
        
        tx.run("""
            MERGE (v:Version {version: $version, documentation: $documentation})
            MERGE (d:Documentation {name: $documentation})
            MERGE (d)-[:HAS_VERSION]->(v)
            
            MERGE (content:Content {file: $file})
            SET content.type = $type
            MERGE (v)-[:HAS_CONTENT]->(content)
    
            RETURN v.version AS version, d.name AS documentation, content.type as type, content.file AS file
            """, 
            version=file.version,
            documentation=file.documentation,
            file=file.data_file,
            type=file.type.name
        )
        
    def link_versions_tx(self, tx):
        # link versions to next version in documentation.
        tx.run("""
            MATCH (d:Documentation)-[:HAS_VERSION]->(v:Version)
            WITH d, v
            ORDER BY 
            CASE 
                // sort numerically
                WHEN v.version =~ '\\d+(\\.\\d+)*' THEN v.version 
                ELSE ''  
            END,
            CASE 
                // sort by date
                WHEN v.version =~ '\\d{2}\\-\\d{2}\\-\\d{4}' 
                THEN date(substring(v.version, 6, 4) + "-" + substring(v.version, 3, 2) + "-" + substring(v.version, 0, 2)) 
                ELSE date('9999-12-31') 
            END
            
            WITH d, COLLECT(v) AS versions  // group per documentation
            UNWIND RANGE(0, SIZE(versions)-2) AS i
            WITH versions[i] AS current, versions[i+1] AS next
            MERGE (current)-[:NEXT_VERSION]->(next)
            RETURN current.version, next.version
            """)

    def cluster_categories_tx(self, tx):
        # list documentation nodes
        result = tx.run("""
                        MATCH (d:Documentation)
                        RETURN d.name AS name, d.description AS description
                        """)
        documentation_nodes = [{"name": record["name"], "description": record["description"]} for record in result]

        # cluster to categories
        cluster_result = cluster_categories(documentations=documentation_nodes)
        
        if cluster_result is not None:
            # create category nodes
            for i, clustering in enumerate(cluster_result):
                tx.run("""
                    MERGE (c:Category {name: $category_name})
                    WITH c
                    UNWIND $doc_names AS doc_name
                    MATCH (d:Documentation {name: doc_name})
                    MERGE (c)-[:CONTAINS]->(d)
                """, category_name=clustering["name"], doc_names=clustering["documents"])
        
    def generate_change_level(self):
        # extract changes from changelog and store them
        changelog_contents = self.get_changelog_contents()
        diff_contents = self.get_diff_contents()
        with self.graph.session() as session:
            for changelog_content in changelog_contents:
                changes_from_changelog = extract_changes_from_changelog(changelog_content)
                session.execute_write(self.store_changes, changes_from_changelog)
            # generate changes from difference between versions
            changes_from_diff = generate_changes_from_diff(diff_contents)
            session.execute_write(self.store_changes, changes_from_diff)
           
    def get_all_content_nodes_with_context(self):
        query = """
        MATCH (cat:Category)-[:CONTAINS]->(doc:Documentation)-[:HAS_VERSION]->(v:Version)-[:HAS_CONTENT]->(ct:Content)
        RETURN ct.file AS file,
            ct.type AS content_type,
            v.version AS version,
            doc.name AS documentation,
            cat.name AS category
        ORDER BY cat.name, doc.name, v.version
        """
        with self.graph.session() as session:
            result = session.run(query)
            return [
                {
                    'file': record['file'],
                    'content_type': record['content_type'],
                    'version': record['version'],
                    'documentation': record['documentation'],
                    'category': record['category']
                }
                for record in result
            ]
    
    def get_all_change_nodes_with_context(self):
        query = """
        MATCH (cat:Category)-[:CONTAINS]->(doc:Documentation)-[:HAS_VERSION]->(v:Version)
            -[:HAS_CHANGES]->(:Changes)-[:INCLUDES]->(ch:Change)
        RETURN ch.name AS name,
            ch.description AS description,
            ch.source_file AS file,
            v.version AS version,
            doc.name AS documentation,
            cat.name AS category
        ORDER BY cat.name, doc.name, v.version
        """
        with self.graph.session() as session:
            result = session.run(query)
            return [
                {
                    'name': record['name'],
                    'description': record['description'],
                    'version': record['version'],
                    'documentation': record['documentation'],
                    'category': record['category'],
                    'file': record['file']
                }
                for record in result
            ]
        
    def get_changelog_contents(self):
        query = f"""
        MATCH (d:Documentation)-[:HAS_VERSION]->(v:Version)-[:HAS_CONTENT]->(ct:Content)
        WHERE ct.type IN ['{FileType.Changelog.name}']
        RETURN d.name AS documentation, v.version AS version, ct.file AS file, ct.type AS type
        ORDER BY d.name, v.version
        """
        with self.graph.session() as session:
            result = session.run(query)
            return [record.data() for record in result]
        
    def get_diff_contents(self):
        query = f"""
        MATCH (d:Documentation)-[:HAS_VERSION]->(v1:Version)-[:NEXT_VERSION]->(v2:Version)
        MATCH (v1)-[:HAS_CONTENT]->(c1:Content)
        MATCH (v2)-[:HAS_CONTENT]->(c2:Content)
        WHERE c1.type = '{FileType.WithoutChangelog.name}' AND c2.type = '{FileType.WithoutChangelog.name}'
        RETURN d.name AS documentation, 
            v1.version AS version1, c1.file AS file1, 
            v2.version AS version2, c2.file AS file2
        ORDER BY d.name, v1.version
        """
        with self.graph.session() as session:
            result = session.run(query)
            return [record.data() for record in result]
        
    def store_changes(self, tx, changes: list[Change]):
        query = """
        MATCH (d:Documentation {name: $documentation})-[:HAS_VERSION]->(v:Version {version: $version})
        MERGE (v)-[:HAS_CHANGES]->(ch:Changes)
        MERGE (ch)-[:INCLUDES]->(chg:Change {name: $name, description: $description})
        SET chg.description = $description,
            chg.source_file = $source_file,
            chg.source_page_nr = $source_page_nr,
            chg.origin = $origin
        RETURN chg
        """
    
        for change in changes:
            tx.run(query, 
                documentation=change.documentation,
                version=change.version,
                name=change.name,
                description=change.description,
                source_file=change.source_file,
                source_page_nr=change.source_page_nr,
                origin=change.origin.name
            )

