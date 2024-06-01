from rdkit import Chem
from rdkit.Chem import AllChem
from neo4j import GraphDatabase

# Connect to Neo4j
driver = GraphDatabase.driver("neo4j://localhost:7687", auth=("neo4j", "1234"))

# # Example molecules
# molecules = {
#     "aspirin": "CC(=O)OC1=CC=CC=C1C(=O)O",
#     "caffeine": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
#     # Add more molecules as needed
# }

# Load molecules from a file
molecules = Chem.SDMolSupplier("chembl_861.sdf")
molecules = [mol for mol in molecules if mol is not None]
# Take 20 Example molecules
molecules = molecules[:20]
molecules = {mol.GetProp("chembl_id"): Chem.MolToSmiles(mol) for mol in molecules}
# remove molecules with invalid SMILES
molecules = {name: smiles for name, smiles in molecules.items() if Chem.MolFromSmiles(smiles) is not None}

# Generate fingerprints
fingerprints = {}
for name, smiles in molecules.items():
    mol = Chem.MolFromSmiles(smiles)
    fingerprint = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=1024)
    fingerprints[name] = list(fingerprint)

similarity_query = """
MATCH (m1:Molecule {id: $name1})
MATCH (m2:Molecule {id: $name2})
RETURN gds.similarity.jaccard(m1.fingerprint, m2.fingerprint) AS similarity
"""

# Load molecules and fingerprints into Neo4j
with driver.session() as session:
    for name, fingerprint in fingerprints.items():
        session.run("CREATE (m:Molecule {id: $name, smiles: $smiles, fingerprint: $fingerprint})",
                    name=name, smiles=molecules[name], fingerprint=fingerprint)
        
    for name1 in molecules:
        for name2 in molecules:
            if name1 != name2:
                result = session.run(similarity_query, name1=name1, name2=name2)
                similarity = result.single()["similarity"]
                print(f"Similarity between {name1} and {name2}: {similarity}")
                # Create a relationship if similarity is above a certain threshold
                if similarity > 0.99:
                    session.run("MATCH (m1:Molecule {id: $name1}) MATCH (m2:Molecule {id: $name2}) "
                                "MERGE (m1)-[:SIMILAR_TO {similarity: $similarity}]->(m2)",
                                name1=name1, name2=name2, similarity=similarity)
                    
driver.close()