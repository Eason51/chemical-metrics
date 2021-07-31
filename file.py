# download all files retrieved from acs published on Journal of Medicinal Chemistry wih the given keyword

import requests
from html.parser import HTMLParser
import sys

addressArr = []
DOMAIN = "https://pubs.acs.org"

class QueryParser(HTMLParser): 
    def __init__(self):
        HTMLParser.__init__(self)
        self.articleTagFound = False

        self.pageListFound = False
        self.nextButtonFound = False

    def handle_starttag(self, tag, attrs):
        if (tag == "h2" and len(attrs) == 1 and attrs[0][1] == "issue-item_title"):
            self.articleTagFound = True
        elif (self.articleTagFound and tag == "a"):
            global addressArr, DOMAIN
            addressArr.append(DOMAIN + attrs[0][1])
            self.articleTagFound = False


        elif (tag == "ul" and len(attrs) == 1 and attrs[0][1] == "rlist--inline pagination__list"):
            self.pageListFound = True
        elif (self.pageListFound and tag == "span"):
            self.nextButtonFound = True
        elif (self.nextButtonFound and tag == "a"):
            self.pageListFound = False
            self.nextButtonFound = False
            for attr in attrs:
                if (attr[0] == "href"):
                    QueryParserHandler.nextPageURL = attr[1]
    

    def handle_endtag(self, tag):
        if(self.pageListFound and tag == "nav"):
            self.pageListFound = False
            self.nextButtonFound = False
            QueryParserHandler.hasNextPage = False


class QueryParserHandler:
    hasNextPage = True
    nextPageURL = ""





keyWords = []

for i in range(1, len(sys.argv)):
    keyWords.append(sys.argv[i])

URLs = []


for keyWord in keyWords:
    queryString = ""
    for word in keyWord.split():
        if(not queryString):
            queryString += word
        else:
            queryString += f"+{word}"
    URLs.append((keyWord, f"https://pubs.acs.org/action/doSearch?field1=AllField&text1={queryString}&field2=AllField&text2=&ConceptID=&ConceptID=&publication=&publication%5B%5D=jmcmar&accessType=allContent&Earliest=")) 



keyWordId = 0
for URL in URLs:
    addressArr.clear()
    QueryParserHandler.hasNextPage = True
    response = requests.get(URL[1])

    queryParser = QueryParser()
    queryParser.feed(response.text)
    while(QueryParserHandler.hasNextPage):
        response = requests.get(QueryParserHandler.nextPageURL, headers = {"User-Agent": "Mozilla/5.0"})
        queryParser.feed(response.text)

    fileId = 0
    for address in addressArr:
        articleResponse = requests.get(address)
        with open(f"files/{keyWords[keyWordId]}/file{fileId}.html", "w", encoding="utf-8") as outputFile:
            
            class TableParser(HTMLParser):
                def __init__(self):
                    HTMLParser.__init__(self)
                    self.HTML = ""

                    self.ICFound = False
                    self.keywordFound = True
                    self.abstractFound = False
                    self.paragraphFound = False
                    self.paragraphDivCount = 0

                
                
                def handle_starttag(self, tag, attrs):
                    self.HTML += (self.get_starttag_text())

                    if(self.keywordFound):
                        return
                    
                    if(tag == "p" and len(attrs) == 1 and attrs[0][1] == "articleBody_abstractText"):
                        self.abstractFound = True
                    if(tag == "div" and len(attrs) == 1 and "NLM_p" in attrs[0][1]):
                        self.paragraphFound = True
                        self.paragraphDivCount += 1
                    elif(self.paragraphFound and tag == "div"):
                        self.paragraphDivCount += 1
                
                
                
                def handle_data(self, data):
                    self.HTML += (data)

                    if(self.keywordFound):
                        return

                    if(self.paragraphFound or self.abstractFound):
                        stringList = ["ic50", "ec50", "ki50", "kd50", "ed50"]            
                        if(any(substring in data.lower().strip() for substring in stringList)):
                            self.keywordFound = True
                        elif(self.ICFound):
                            if(len(data) >= 2 and data[:2] == "50"):
                                self.keywordFound = True
                            else:
                                self.ICFound = False
                        elif(len(data) >= 2 and (data.lower().strip()[-2:] in ["ic", "ec", "ki", "kd", "ed"])):
                            self.ICFound = True
                
                
                
                def handle_endtag(self, tag):
                    self.HTML += (f"</{tag}>")

                    if(self.keywordFound):
                        return

                    if(self.abstractFound and tag == "p"):
                        self.abstractFound = False
                    if(self.paragraphFound and tag == "div" and self.paragraphDivCount == 1):
                        self.paragraphFound = False
                        self.paragraphDivCount -= 1
                    elif(self.paragraphFound and tag == "div" and self.paragraphDivCount > 1):
                        self.paragraphDivCount -= 1
 


            tableParser = TableParser()
            tableParser.feed(articleResponse.text)
            
            if(tableParser.keywordFound):
                outputFile.write(tableParser.HTML)
            else:
                print(address)

        fileId += 1
    keyWordId += 1