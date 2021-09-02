import json
from html.parser import HTMLParser
import glob
import table
import requests



def exitParser(parser):
    parser.reset()

class TableParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)


        self.doi = ""

        self.doiFound = False
        self.doiLink = False
        


    def handle_starttag(self, tag, attrs):
        if(tag == "div" and len(attrs) == 1 and attrs[0][1] == "article_header-doiurl"):
            self.doiFound = True
        if(self.doiFound and tag == "a"):
            self.doiLink = True



    def handle_data(self, data):

        if(self.doiLink):
            index = data.find("https://doi.org/")
            if(index != -1):
                self.doi = data[16:]


    
    def handle_endtag(self, tag):
        if(self.doiFound and tag == "div"):
            self.doiFound = False
            exitParser(self)
        if(self.doiLink and tag == "a"):
            self.doiLink = False



def getArticleParsers(inputFilePath, targetName):
    articleParserArr = []

    with open(inputFilePath, "r", encoding="utf-8") as inputFile:
        resultDict = json.load(inputFile)

    fileAmount = len(glob.glob(f"files/{targetName.lower()}/*"))
    fileId = 0
    for article in resultDict["drug_molecule_paper"]:
        
        success = False
        while(not success):
            if(fileId < fileAmount):
                for i in range(fileId, fileAmount):
                    with open(f"files/{targetName.lower()}/file{i}.html", encoding="utf-8") as articlePage:
                        doiParser = TableParser()
                        try:
                            doiParser.feed(articlePage.read())
                        except AssertionError as ae:
                            pass
                        if(doiParser.doi == article["doi"]):
                            parser = table.ACSTableParser()
                            try:
                                with open(f"files/{targetName.lower()}/file{i}.html", encoding="utf-8") as articlePage2:
                                    parser.feed(articlePage2.read())
                            except AssertionError as ae:
                                pass
                            articleParserArr.append([article, parser])
                            success = True
                            fileId += 1
                            break
                        else:
                            fileId += 1
            
            else:
                QUERY_URL = "https://api.elsevier.com/content/article/doi/"
                APIKEY = "1db58eab83275e096b8f658fe085a39a"
                header = {"X-ELS-APIKey": APIKEY, "Accept": "text/xml"}
                response = requests.get(QUERY_URL + article["doi"], headers=header)
                
                parser = table.ScienceDirectTableParser()
                try:
                    parser.feed(response.text)
                except AssertionError as ae:
                    pass
                    
                articleParserArr.append([article, parser])
                success = True

    return articleParserArr



