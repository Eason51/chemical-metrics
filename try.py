from table import ACSTableParser
import nlp_implementation as nlp



fileId = 107
tableParser = ACSTableParser()
# open a file locally, should be retrieved through http request in real programs
with open(f"files/kras/file{fileId}.html", encoding="utf-8") as inputFile:

    try:
        tableParser.feed(inputFile.read())
    except AssertionError as ae:
        pass


modelDict = nlp.load_pre_trained_nlp_model()
nlpResult = nlp.get_nlp_results(tableParser, **modelDict)
print(nlpResult)
