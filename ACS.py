import requests
from html.parser import HTMLParser
import sys

AMOUNT = 0
AMOUNT2 = 0
addressArr = []
tableAddressArr = []
DOMAIN = "https://pubs.acs.org"
# (year, occurrence)
dateArr = []


class ParserHandler:
    def resetParser(parser):
        parser.reset()


class AmountParser(HTMLParser): 
    def __init__(self):
        HTMLParser.__init__(self)
        self.tagFound = False

    def handle_starttag(self, tag, attrs):
        if (tag == "span" and len(attrs) == 1 and attrs[0][1] == "result__count"):
            self.tagFound = True
    
    def handle_data(self, data):
        if(self.tagFound):
            AmountParserHandler.tagFound(self, data)

class AmountParserHandler:
    def tagFound(parser, data):
        global AMOUNT
        AMOUNT = int(data)
        global AMOUNT2
        AMOUNT2 = 0
        ParserHandler.resetParser(parser)




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
        




class ContentParser(HTMLParser): 
    def __init__(self):
        HTMLParser.__init__(self)
        self.contentFound = False
        self.ICFound = False
        self.complete = False

        self.dateRowFound = False
        self.dateFound = False
        self.date = ""
        
        self.titleFound = False


    def handle_starttag(self, tag, attrs):
        if (self.complete):
            return
        elif (tag == "div" and len(attrs) == 1 and attrs[0][1] == "NLM_p"):
            self.contentFound = True
        elif (tag == "div" and len(attrs) == 1 and attrs[0][1] == "article_header-epubdate"):
            self.dateRowFound = True
        elif (self.dateRowFound and len(attrs) == 1 and attrs[0][1] == "pub-date-value"):
            self.dateFound = True
        elif (tag == "div" and len(attrs) == 1 and attrs[0][1] == "article_content-title"):
            self.titleFound = True

    
    def handle_data(self, data):
        if (self.complete):
            return
        
        global AMOUNT2
        if(self.contentFound):
            stringList = ["ic50", "ec50", "ki50", "kd50", "ed50"]            
            if(any(substring in data.lower() for substring in stringList)):
                AMOUNT2 += 1
                ParserHandler.resetParser(self)
                self.complete = True
            elif(self.ICFound):
                if(len(data) >= 2 and data[:2] == "50"):
                    AMOUNT2 += 1
                    ParserHandler.resetParser(self)
                    self.complete = True
                else:
                    self.ICFound = False
            elif(len(data) >= 2 and (data.lower()[-2:] in ["ic", "ec", "ki", "kd", "ed"])):
                self.ICFound = True
        
        elif(self.dateFound):
            self.date = data.split()[-1]
        elif(self.titleFound):
            if(data.lower() in "references"):
                ParserHandler.resetParser(self)

    
    def handle_endtag(self, tag):
        if(self.complete):
            return
        elif(self.contentFound and tag == "div"):
            self.contentFound = False
        elif(self.dateRowFound and tag == "div"):
            self.dateRowFound = False
        elif(self.dateFound and tag == "span"):
            self.dateFound = False
        elif(self.titleFound and tag == "div"):
            self.titleFound = False




class TableParser(HTMLParser): 
    def __init__(self):
        HTMLParser.__init__(self)

        self.content = ""

        self.tableFound = False
        self.headerFound = False
        self.headerContent = ""
        self.headerRowFound = False
        self.firstTitle = False
        
        self.tableBody = False
        self.bodyRow = False
        self.firstColumn = False
        self.columnContent = []

        self.compoundSet = set()

        self.titleFound = False


    def handle_starttag(self, tag, attrs):
        # if(self.tableFound):
        #     self.content += (self.get_starttag_text())
        if (tag == "div"):
            for attr in attrs:
                if(attr[0] == "class" and attr[1] == "scrollable-table-wrap"):
                    self.tableFound = True
                    # self.content = (self.get_starttag_text())
        elif (self.tableFound and tag == "thead"):
            self.headerFound = True
        elif (self.headerFound and tag == "tr"):
            self.headerContent = ""
            self.headerRowFound = True
        elif (self.headerRowFound and tag == "th"):
            self.firstTitle = True
        
        elif (self.tableFound and tag == "tbody"):
            self.tableBody = True 
        elif (self.tableBody and tag == "tr"):
            self.bodyRow = True 
        elif (self.bodyRow and tag == "td"):
            self.firstColumn = True
        elif (tag == "div" and len(attrs) == 1 and attrs[0][1] == "article_content-title"):
            self.titleFound = True          

    
    def handle_data(self, data):
        # if(self.tableFound):
        #     self.content += data
        if(self.firstTitle):
            self.headerContent = data
            self.firstTitle = False
            self.headerRowFound = False
        elif(self.firstColumn):
            if(not data.isspace()):
                self.columnContent.append(data)
            self.firstColumn = False
            self.bodyRow = False
        elif(self.titleFound):
            if(data.lower() in "references"):
                ParserHandler.resetParser(self)
    

    def handle_endtag(self, tag):
        if(self.tableFound and tag == "div"):
            
            self.tableFound = False
            # self.content += ("</div>")
            # self.content += ("<br><br>")

            compoundFound = False
            nameList = ["compound", "no", "id", "compd", "cpd", "cmp"]
            if(self.headerContent.lower() in nameList):
                compoundFound = True
            for name in nameList:
                if (name in self.headerContent.lower()):
                    compoundFound = True
                    break
            
            if (not compoundFound):
                for name in self.columnContent:
                    if(name.isnumeric()):
                        compoundFound = True
                        break
                    elif(len(name) > 1 and name[:-2].isnumeric() and name[-1].isalpha()):
                        compoundFound = True
                        break

            # if (not compoundFound):
            #     outputFile.write(self.content)
            if(compoundFound):
                for name in self.columnContent:
                    self.compoundSet.add(name)
            self.columnContent.clear()
        elif(self.headerRowFound and tag == "tr"):
            self.headerRowFound = False            
        # elif(self.tableFound):
        #     self.content += (f"</{tag}>")
        elif(self.tableFound and tag == "thead"):
            self.headerFound = False
        elif(self.tableFound and tag == "tbody"):
            self.tableBody = False
        elif (self.tableBody and tag == "tr"):
            self.bodyRow = False 
        elif (self.bodyRow and tag == "td"):
            self.firstColumn = False
        elif(self.titleFound and tag == "div"):
            self.titleFound = False




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




for URL in URLs:
    addressArr.clear()
    QueryParserHandler.hasNextPage = True
    response = requests.get(URL[1], headers = {"User-Agent": "Mozilla/5.0"})
    try:
        parser = AmountParser()
        parser.feed(response.text)
    except AssertionError as ae:
        pass
    
    print(f"""
    {URL[0]} in Journal of Medicinal Chemistry:
        {AMOUNT}
    """)

    queryParser = QueryParser()
    queryParser.feed(response.text)
    while(QueryParserHandler.hasNextPage):
        response = requests.get(QueryParserHandler.nextPageURL, headers = {"User-Agent": "Mozilla/5.0"})
        queryParser.feed(response.text)

    dateArr.clear()
    oldAmount2 = AMOUNT2
    for address in addressArr:
        try:
            contentParser = ContentParser()
            articleResponse = requests.get(address, headers = {"User-Agent": "Mozilla/5.0"})
            contentParser.feed(articleResponse.text)
        except AssertionError as ae:
            pass

        if(AMOUNT2 > oldAmount2):
            tableAddressArr.append(address)

            found = False
            for yearOccur in dateArr:
                if (yearOccur[0] == contentParser.date):
                    found = True
                    yearOccur[1] += 1
                    break
            if(not found):
                dateArr.append([contentParser.date, 1])  
            
            oldAmount2 = AMOUNT2

    
    print(f"""
    {URL[0]} in Journal of Medicinal Chemistry with ["ic", "ec", "ki", "kd", "ed"]50 keywords:
        {AMOUNT2}
    """)

    print("\n\n (year, occurrence) pairs: ")
    dateArr.sort()
    for pair in dateArr:
        print(tuple(pair))
    print("\n\n")

    AMOUNT = 0
    AMOUNT2 = 0



#tableAddressArr = []

# with open("table.txt") as linkFile:
#     for line in linkFile:
#         tableAddressArr.append(line)
    


    print(f"tableArticles: {len(tableAddressArr)}")


    for tableAddress in tableAddressArr:
        response = requests.get(tableAddress, headers = {"User-Agent": "Mozilla/5.0"})
        print(f"\n\narticle address: {tableAddress}\n\n")
        tableParser = TableParser()
        tableParser.feed(response.text)
        print(f"number of compounds: {len(tableParser.compoundSet)}")
