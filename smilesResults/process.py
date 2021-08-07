import json

inputName = "stat3New.json"
outputName = "stat3Processed.json"

with open(inputName, "r", encoding="utf-8") as inputFile:
    resultDict = json.load(inputFile)

newDrugMoleculePaper = []
index = 0
for article in resultDict["drug_molecule_paper"]:
    if(article["compound_smiles"]):
        article["id"] = index
        newDrugMoleculePaper.append(article)
        index += 1

resultDict["drug_molecule_paper"] = newDrugMoleculePaper
resultDict["drug_molecule_count"] = len(resultDict["drug_molecule_paper"])

with open(outputName, "w", encoding="utf-8") as outputFile:
    jsonString = json.dumps(resultDict, ensure_ascii=False)
    outputFile.write(jsonString)

 


