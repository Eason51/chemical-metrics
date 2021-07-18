import requests
from html.parser import HTMLParser

def all_to_json(targetName):
    
    ACSUrl = ACS.prepare_query_url(targetName)

    (paper_count, queryResponse) = ACS.get_article_amount_and_response(ACSUrl)

    addressArr =  ACS.get_article_URLs(queryResponse)

    (dateArr, tableAdressArr, drug_molecule_count) = ACS.get_drug_molecule_paper(addressArr)





# Parsers cannot exit from inside, the reset() method needs to be called from outside
def exitParser(parser):
    parser.reset()

    
class ACS:

    DOMAIN = "https://pubs.acs.org"
    
    class AmountParser(HTMLParser): 
        def __init__(self):
            HTMLParser.__init__(self)
            self.tagFound = False
            self.articleTotalAmount = 0

        def handle_starttag(self, tag, attrs):
            if (tag == "span" and len(attrs) == 1 and attrs[0][1] == "result__count"):
                self.tagFound = True
        
        def handle_data(self, data):
            if(self.tagFound):
                self.articleTotalAmount = int(data)
                exitParser(self)

    
    class QueryParser(HTMLParser): 
        
        hasNextPage = True
        nextPageURL = ""
        
        def __init__(self):
            HTMLParser.__init__(self)
            self.articleTagFound = False

            self.pageListFound = False
            self.nextButtonFound = False

            self.addressArr = []


        def handle_starttag(self, tag, attrs):
            if (tag == "h2" and len(attrs) == 1 and attrs[0][1] == "issue-item_title"):
                self.articleTagFound = True
            elif (self.articleTagFound and tag == "a"):
                self.addressArr.append(ACS.DOMAIN + attrs[0][1])
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
                        ACS.QueryParser.nextPageURL = attr[1]
        

        def handle_endtag(self, tag):
            if(self.pageListFound and tag == "nav"):
                self.pageListFound = False
                self.nextButtonFound = False
                ACS.QueryParser.hasNextPage = False



    def prepare_query_url(targetName):
        
        keyWord = targetName
        URL = ""
        queryString = ""
        for word in keyWord.split():
            if(not queryString):
                queryString += word
            else:
                queryString += f"+{word}"
        URL = f"https://pubs.acs.org/action/doSearch?field1=AllField&text1={queryString}&field2=AllField&text2=&ConceptID=&ConceptID=&publication=&publication%5B%5D=jmcmar&accessType=allContent&Earliest="

        return URL 
    
    
    def get_article_amount_and_response(URL):

        response = requests.get(URL, headers = {"User-Agent": "Mozilla/5.0"})
        try:
            amountParser = ACS.AmountParser()
            amountParser.feed(response.text)
        except AssertionError as ae:
            pass
        
        return (amountParser.articleTotalAmount, response)

    
    def get_article_URLs(response):

        queryParser = ACS.QueryParser()
        queryParser.feed(response.text)
        while(ACS.QueryParser.hasNextPage):
            response = requests.get(ACS.QueryParser.nextPageURL, headers = {"User-Agent": "Mozilla/5.0"})
            queryParser.feed(response.text)

        return queryParser.addressArr


    

    class ContentParser(HTMLParser): 
        
        dateArr = []
        tableAdressArr = []
        drugPaperCount = 0
        
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
                    ACS.ContentParser.drugPaperCount += 1
                    exitParser(self)
                    self.complete = True
                elif(self.ICFound):
                    if(len(data) >= 2 and data[:2] == "50"):
                        ACS.ContentParser.drugPaperCount += 1
                        exitParser(self)
                        self.complete = True
                    else:
                        self.ICFound = False
                elif(len(data) >= 2 and (data.lower()[-2:] in ["ic", "ec", "ki", "kd", "ed"])):
                    self.ICFound = True
            
            elif(self.dateFound):
                self.date = data.split()[-1]
            elif(self.titleFound):
                if(data.lower() in "references"):
                    exitParser(self)

        
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
    

    def get_drug_molecule_paper(addressArr):
        oldAmount2 = ACS.ContentParser.drugPaperCount
        for address in addressArr:
            try:
                contentParser = ACS.ContentParser.ContentParser()
                articleResponse = requests.get(address, headers = {"User-Agent": "Mozilla/5.0"})
                contentParser.feed(articleResponse.text)
            except AssertionError as ae:
                pass

            if(ACS.ContentParser.drugPaperCount > oldAmount2):
                ACS.ContentParser.tableAddressArr.append(address)

                found = False
                for yearOccur in ACS.ContentParser.dateArr:
                    if (yearOccur[0] == contentParser.date):
                        found = True
                        yearOccur[1] += 1
                        break
                if(not found):
                    ACS.ContentParser.dateArr.append([contentParser.date, 1])  
                
                oldAmount2 = ACS.ContentParser.drugPaperCount
        
        return (ACS.ContentParser.dateArr, ACS.ContentParser.tableAdressArr, ACS.ContentParser.drugPaperCount)













