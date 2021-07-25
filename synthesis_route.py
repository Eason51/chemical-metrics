api_key = 'apk-0f058b2cd32807d420ae9bd9afd107274fb517646f6cbf9c532d91545ec7c5bba1194b20abfc8d7a654b382e5215ac1a706db21' \
          'd02d6a8a8582578cad4b2c59546023c737f6e8f27ea25190eb435e08a'
from rxn4chemistry import RXN4ChemistryWrapper
import time
import molecular_Structure_Similarity as similarity
import json

rxn4chemistry_wrapper = RXN4ChemistryWrapper(api_key=api_key)
rxn4chemistry_wrapper.set_project('60f6c190ea9ac40001f5ebd5')

def maxDepth(root):
    if 'children' in root and len(root['children']) and not root['isCommercial']:
        return 1 + max(maxDepth(child) for child in root['children'])
    else:
        return 0

def min_Synthesis_Path(smiles):
    response = rxn4chemistry_wrapper.predict_automatic_retrosynthesis(product=smiles)

    time.sleep(10)
    while True:
        results = rxn4chemistry_wrapper.get_predict_automatic_retrosynthesis_results(response['prediction_id'])
        if results['status'] == 'SUCCESS':
            break
        if results['status'] == 'PROCESSING':
            time.sleep(30)
        else:
            return 0

    path = results['retrosynthetic_paths']

    min_Path_depth = min(maxDepth(child) for child in path)
    return min_Path_depth

with open('','r',encoding='utf8')as fp:
    json_data = json.load(fp)

drug_molecule_paper = json_data["drug_molecule_paper"]
synthesis_route={}
for i in drug_molecule_paper:
    synthesis_route[str(i['"paper_id"'])] = min_Synthesis_Path(i['compound_smiles'])

with open('','w')as fp:
    json.dump(synthesis_route,fp)