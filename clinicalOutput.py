import json
import re
import Clinical_View as clinical


resultDict = None

with open("output.json", "r", encoding="utf-8") as inputFile:
    resultDict = json.load(inputFile)

print(resultDict.keys())
articles = resultDict["drug_molecule_paper"]

for article in articles:
    compoundDrugName = article["compound_name_drug"]

    if(re.search("[A-Z]", compoundDrugName)):
        r = clinical.getloadClinicalData(compoundDrugName)
        if("StudyFieldsResponse" in r and "StudyFields" in r["StudyFieldsResponse"]):
            article["clinical_statistics"] = clinical.study_num_Phase(r)
        else:
            article["clinical_statistics"] = {}
    else:
        article["clinical_statistics"] = {}

with open("clinicalOutput.json", "w", encoding="utf-8") as outputFile:
    jsonString = json.dumps(resultDict, ensure_ascii=False)
    outputFile.write(jsonString)