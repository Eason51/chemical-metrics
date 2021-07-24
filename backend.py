import requests
from html.parser import HTMLParser
from chemdataextractor import Document
import easyocr
import json
from elsapy.elsclient import ElsClient
from elsapy.elsdoc import FullDoc







# Parsers cannot exit from inside, the reset() method needs to be called from outside
def exitParser(parser):
    parser.reset()


# identify whether a string is "ic50", OCR result could be "icso", "icSo" etc.
def ic50(string):
    string = string.lower()
    pos = string.find("ic")
    if(pos == -1):
        return False
    
    pos += 2
    if(pos >= len(string)):
        return False
    if not(string[pos] == "5" or string[pos] == "s" or string[pos] == "S"):
        return False
    pos += 1
    if(pos >= len(string)):
        return False
    if not (string[pos] == "0" or string[pos] == "O" or string[pos] == "o"):
        return False
    return True


# identify whether a string is in the form of a compound name, pure number like 18, or number followed by letter like 18ae
def compoundName(string):
    if(string == ""):
        return False
    string = string.lower().strip()
    for c in string:
        if(c.isspace()):
            return False
    if(string.isdigit()):
        return True
    if(len(string) >= 2 and string[0].isdigit()):
        onlyDigit = True
        for c in string:
            if(not onlyDigit and not c.isalpha()):
                return False
            if(onlyDigit and not c.isdigit()):
                onlyDigit = False
        return True
    return False


# identify whether a string is in the form of a molecule name, either pure letters, or contains numbers with dash("-")
def moleculeName(string):
    string = string.lower().strip()
    if(string.isalpha()):
        return True
    hasNumber = False
    hasDash = False
    for letter in string:
        if(letter.isdigit()):
            hasNumber = True
        elif(letter == "-"):
            hasDash = True
    if(hasNumber and not hasDash):
        return False
    return True



class BodyText:
    
    class Section:
        
        class Paragraph:
            def __init__(self, header = ""):
                self.header = header
                self.contents = [] # list[str]
                self.boldContents = []
        
        def __init__(self, title):
            self.title = title
            self.paragraphs = [] # list[self.Paragraph]
    
    def __init__(self):
        self.sections = [] # list[self.Section]


class Table:

    class Grid:

        class Row:

            def __init__(self):
                # a cell may hold empty string, if html element is "&nbsp"
                self.cells = [] # list[str]

        def __init__(self):
            self.columnNum = 0
            self.header = [] # list[self.Row]
            self.body = [] # list[self.Row]

    def __init__(self):
        self.caption = ""
        self.descriptions = [] # list[str]
        self.grid = self.Grid()



# --------------------------------------------------------------------------------------------------------------
class ACS:

    DOMAIN = "https://pubs.acs.org"
    TARGET = ""
    


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



    class ContentParser(HTMLParser): 
        
        dateArr = []
        tableAddressArr = []
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

            self.abstractFound = False
            self.figureFound = False
            self.figureLinkFound = False



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
            if(tag == "div" and len(attrs) >= 1):
                for attr in attrs:
                    if (attr[0] == "class" and attr[1] == "article_abstract-content hlFld-Abstract"):
                        self.abstractFound = True
                        break
            if(self.figureFound and tag == "figure"):
                self.figureFound = True
            if(self.figureFound and tag == "a" and len(attrs) >= 2):
                title = link = ""
                for attr in attrs:
                    if(attr[0] == "title"):
                        title = attr[1]
                if(title == "High Resolution Image"):
                    self.figureLinkFound = True
            if(tag == "div" and len(attrs) == 1 and attrs[0][1] == "article_content-title"):
                if(not self.figureLinkFound):
                    exitParser(self)
            

        
        def handle_data(self, data):
            if (self.complete):
                return
            
            if(self.contentFound):
                stringList = ["IC50", "EC50", "ED50"]            
                if(any(substring in data for substring in stringList)):
                    ACS.ContentParser.drugPaperCount += 1
                    exitParser(self)
                    self.complete = True
                elif(any(substring in data for substring in stringList)):
                    index = data.find("Ki")
                    if(index == -1):
                        index = data.find("Kd")
                    if(index == -1):
                        return
                    keywordFound = False
                    if((index + 2) >= len(data)):
                        keywordFound = True
                    else:
                        if(not data[index + 2].isalpha()):
                            keywordFound = True
                    if(keywordFound):
                        ACS.ContentParser.drugPaperCount += 1
                        exitParser(self)
                elif(self.ICFound):
                    if(len(data) >= 2 and data[:2] == "50"):
                        ACS.ContentParser.drugPaperCount += 1
                        exitParser(self)
                        self.complete = True
                    else:
                        self.ICFound = False
                elif(len(data) >= 2 and (data[-2:] in ["IC", "EC", "ED"])):
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

# --------------------------------------------------------------------------------------------------------------

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



    def get_drug_molecule_paper(addressArr):
        oldAmount2 = ACS.ContentParser.drugPaperCount
        for address in addressArr:
            try:
                contentParser = ACS.ContentParser()
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
        
        ACS.ContentParser.dateArr.sort()
        return (ACS.ContentParser.dateArr, ACS.ContentParser.tableAddressArr, ACS.ContentParser.drugPaperCount)



# --------------------------------------------------------------------------------------------------------------


    
    class ACSArticle:        
        

        # Parse the reponse from online enquiry and store useful information
        class TargetParser(HTMLParser):
            def __init__(self):
                HTMLParser.__init__(self)

                self.tableFound = False
                self.resultFound = False
                # the returned abbreviation or full name
                self.result = ""
                self.columnNum = 0
                self.frequencyFound = False
                # frequency of occurrence of self.result found in database
                self.frequency = 0

            
            def handle_starttag(self, tag, attrs):
                if(tag == "table"):
                    self.tableFound = True
                if(tag == "table" and len(attrs) > 0):
                    for attr in attrs:
                        if(attr[0] == "class" and attr[1] == "sortable"):
                            self.resultFound = True
                if(self.resultFound and tag == "td"):
                    self.columnNum += 1
                if(self.columnNum == 2 and tag == "div"):
                    exitParser(self)
                if(self.columnNum == 2 and tag == "br"):
                    self.frequencyFound = True

            
            def handle_data(self, data):
                if(self.frequencyFound):
                    frequencyStr = ""
                    for c in data:
                        if(c.isdigit()):
                            frequencyStr += c
                    self.frequency = int(frequencyStr)
                    return
                if(self.columnNum == 2):
                    self.result += data
                if(self.tableFound):
                    if("not found" in data):
                        exitParser(self)

            
            def handle_endtag(self, tag):
                if(self.resultFound and tag == "table"):
                    self.resultFound = False
                if(self.tableFound and tag == "table"):
                    self.tableFound = False



# parsing a html file
# --------------------------------------------------------------------------------------------------------------
        class TableParser(HTMLParser):
            def __init__(self):
                HTMLParser.__init__(self)

                self.authorArr = []
                self.year = -1
                self.institution = []
                self.paperCited = -1
                self.doi = ""
                self.journal = ""

                self.authorFound = False
                self.dateFound = False
                self.institutionFound = False
                self.citationFound = False
                self.citationDivCount = 0
                self.citationNumber = False
                self.doiFound = False
                self.doiLink = False
                self.journalFound = False
                self.journalName = False



                # enable this flag to skip handle_data for the next element
                self.disableRead = False

                # the link(s) to access abstract image
                self.imgArr = []
                # complete abstract text content
                self.abstractText = ""
                self.abstractBoldText = ""
                # all elements in abstract text in bold (<b></b>)
                self.boldAbstractTextArr = []

                self.abstractFound = False
                self.figureFound = False
                self.imgLinkFound = False
                self.textFound = False
                self.boldTextFound = False

                self.titleFound = False
                self.titleText = False
                self.title = ""

                # a BodyText object to hold the content of body text
                self.bodyText = BodyText()
                self.newSectionFound = False
                self.sectionTitleFound = False
                self.paragraphFound = False
                self.paragraphDivCount = 0
                # hold the content of the paragraph currently being parsed
                self.paragraphText = ""
                self.paragraphHeaderFound = False
                # hold the title for the currently parsed paragraph (could be empty)
                self.paragraphHeader = ""
                self.paragraphBoldFound = False
                self.paragraphBoldText = ""

                # hold all the Table objects contained in the current article
                self.tables = [] # list[Table]
                self.tableFound = False
                self.tableDivCount = 0
                self.tableCaptionFound = False
                self.tableCaptionDivCount = 0
                # hold the caption of the table currently being parsed
                self.tableCaption = ""

                self.tableGridFound = False
                self.tableColCountFound = False
                self.gridHeaderFound = False
                self.cellFound = False
                self.gridBodyFound = False
                # hold the content of the current parsing cell
                self.cell = ""
                self.cellSpace = False

                self.tableDescriptionFound = False
                self.tableDescriptionDivCount = 0
                self.tableFootnoteFound = False
                


            def handle_starttag(self, tag, attrs):

                if(tag == "span" and len(attrs) == 1 and attrs[0][1] == "hlFld-ContribAuthor"):
                    self.authorFound = True
                if(tag == "span" and len(attrs) == 1 and attrs[0][1] == "pub-date-value"):
                    self.dateFound = True
                if(tag == "span" and len(attrs) == 1 and attrs[0][1] == "aff-text"):
                    self.institutionFound = True
                    self.institution.append("")
                if(tag == "div" and len(attrs) == 1 and attrs[0][1] == "articleMetrics_count"):
                    self.citationFound = True
                    self.citationDivCount += 1
                elif(self.citationFound and tag == "div"):
                    self.citationDivCount += 1
                if(self.citationFound and tag == "a"):
                    self.citationNumber = True
                if(tag == "div" and len(attrs) == 1 and attrs[0][1] == "article_header-doiurl"):
                    self.doiFound = True
                if(self.doiFound and tag == "a"):
                    self.doiLink = True
                if(not self.journalFound and tag == "input" and len(attrs) > 0):
                    value = ""
                    for attr in attrs:
                        if(attr[0] == "name" and attr[1] == "journalNameForjhpLink"):
                            self.journalFound = True
                        elif(attr[0] == "value"):
                            value = attr[1]
                    if(self.journalFound and value):
                        self.journal = value



                # handle title, abstract image and abstract text

                if(tag == "div" and len(attrs) >= 1):
                    for attr in attrs:
                        if (attr[0] == "class" and attr[1] == "article_abstract-content hlFld-Abstract"):
                            self.abstractFound = True
                            break
                if(tag == "div" and len(attrs) == 1 and attrs[0][1] == "article_content"):
                    self.abstractText += " . "
                    self.abstractBoldText += " . "
                    self.abstractFound = False
                if(self.abstractFound and tag == "figure"):
                    self.figureFound = True
                if(self.figureFound and tag == "a" and len(attrs) >= 2):
                    title = link = ""
                    for attr in attrs:
                        if(attr[0] == "title"):
                            title = attr[1]
                        elif(attr[0] == "href"):
                            link = ACS.DOMAIN + attr[1]
                    if(title == "High Resolution Image"):
                        self.imgArr.append(link)
                if(self.abstractFound and tag == "p" and len(attrs) == 1 and attrs[0][1] == "articleBody_abstractText"):
                    self.textFound = True
                if(tag == "h1" and len(attrs) == 1 and attrs[0][1] == "article_header-title"):
                    self.titleFound =True
                if(self.titleFound and tag == "span"):
                    self.titleText = True
                if(self.textFound and tag == "b"):
                    self.boldTextFound = True
                    self.abstractBoldText += "<b>"

                #handle body text
                
                if(tag == "div" and len(attrs) == 1 and attrs[0][1] == "article_content-title"):
                    self.sectionTitleFound = True
                    self.newSectionFound = True
                if(tag == "div" and len(attrs) == 1 and "NLM_p" in attrs[0][1]):
                    self.paragraphFound = True
                    self.paragraphDivCount += 1
                elif(self.paragraphFound and tag == "div"):
                    self.paragraphDivCount += 1
                if(tag == "h3" and len(attrs) > 0):
                    for attr in attrs:
                        if(attr[0] == "class" and attr[1] == "article-section__title"):
                            self.paragraphHeaderFound = True
                if(self.paragraphFound and tag == "b"):
                    self.paragraphBoldFound = True
                    self.paragraphBoldText += "<b>"

                # handle table caption
                
                if(tag == "div" and len(attrs) > 1):
                    for attr in attrs:
                        if(attr[0] == "class" and attr[1] == "NLM_table-wrap"):
                            self.tableFound = True
                            self.tableDivCount += 1
                            self.tables.append(Table())
                            return
                if(self.tableFound and tag == "div"):
                    self.tableDivCount += 1
                if(self.tableFound and tag == "div" and len(attrs) > 0):
                    for attr in attrs:
                        if(attr[0] == "class" and attr[1] == "NLM_caption"):
                            self.tableCaptionFound = True
                            self.tableCaptionDivCount += 1
                            return
                if(self.tableCaptionFound and tag == "div"):
                    self.tableCaptionDivCount += 1
                if(self.tableCaptionFound and tag == "a"):
                    self.disableRead = True
                
                # handle table grid
                
                if(self.tableFound and tag == "table"):
                    self.tableGridFound = True
                if(self.tableGridFound and tag == "colgroup"):
                    self.tableColCountFound = True
                if(self.tableColCountFound and tag == "col"):
                    self.tables[-1].grid.columnNum += 1
                if(self.tableGridFound and tag == "thead"):
                    self.gridHeaderFound = True
                if(self.gridHeaderFound and tag == "tr"):
                    self.tables[-1].grid.header.append(Table.Grid.Row())
                if(self.gridHeaderFound and tag == "th"):
                    self.cellFound = True
                if(self.tableGridFound and tag == "tbody"):
                    self.gridBodyFound = True
                if(self.gridBodyFound and tag == "tr"):
                    self.tables[-1].grid.body.append(Table.Grid.Row())
                if(self.gridBodyFound and tag == "td"):
                    self.cellFound = True
                if(self.cellFound and tag == "sup"):
                    self.cellSpace = True
                if(self.cellFound and tag == "br"):
                    self.cell += " "
                
                # handle table description
                
                if(self.tableFound and (not self.tableCaptionFound) and (not self.tableGridFound) and tag == "div" and len(attrs) > 0):
                    for attr in attrs:
                        if(attr[0] == "class" and attr[1] == "NLM_table-wrap-foot"):
                            self.tableDescriptionFound = True
                            self.tableDescriptionDivCount += 1
                            return
                if(self.tableDescriptionFound and tag == "div"):
                    self.tableDescriptionDivCount += 1
                if(self.tableDescriptionFound and tag == "div" and len(attrs) > 0):
                    for attr in attrs:
                        if(attr[0] == "class" and attr[1] == "footnote"):
                            self.tableFootnoteFound = True
                            self.tables[-1].descriptions.append("")
                if(self.tableFootnoteFound and tag in ["sup", "a"]):
                    self.disableRead = True



            def handle_data(self, data):
                if(self.disableRead):
                    return
                if(self.cellSpace):
                    self.cell += " "
                    return
                
                if(self.authorFound):
                    self.authorArr.append(data)
                if(self.dateFound):
                    index = data.find(",")
                    self.year = int(data[index + 1 :].strip())
                if(self.institutionFound):
                    self.institution[-1] += data
                if(self.citationNumber):
                    self.paperCited = int(data)
                if(self.doiLink):
                    index = data.find("https://doi.org/")
                    if(index != -1):
                        self.doi = data[16:]


                # handle title and abstract

                if(self.textFound):
                    self.abstractText += data
                    self.abstractBoldText += data
                if(self.titleText):
                    self.title += data
                if(self.boldTextFound):
                    self.boldAbstractTextArr.append(data)
                
                # handle body text

                # found a new section, append the section to bodyText
                if(self.newSectionFound):
                    section = BodyText.Section(data)
                    self.bodyText.sections.append(section)
                    self.newSectionFound = False
                    # ignore any content after references
                    if(data == "References"):
                        exitParser(self)
                if(self.paragraphFound):
                    self.paragraphText += data
                    self.paragraphBoldText += data
                if(self.paragraphHeaderFound):
                    self.paragraphHeader += data

                # handle Tables

                if(self.tableCaptionFound):
                    self.tableCaption += data
                if(self.gridHeaderFound and self.cellFound):
                    self.cell += data            
                if(self.gridBodyFound and self.cellFound):
                    self.cell += data
                if(self.tableFootnoteFound):
                    self.tables[-1].descriptions[-1] += data

            
            def handle_endtag(self, tag):

                if(self.authorFound and tag == "span"):
                    self.authorFound = False
                if(self.dateFound and tag == "span"):
                    self.dateFound = False
                if(self.institutionFound and tag == "span"):
                    self.institutionFound = False
                if(self.citationFound and tag == "div" and self.citationDivCount == 1):
                    self.citationDivCount -= 1
                    self.citationFound = False
                elif(self.citationFound and tag == "div" and self.citationDivCount > 1):
                    self.citationDivCount -= 1
                if(self.citationNumber and tag == "a"):
                    self.citationNumber = False
                if(self.doiFound and tag == "div"):
                    self.doiFound = False
                if(self.doiLink and tag == "a"):
                    self.doiLink = False


                # handle title and abstract
                
                if(self.disableRead):
                    self.disableRead = False
                if(self.cellSpace):
                    self.cellSpace = False
                if(self.figureFound and tag == "figure"):
                    self.figureFound = False
                if(self.textFound and tag == "p"):
                    self.textFound = False
                if(self.titleFound and tag == "h1"):
                    self.titleFound = False
                if(self.titleText and tag == "span"):
                    self.titleText = False
                if(self.boldTextFound and tag == "b"):
                    self.boldTextFound = False
                    self.abstractBoldText += "</b>"
                
                # handle body text
                
                if(self.sectionTitleFound and tag == "div"):
                    self.sectionTitleFound = False
                # found the end of a paragraph, append the content to the last section
                if(self.paragraphFound and tag == "div" and self.paragraphDivCount == 1):
                    if(len(self.bodyText.sections[-1].paragraphs) == 0):
                        newParagraph = BodyText.Section.Paragraph()
                        self.bodyText.sections[-1].paragraphs.append(newParagraph)
                    self.bodyText.sections[-1].paragraphs[-1].contents.append(self.paragraphText)
                    self.paragraphText = ""
                    self.paragraphFound = False
                    self.paragraphDivCount -= 1
                elif(self.paragraphFound and tag == "div" and self.paragraphDivCount > 1):
                    self.paragraphDivCount -= 1
                # found a paragraph header, append a new paragraph with header to the last section
                if(self.paragraphHeaderFound and tag == "h3"):
                    self.paragraphHeaderFound = False
                    newParagraph = BodyText.Section.Paragraph(self.paragraphHeader)
                    self.bodyText.sections[-1].paragraphs.append(newParagraph)
                    self.paragraphHeader = ""
                if(self.paragraphBoldFound and tag == "b"):
                    self.paragraphBoldText += "</b>"
                    self.paragraphBoldText = ""
                    self.paragraphBoldFound = False
                
                # handle table caption

                if(self.tableFound and tag == "div" and self.tableDivCount == 1):
                    self.tableFound = False
                    self.tableDivCount -= 1
                elif(self.tableFound and tag == "div" and self.tableDivCount > 1):
                    self.tableDivCount -= 1
                if(self.tableCaptionFound and tag == "div" and self.tableCaptionDivCount == 1):
                    self.tableCaptionFound = False
                    self.tableCaptionDivCount -= 1
                    self.tables[-1].caption = self.tableCaption
                    self.tableCaption = ""
                elif(self.tableCaptionFound and tag == "div" and self.tableCaptionDivCount > 1):
                    self.tableCaptionDivCount -= 1
                
                # handle table grip

                if(self.tableGridFound and tag == "table"):
                    self.tableGridFound = False
                if(self.tableColCountFound and tag == "colgroup"):
                    self.tableColCountFound = False
                if(self.gridHeaderFound and tag == "thead"):
                    self.gridHeaderFound = False
                if(self.gridHeaderFound and tag == "th" and self.cellFound):
                    self.tables[-1].grid.header[-1].cells.append(self.cell)
                    self.cell = ""
                    self.cellFound = False
                if(self.gridBodyFound and tag == "tbody"):
                    self.gridBodyFound = False
                if(self.gridBodyFound and tag == "td" and self.cellFound):
                    self.tables[-1].grid.body[-1].cells.append(self.cell)
                    self.cell = ""
                    self.cellFound = False

                # handle table description

                if(self.tableDescriptionFound and self.tableDescriptionDivCount == 1 and tag == "div"):
                    self.tableDescriptionDivCount -= 1
                    self.tableDescriptionFound = False
                elif(self.tableDescriptionFound and tag == "div" and self.tableDescriptionDivCount > 1):
                    self.tableDescriptionDivCount -= 1
                if(self.tableFootnoteFound and tag == "div"):
                    self.tableFootnoteFound = False





# --------------------------------------------------------------------------------------------------------------
        def __init__(self, articleURL):

            self.articleURL = articleURL

            self.authorArr = []
            self.year = -1
            self.instituition = ""
            self.paperCited = -1
            self.doi = ""
            self.journal = ""
            
            # fullname and abbreviation is used in ic50 extraction in abstract image
            # stores the fullname of the target gene, omit number, e.g. if target is "jak1", fullname is "janus kinase"
            self.FULLNAME = ""
            # stores the abbreviation of the target gene, omit number, e.g. if target is "jak1", abbreviation is "jak"
            self.ABBREVIATION = ""
            # Target name of the article's focus
            self.focusedTarget = ""


            self.tableParser = None            
            # hold title content after parsing html file
            self.titleText = ""
            # hold links to abstract images after parsing html file
            self.imgArr = []
            # hold abstract content after parsing html file
            self.abstractText = ""

            # BodyText object for holding body text
            self.bodyText = None
            # Table object for holding tables
            self.tables = None



            # hold the molecule name
            self.molecule = ""
            # hold the compound name
            self.compound = ""
            # hold the ic50 value
            self.ic50Value = ""


            # Arr variables provide additional and alternative information, in case the identified molecule, compound, ic50value are incorrect

            # hold all identified molecule names
            self.moleculeArr = []
            # hold all identified compound names
            self.compoundArr = []
            # hold all identified ic50 values
            self.ic50Arr = []

            self.enzymeKeywords = [self.ABBREVIATION, self.FULLNAME, "enzyme", "enzymatic"]
            self.cellKeywords = ["cell", "cellar"]
            self.compoundKeywords = ["compound", "no", "id", "compd", "cpd", "cmp"]

            self.enzymeIc50 = ""
            self.cellIc50 = ""
            self.enzymeKi = ""
            self.cellKi = ""
            self.enzymeKd = ""
            self.cellKd = ""
            self.enzymeSelectivity = ""
            self.cellSelectivity = ""
            self.cellSolubility = ""
            self.vivoSolubility = ""
            self.ec50 = ""
            self.ed50 = ""
            self.auc = ""
            self.herg = ""


            self.retrieve_values()




        def retrieve_values(self):

            self.get_FULLNAME_ABBREVIATION()
            self.retrieve_article_information()
            self.retrieve_target()

            positionResult = self.retrieve_image_text()
            self.get_ic50_from_image(positionResult)
            self.get_compound_from_image(positionResult)
            self.get_molecule_from_title_abstract()
            self.get_compound_from_abstract()
            self.get_ic50_from_abstract()
            self.get_ic50_from_body()
            self.get_kikd_from_body()
            self.get_single_value_from_body()
        


        def get_FULLNAME_ABBREVIATION(self):
            
            # trim the number at the end of TARGET
            i = len(ACS.TARGET) - 1
            while(i >= 0):
                if(not ACS.TARGET[i].isalpha()):
                    i -= 1
                else:
                    break
            queryTarget = ACS.TARGET[:i + 1]

            # target name identification is performed through an online database: http://allie.dbcls.jp/
            # at this point, the user might input a fullname or an abbreviation, so it needs to be queried twice

            # queryLongUrl: treat the input as a fullname, find abbreviation
            queryLongUrl = f"https://allie.dbcls.jp/long/exact/Any/{queryTarget.lower()}.html"
            # queryShortUrl: treat the input as an abbreviation, find fullname
            queryShortUrl = f"https://allie.dbcls.jp/short/exact/Any/{queryTarget.lower()}.html"

            longResponse = requests.get(queryLongUrl)
            shortReponse = requests.get(queryShortUrl)

            longParser = ACS.ACSArticle.TargetParser()
            shortParser = ACS.ACSArticle.TargetParser()
            try:
                longParser.feed(longResponse.text)    
            except AssertionError as ae:
                pass

            try:
                shortParser.feed(shortReponse.text)
            except AssertionError as ae:
                pass

            longForm = shortParser.result.lower().strip()
            longFrequency = shortParser.frequency
            shortForm = longParser.result.lower().strip()
            shortFrequency = longParser.frequency

            # if the input is a full name, shortFrequency will be 0, the input will be FULLNAME, vice versa.
            if(shortFrequency > longFrequency):
                self.FULLNAME = queryTarget
                self.ABBREVIATION = shortForm
            else:
                self.FULLNAME = longForm
                self.ABBREVIATION = queryTarget



        def retrieve_article_information(self):
            self.tableParser = ACS.ACSArticle.TableParser()
            # open a file locally, should be retrieved through http request in real programs
            response = requests.get(self.articleURL)

            # parse the given html file with TableParser()
            try:
                self.tableParser.feed(response.text)
            except AssertionError as ae:
                pass
            
            self.titleText = self.tableParser.title
            self.imgArr = self.tableParser.imgArr
            self.abstractText = self.tableParser.abstractText
            self.bodyText = self.tableParser.bodyText
            self.tables = self.tableParser.tables
            self.authorArr = self.tableParser.authorArr
            self.year = self.tableParser.year
            self.instituition = self.tableParser.institution
            self.paperCited = self.tableParser.paperCited
            self.doi = self.tableParser.doi
            self.journal = self.tableParser.journal


# retrieve target information
# -------------------------------------------------------------------------------------------------------------- 
        def retrieve_target(self):

            # find occurrences of target fullname and abbreviation in title
            number = ""
            fullIndex = self.titleText.lower().rfind(self.FULLNAME)
            abbrIndex = self.titleText.lower().rfind(self.ABBREVIATION)
            # find the number following the target name, e.g. "jak3", find "3" after "jak"
            if(fullIndex == -1 and abbrIndex == -1):
                pass
            # if only fullname is found
            elif(fullIndex != -1 and (fullIndex + len(self.FULLNAME) + 1) < len(self.titleText)):    
                index = fullIndex + len(self.FULLNAME) + 1
                while(self.titleText[index].isdigit()):
                    number += self.titleText[index]
                    index += 1
            # if only abbreviation is found
            elif(abbrIndex != -1 and (abbrIndex + len(self.FULLNAME) + 1) < len(self.titleText)):
                index = abbrIndex + len(self.ABBREVIATION) + 1
                while(self.titleText[index].isdigit()):
                    number += self.titleText[index]
                    index += 1
            # of both fullname and abbreviation are found
            elif((fullIndex + len(self.FULLNAME) + 1) < len(self.titleText) and (abbrIndex + len(self.ABBREVIATION) + 1) < len(self.titleText)):
                # abbreviation is preferred over fullname
                index = abbrIndex + len(self.ABBREVIATION) + 1
                while(self.titleText[index].isdigit()):
                    number += self.titleText[index]
                    index += 1
                if(not number):
                    index = fullIndex + len(self.FULLNAME) + 1
                    while(self.titleText[index].isdigit()):
                        number += self.titleText[index]
                        index += 1

            # use abbreviation and the identfied number as the target name to look for in the image
            if(number):
                self.focusedTarget = self.ABBREVIATION + number

            # if targetname is not found in the title, search in the abstract text
            if(not self.focusedTarget):
                targetArr = []

                # find every full target name in the abstract text, record its frequency and last occurred position
                index = 0
                while(index >= 0 and index < len(self.abstractText)):
                    index = self.abstractText.lower().find(self.FULLNAME, index)
                    if(index != -1 and (index + len(self.FULLNAME) + 1) < len(self.abstractText)):
                        number = ""
                        index += len(self.FULLNAME) + 1
                        while(index < len(self.abstractText)):
                            if(self.abstractText[index].isdigit()):
                                number += self.abstractText[index]
                                index += 1
                            else:
                                break
                        if(number):
                            targetName = self.ABBREVIATION + number
                            targetFound = False
                            for freqPosTarget in targetArr:
                                if(freqPosTarget[2] == targetName):
                                    freqPosTarget[0] += 1
                                    freqPosTarget[1] = index
                                    targetFound = True
                                    break
                            if(not targetFound):
                                targetArr.append([1, index, targetName])
                    elif(index != -1):
                        index += 1
                            

                # find every abbreviatioin target name in the abstract text, record its frequency and last occurred position
                index = 0
                while(index >= 0 and index < len(self.abstractText)):
                    index = self.abstractText.lower().find(self.ABBREVIATION, index)
                    if(index != -1 and (index + len(self.ABBREVIATION) < len(self.abstractText))):
                        number = ""
                        index += len(self.ABBREVIATION)
                        while(index < len(self.abstractText)):
                            if(self.abstractText[index].isdigit()):
                                number += self.abstractText[index]
                                index += 1
                            else:
                                break
                        if(number):
                            targetName = self.ABBREVIATION + number
                            targetFound = False
                            for freqPosTarget in targetArr:
                                if(freqPosTarget[2] == targetName):
                                    freqPosTarget[0] += 1
                                    freqPosTarget[1] = index
                                    targetFound = True
                                    break
                            if(not targetFound):
                                targetArr.append([1, index, targetName])
                    elif(index != -1):
                        index += 1        
                    
                #sort target names first by frequency, then by last occured position
                if(len(targetArr) > 0):
                    targetArr.sort(reverse=True)
                    self.focusedTarget = targetArr[0][2]   



        def retrieve_image_text(self):
            image = requests.get().content
            with open("abstract_image/image.jpeg", "wb") as handler:
                handler.write(image)

            # identify all text within the abstract image
            reader = easyocr.Reader(["en"], gpu = False)
            # retrieve picture through http request
            positionResult = reader.readtext("abstract_image/image.jpeg", "wb")

            return positionResult
        

        def get_ic50_from_image(self, positionResult):
            
            # find ic50 keyword location
            xrangeArr = []
            elements = []
            for element in positionResult:
                if(ic50(element[1].lower()) or ("ic" in element[1].lower() and "nm" in element[1].lower())):
                    elements.append(element)
                    leftX = min(element[0][0][0], element[0][3][0])
                    rightX = max(element[0][1][0], element[0][2][0])
                    xrangeArr.append([leftX, rightX, element[1]])        


            # find the rightmost ic50 keyword
            needTarget = False
            position = []
            centerX = 0
            for element in elements:
                if(needTarget):
                    break
                
                localCenterX = (element[0][0][0] + element[0][1][0] + element[0][2][0] + element[0][3][0]) / 4
                for xrange in xrangeArr:
                    if(localCenterX >= xrange[0] and localCenterX <= xrange[1] and element[1] != xrange[2]):
                        needTarget = True
                        break
                if(localCenterX > centerX):
                    centerX = localCenterX
                    position = element


            if((not needTarget) and len(position) > 0):
                # check if ic50 keyword contains the required value
                valueFound = False
                for word in position[1].lower().split():
                    if("nm" in word):
                        valueFound = True
                        break

                # if ic50 keyword contains the value, retrieve the value
                if(valueFound):
                    pos = position[1].find("=")
                    if(pos == -1):
                        pos = position[1].find(":")
                    if(pos == -1 or (pos + 1) >= len(position[1])):
                        valueFound = False
                    else:
                        self.ic50Value = position[1][pos + 1: ]

                # if no value is found in ic50 keyword
                else:
                    # find all keywords conataining "nm"
                    nmArr = []
                    for element in positionResult:
                        # the "nm" keyword has to locate on the right of "ic50" keyword
                        if("nm" in element[1].lower() and (element[0][0][0] + element[0][1][0] + element[0][2][0] + element[0][3][0]) / 4 >= min(position[0][1][0], position[0][2][0])):
                            nmArr.append(list(element))
                            nmArr[0][1] = nmArr[0][1].lower()
                    
                    for element in nmArr:
                        # if the keyword contains only "nm", needs to combine it with the number before it e.g.: keyword(50), keyword(nm), combined into keyword(50nm)
                        if(element[1].strip() == "nm"):

                            downY = max(element[0][2][1], element[0][3][1])
                            topY = min(element[0][0][1], element[0][1][1])
                            leftX = (element[0][0][0] + element[0][3][0]) / 2
                            rightX = (element[0][1][0] + element[0][2][0]) / 2
                            valueElement = []
                            xDistance = element[0][1][0]
                            for localElement in positionResult:
                                localCenterY = (localElement[0][0][1] + localElement[0][1][1] + localElement[0][2][1] + localElement[0][3][1]) / 4
                                # same y level as "nm" keyword
                                if(localCenterY <= downY and localCenterY >= topY):
                                    localRightX = (localElement[0][1][0] + localElement[0][2][0]) / 2
                                    # left of "nm" keyword
                                    if(localRightX < rightX):
                                        localxDistance = leftX - localRightX
                                        # closest to "nm" keyword
                                        if(localxDistance < xDistance):
                                            valueElement = localElement
                                            xDistance = localxDistance
                            
                            # combine keyword "nm" with the number before it
                            element[1] = valueElement[1] + element[1]
                            element[0][0] = valueElement[0][0]
                            element[0][3] = valueElement[0][3]

                    # find the corresponding value for the given "ic50" keyword, e.g. "ic50 = 12nm", find keyword(12nm) on the right of "ic50"
                    downY = max(position[0][2][1], position[0][3][1])
                    topY = min(position[0][0][1], position[0][1][1])
                    leftX = (position[0][0][0] + position[0][3][0]) / 2
                    rightX = (position[0][1][0] + position[0][2][0]) / 2
                    xDistance = position[0][1][0]
                    for element in nmArr:
                        localCenterY = (element[0][0][1] + element[0][1][1] + element[0][2][1] + element[0][3][1]) / 4
                        # same y level as "ic50" keyword
                        if(localCenterY <= downY and localCenterY >= topY):
                            localLeftX = (element[0][0][0] + element[0][3][0]) / 2
                            # right of "ic50" keyword
                            if(localLeftX > leftX):
                                localxDistance = localLeftX - rightX
                                # closest to "ic50" keyword
                                if(localxDistance < xDistance):
                                    self.ic50Value = element[1]
                                    localxDistance = xDistance

                if(self.ic50Value):
                    self.ic50Value = self.ic50Value.strip()
                    if(self.ic50Value[0] in ["=", ":"]):
                        self.ic50Value = self.ic50Value[1:]



            # if multiple ic50 values exist for one compound, need to use target name to identify
            if((not self.ic50Value) and self.focusedTarget):
                targetArr = []

                # find all tokens containing target name
                for element in positionResult:
                    if(self.focusedTarget in element[1].lower()):
                        centerX = (element[0][0][0] + element[0][1][0] + element[0][2][0] + element[0][3][0]) / 4
                        targetArr.append([centerX, element])

                # sort with the rightmost first
                targetArr.sort(reverse=True)

                if(len(targetArr) > 0):
                    for target in targetArr:
                        targetElement = target[1]

                        # if the value is already contained in the token
                        if(":" in targetElement[1] or "=" in targetElement[1]):
                            index = targetElement[1].find(":")
                            if(index == -1):
                                index = targetElement[1].find("=")
                            hasDigit = False
                            for c in range(index, len(targetElement[1])):
                                if(targetElement[1][c].isdigit()):
                                    hasDigit = True
                                    break
                            if(hasDigit):
                                self.ic50Value = targetElement[1]
                                break

                        centerX = targetArr[0][0]
                        topY = min(targetElement[0][0][1], targetElement[0][1][1])
                        downY = max(targetElement[0][2][1], targetElement[0][3][1])

                        # find all tokens to the right of the target name
                        elementArr = []
                        for element in positionResult:
                            localCenterX = (element[0][0][0] + element[0][1][0] + element[0][2][0] + element[0][3][0]) / 4
                            if(localCenterX > centerX):
                                localCenterY = (element[0][0][1] + element[0][1][1] + element[0][2][1] + element[0][3][1]) / 4
                                if(localCenterY >= topY and localCenterY <= downY):
                                    elementArr.append([localCenterX, element])
                        
                        # arrange the identified tokens from left to right, append them all into a string
                        elementArr.sort()
                        if(len(elementArr) > 0):
                            identifiedString = targetElement[1]
                            for element in elementArr:
                                identifiedString += element[1][1]
                                index = identifiedString.find("=")
                                if(index == -1):
                                    index = identifiedString.find(":")
                                if(index != -1 and (index + 1) < len(identifiedString)):
                                    self.ic50Value = identifiedString[index :]
                                else:
                                    self.ic50Value = identifiedString
                                

                                if(":" not in self.ic50Value and "=" not in self.ic50Value):
                                    self.ic50Value = ""
                                
                        # if the rightmost target name has no value, check the target names on its left
                        if(self.ic50Value):
                            break


        
        def get_compound_from_image(self, positionResult):
            # identify all compound names from the abstract image
            contentResult = []
            for element in positionResult:
                contentResult.append(element[1])
            compoundFound = False
            # identify all "compound" keyword and the name after it
            for word in contentResult:
                word = word.lower().strip()
                if(word == "compound"):
                    compoundFound = True
                    continue
                if("compound" in word):
                    pos = word.find("compound")
                    pos += 8
                    if(pos < len(word) and compoundName(word[pos:])):
                        self.compoundArr.append(word[pos:].strip())
                if(compoundFound):
                    if(compoundName(word)):
                        self.compoundArr.append(word)
                    compoundFound = False

            if(len(self.compoundArr) == 1):
                self.compound = self.compoundArr[0]


            if(not self.compound):
                compoundPosArr = []
                # find all keyword in the form of a compound name
                for element in positionResult:
                    if(compoundName(element[1]) and "nm" not in element[1].lower()):
                        compoundPosArr.append(element)
                
                # find the centerX of all identified keyword
                tempArr = []
                for element in compoundPosArr:
                    centerX = (element[0][0][0] + element[0][1][0] + element[0][2][0] + element[0][3][0]) / 4
                    tempArr.append([centerX, element[1]])
                tempArr.sort(reverse=True)

                # use the rightmost keyword as compound name
                if(len(tempArr) > 0):
                    self.compound = tempArr[0][1]

            self.compoundArr.clear()
        
# --------------------------------------------------------------------------------------------------------------
      

        def get_molecule_from_title_abstract(self):
            # find all identified molecule names inside of title
            doc = Document(self.titleText)
            for NR in doc.cems:
                self.moleculeArr.append(NR.text)
            tempArr = []
            for name in self.moleculeArr:
                if(moleculeName(name)):
                    tempArr.append(name)
            self.moleculeArr = tempArr # moleculeArr contains all chemistry named entities found in the title

            if(len(self.moleculeArr) == 1):
                self.molecule = self.moleculeArr[0]
                self.moleculeArr.clear()
            else:
                # if there's multiple named entities in title, then use abstract text to help identification
                titleMoleculeArr = self.moleculeArr.copy()
                self.moleculeArr.clear()
                
                doc = Document(self.abstractText)
                for NR in doc.cems:
                    self.moleculeArr.append(NR.text)
                textArr = []
                for name in self.moleculeArr:
                    if(moleculeName(name)):
                        textArr.append(name)
                
                if(len(titleMoleculeArr) == 0):
                    self.moleculeArr = textArr.copy()
                elif(len(textArr) == 0):
                    self.moleculeArr = titleMoleculeArr.copy()
                else:
                    # find named entities that appear both in title and in abstract text
                    self.moleculeArr = list(set(titleMoleculeArr).intersection(textArr))
                    if(len(self.moleculeArr) == 0):
                        self.moleculeArr = titleMoleculeArr.copy()
                
                if(len(self.moleculeArr) == 1):
                    self.molecule = self.moleculeArr[0]
        

        
        def get_compound_from_abstract(self):
            # identify compound name from abstract text, compound names are always in bold ( <b>keyword</b> )
            self.compoundArr = self.tableParser.boldAbstractTextArr.copy()
            # find all keywords in the form of compound name
            tempArr = []
            for name in self.compoundArr:
                if(compoundName(name)):
                    tempArr.append(name)

            # find the frequency of occurrence of each keyword in abstract text
            self.compoundArr.clear()
            for name in tempArr:
                nameFound = False
                for freqName in self.compoundArr:
                    if(freqName[1] == name):
                        freqName[0] += 1
                        nameFound = True
                        break
                if(not nameFound):
                    self.compoundArr.append([1, name])
            self.compoundArr.sort(reverse=True)

            tempArr.clear()
            if(len(self.compoundArr) > 0):
                # find all keywords with the highest frequency of occurrence
                maxFreq = self.compoundArr[0][0]
                for freqName in self.compoundArr:
                    if(freqName[0] == maxFreq):
                        tempArr.append([-1, freqName[1]])
                
                # find the position where the keyword is in abstract text
                # if there are multiple keywords have the highest frequency, select the one occurs last in text
                for posName in tempArr:
                    position = len(self.tableParser.boldAbstractTextArr) - 1
                    while(position >= 0):
                        if(self.tableParser.boldAbstractTextArr[position] == posName[1]):
                            posName[0] = position
                            break
                        position -= 1
                
                tempArr.sort(reverse=True)
                self.compoundArr = tempArr.copy()
                if(not self.compound and len(self.compoundArr) > 0):
                    self.compound = self.compoundArr[0][1]



        def get_ic50_from_abstract(self):
            # identify all ic50 values from abstract text
            ic50Found = False
            for word in self.abstractText.split():
                word = word.lower().strip()
                
                if(ic50(word)):
                    ic50Found = True
                    self.ic50Arr.append("")
                if(ic50Found):
                    self.ic50Arr[-1] += (word + " ")
                    if("nm" in word):
                        ic50Found = False
        


        # # ki and kd values have similar patterns, hence they are generalized here
        # # valueName: ki or kd
        # def find_enzyme_cell_value_in_table(self, valueName): 
            
        #     if(not self.compound):
        #         return ["", ""]
            
        #     enzymeValue = []
        #     cellValue = []

        #     tableNum = 0
        #     for table in self.tables:
        #         tableNum += 1
        #         enzymeFound = False
        #         cellFound = False
        #         valueNameFound = False
                
        #         caption = table.caption.lower()
        #         descriptions = table.descriptions
        #         grid = table.grid
        #         # check if valueName is contained in the table title
        #         valueNameIndex = 0
        #         while(valueNameIndex != -1 and valueNameIndex < len(caption)):
        #             valueNameIndex = caption.find(valueName, valueNameIndex)
        #             if(valueNameIndex != -1):
        #                 # the character following the valueName cannot be a letter or a number
        #                 if(valueNameIndex + len(valueName) < len(caption) 
        #                     and not caption[valueNameIndex + len(valueName)].isalpha()
        #                     and not caption[valueNameIndex + len(valueName)].isdigit()):

        #                     valueNameFound = True
        #                     break
        #                 else:
        #                     valueNameIndex += 1

        #         # Identify the column number of header that contains the valueName and the "compound" keyword
        #         valueColNum = -1
        #         compoundColNum = -1
        #         for row in grid.header:
        #             colNum = 0
        #             for cell in row.cells:
        #                 if(valueColNum != -1 and compoundColNum != -1):
        #                     break
        #                 # different rules apply to ki and kd, sometimes "kinact/ki" appears in a cell, needs to eliminate
        #                 if(valueName == "ki"):
        #                     if("ki" in cell.lower() and "kinact" not in cell.lower()):
        #                         index = cell.lower().find("ki")
        #                         if(index + 2 < len(cell) and cell[index + 2].isspace()):
        #                             valueColNum = colNum
        #                 elif(valueName == "kd"):
        #                     if("kd" in cell.lower()):
        #                         index = cell.lower().find("kd")
        #                         if(index + 2 < len(cell) and cell[index + 2].isspace()):
        #                             valueColNum = colNum
        #                 elif(valueName == "ic50"):
        #                     if("ic50" in cell.lower()):
        #                         index = cell.lower().find("ic50")
        #                         if(index + 4 < len(cell) and cell[index + 4].isspace()):
        #                             valueColNum = colNum
        #                 for compoundName in self.compoundKeywords:
        #                     if(compoundName in cell.lower()):
        #                         compoundColNum = colNum

        #                 colNum += 1
                
        #         # if valueName is not found in the title and not in the header or description, skip the current table
        #         foundInDescription = False
        #         if(valueColNum == -1 and not valueNameFound):
        #             for description in table.descriptions:
        #                 if(valueName in description.lower()):
        #                     foundInDescription = True
        #                     break
        #             if(not foundInDescription):
        #                 continue


        #         # try to identify whether the table is about enzyme or about cell from the title
        #         for enzymeName in self.enzymeKeywords:
        #             if(enzymeName in caption):
        #                 enzymeFound = True
        #                 break
        #         if(not enzymeFound):
        #             for cellName in self.cellKeywords:
        #                 if(cellName in caption):
        #                     cellFound = True
                
        #         # if the table is not about cell, try to found the header column that contains the target name
        #         targetColNum = -1
        #         if(not cellFound and self.focusedTarget):
        #             for row in grid.header:
        #                 colNum = 0
        #                 for cell in row.cells:
        #                     if(self.focusedTarget in cell.lower()):
        #                         targetColNum = colNum
        #                         break
        #                     colNum += 1
                
        #         # if the "compound" keyword is not found in the header, use the leftmost column as the compound column
        #         # try to find the name of the compound from the compound column and record the row number
        #         if(compoundColNum == -1):
        #             compoundColNum = 0
        #         compoundRowNum = -1
        #         rowNum = 0
        #         for row in grid.body:
        #             for cell in row.cells:
        #                 if(cell.lower().strip() == self.compound):
        #                     compoundRowNum = rowNum
        #                     break
        #             rowNum += 1
            
        #         if(not valueNameFound and valueColNum == -1 and foundInDescription and targetColNum != -1):
        #             if(compoundRowNum != -1):
        #                 if(enzymeFound):
        #                     enzymeValue.append(grid.body[compoundRowNum].cells[targetColNum].strip())
        #                 else:
        #                     cellValue.append(grid.body[compoundRowNum].cells[targetColNum].strip())

        #         elif(not enzymeFound):        
        #             if(compoundRowNum != -1):
        #                 cellValue.append(grid.body[compoundRowNum].cells[valueColNum].strip())
                
        #         elif(enzymeFound and targetColNum != -1):
        #             if(compoundRowNum != -1):
        #                 enzymeValue.append(grid.body[compoundRowNum].cells[targetColNum].strip())
                
        #         elif(enzymeFound and targetColNum == -1 and valueColNum != -1):
        #             if(compoundRowNum != -1):
        #                 enzymeValue.append(grid.body[compoundRowNum].cells[valueColNum].strip())
                
        #         # if neither enzyme keyword nor target name is found, only the title contains the valueName,
        #         # select one value from the compound row as its value
        #         elif(valueNameFound):
        #             if(compoundRowNum != -1):
        #                 colNum = 0
        #                 for cell in grid.body[compoundRowNum].cells:
        #                     if(colNum != compoundColNum):
        #                         if(enzymeFound):
        #                             enzymeValue.append(cell.strip())
        #                         else:
        #                             cellValue.append(cell.strip())
        #                         break
        #                     colNum += 1
            
        #     if(len(enzymeValue) > 0):
        #         enzymeValue = enzymeValue[0]
        #     else:
        #         enzymeValue = ""
        #     if(len(cellValue) > 0):
        #         cellValue = cellValue[0]
        #     else:
        #         cellValue = ""
        #     return [enzymeValue, cellValue]
        


        def find_values_in_table(self, valueName):

            if(not self.compound):
                return ""
            
            mediValue = ""
            vitroValue = ""
            vivoValue = ""


            for table in self.tables:
                
               
                titleFound = False
                index = table.caption.find(valueName)
                if(index != -1):
                    if((index + len(valueName)) >= len(table.caption)):
                        titleFound = True
                    else:
                        if(valueName[-1].isdigit()):
                            titleFound = True
                        else:
                            if(not table.caption[index + len(valueName)].isalpha()):
                                titleFound = True
                

                valueColNum = -1
                for row in table.grid.header:
                    
                    if(valueColNum != -1):
                        break
                    
                    colNum = 0
                    for cell in row.cells:
                        
                        index = cell.find(valueName)
                        if(index != -1):
                            if(valueName[-1].isdigit() or (index + len(valueName)) >= len(cell)):
                                valueColNum = colNum
                                break
                            else:
                                if(not cell[index + len(valueName)].isspace()):
                                    valueColNum = colNum
                                    break

                        colNum += 1
                

                if(not titleFound and valueColNum == -1):
                    continue

                
                compoundColNum = -1
                for row in table.grid.header:

                    if(compoundColNum != -1):
                        break

                    colNum = 0
                    for cell in row.cells:
                        
                        if(compoundColNum != -1):
                            break

                        for keyword in self.compoundKeywords:
                            if(keyword in cell.lower()):
                                compoundColNum = colNum
                                break
                        
                        colNum += 1
                

                compoundRowNum = -1
                if(compoundColNum == -1):
                    compoundColNum = 0
                rowNum = 0
                for row in table.grid.body:
                    
                    if(compoundRowNum != -1):
                        break
                    
                    colNum = 0
                    for cell in row.cells:
                        
                        if(colNum != compoundColNum):
                            continue
                        
                        if(cell.lower().strip() == self.compound):
                            compoundRowNum = rowNum
                            break

                        colNum += 1
                    rowNum += 1
                

                if(compoundRowNum == -1):
                    continue

                
                mediFound = False
                vitroFound = False
                vivoFound = False
                if("enzyme" in table.caption.lower() or "enzymatic" in table.caption.lower()):
                    mediFound = True
                elif("cell" in table.caption.lower() or "cellular" in table.caption.lower() 
                or "vitro" in table.caption.lower()):
                    vitroFound = True
                elif("pharmacokinetic" in table.caption.lower() or "preliminary" in table.caption.lower()
                or "vivo" in table.caption.lower() or "preclinical" in table.caption.lower()):
                    vivoFound = True
                

                if(not mediFound and not vitroFound and not vivoFound):
                    continue


                targetColNum = -1
                if(self.focusedTarget):

                    for row in table.grid.header:
                        
                        if(targetColNum != -1):
                            break
                        
                        colNum = 0
                        for cell in row.cells:
                            
                            if(self.focusedTarget in cell.lower()):
                                targetColNum = colNum
                                break

                            colNum += 1


                if(valueColNum == -1 and targetColNum == -1):
                    continue

                value = ""
                if(titleFound):
                    if(targetColNum != -1):
                        value = table.grid.body[compoundRowNum].cells[targetColNum]
                    else:
                        value = table.grid.body[compoundRowNum].cells[valueColNum]
                else:
                    value = table.grid.body[compoundRowNum].cells[valueColNum]
                
                
                if(mediFound):
                    mediValue = value
                elif(vitroFound):
                    vitroValue = value
                else:
                    vivoValue = value


            return[mediValue, vitroValue, vivoValue]



        def find_single_value_in_table(self, valueName):
            
            if(not self.compound):
                return ""

            for table in self.tables:
                
                valueNameFound = False
                index = 0
                while(index >= 0 and index < len(table.caption)):
                    index = table.caption.lower().find(valueName, index)
                    if(index != -1):
                        if((index + len(valueName)) < len(table.caption)):
                            if(table.caption[index + len(valueName)].isspace()):
                                valueNameFound = True
                                break
                        else:
                            valueNameFound = True
                            break
                        index += 1
                
                valueColNum = -1
                for row in table.grid.header:
                    colNum = 0
                    for cell in row.cells:
                        index = cell.lower().find(valueName)
                        if(index != -1):
                            if((index + len(valueName)) < len(cell)):
                                if(cell[index + len(valueName)].isspace()):
                                    valueColNum = colNum
                                    break
                                elif(valueName.lower() == "auc"):
                                    valueColNum = colNum
                                    break
                            else:
                                valueColNum = colNum
                                break
                        colNum += 1
                
                targetColNum = -1
                if(self.focusedTarget):
                    for row in table.grid.header:
                        colNum = 0
                        for cell in row.cells:
                            if(self.focusedTarget in cell.lower()):
                                targetColNum = colNum
                        colNum += 1
                

                if((valueColNum == -1 and not valueNameFound) or (valueNameFound and targetColNum == -1)):
                    continue

                
                compoundColNum = -1
                for row in table.grid.header:
                    colNum = 0
                    for cell in row.cells:
                        for compoundName in self.compoundKeywords:
                            if(compoundName in cell.lower()):
                                compoundColNum = colNum
                                break
                        colNum += 1
                
                if(compoundColNum == -1):
                    compoundColNum = 0
                
                compoundRowNum = -1
                rowNum = 0
                for row in table.grid.body:
                    for cell in row.cells:
                        if(cell.lower().strip() == self.compound):
                            compoundRowNum = rowNum
                            break
                    rowNum += 1

                if(compoundRowNum == -1):
                    continue
                
                if(valueColNum != -1):
                    return table.grid.body[compoundRowNum].cells[valueColNum]
                elif(valueNameFound and targetColNum != -1):
                    return table.grid.body[compoundRowNum].cells[targetColNum]
            
            return ""



        def get_multiple_values_from_body(self):
            [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("IC50")
            if(not self.ic50Value):
                self.enzymeIc50 = enzymeValue
            else:
                self.enzymeIc50 = self.ic50Value
            self.cellIc50 = cellValue
            [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("Ki")
            self.enzymeKi = enzymeValue
            self.cellKi = cellValue
            [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("Kd")
            self.enzymeKd = enzymeValue
            self.cellKd = cellValue
            [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("selectivity")
            self.enzymeSelectivity = enzymeValue
            self.cellSelectivity = cellValue
            [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("solubility")
            self.cellSolubility = cellValue
            self.vivoSolubility = vivoValue


        
        def get_single_value_from_body(self):
            self.ec50 = self.find_single_value_in_table("ec50")
            self.ed50 = self.find_single_value_in_table("ed50")
            self.auc = self.find_single_value_in_table("auc")
            self.herg = self.find_single_value_in_table("herg")





class ScienceDirect:

    TARGET = ""
    
    ## Load configuration
    con_file = open("config.json")
    config = json.load(con_file)
    con_file.close()
    APIKEY = config['apikey']

    ## Initialize client
    client = ElsClient(APIKEY)

    JOURNAL1 = "European Journal of Medicinal Chemistry"
    JOURNAL2 = "Drug Discovery Today"
    TARGET = ""
    conditions = []



    def initialize_conditions(targetName):
        TARGET = targetName
        ScienceDirect.conditions.append((TARGET, ScienceDirect.JOURNAL1))
        ScienceDirect.conditions.append((TARGET, ScienceDirect.JOURNAL2))
    


    def retrieve_article_amount_and_doi():
        
        for condition in ScienceDirect.conditions:

            AMOUNT1 = 0
            AMOUNT2 = 0
            DOIArr = []
            dateArr = []

            url = "https://api.elsevier.com/content/search/sciencedirect"
            header = {"x-els-apikey": "7f59af901d2d86f78a1fd60c1bf9426a", "Accept": "application/json", "Content-Type": "application/json"}
            payload = {
            "qs": f"{condition[0]}",
            "pub": f"\"{condition[1]}\"",
            }

            response = requests.put(url, headers=header, json=payload)
            result = json.loads(response.text)
            AMOUNT1 = result["resultsFound"]

            if ("results" in result):
                for article in result["results"]:
                    if (article["doi"]):
                        doc = FullDoc(doi = article["doi"])
                        stringList = ["IC50", "EC50", "ED50"]
                        keywordFound = False
                        if(doc.read(ScienceDirect.client)):
                            if(any(substring in doc.data["originalText"] for substring in stringList)):
                                keywordFound = True
                            if(not keywordFound):
                                index = doc.data["originalText"].find("Ki")
                                if(index == -1):
                                    index = doc.data["originalText"].find("Kd")
                                if(index == -1):
                                    continue
                                if((index + 2) >= len(doc.data["originalText"])):
                                    keywordFound = True
                                else:
                                    if(not doc.data["originalText"][index + 2].isalpha()):
                                        keywordFound = True
                                                        
                        if(keywordFound):    
                            AMOUNT2 += 1
                            DOIArr.append(article["doi"])

                            date = article["publicationDate"][:4]
                            found = False
                            for yearOccur in dateArr:
                                if(yearOccur[0] == date):
                                    yearOccur[1] += 1
                                    found = True
                                    break
                            if(not found):
                                dateArr.append([date, 1])
                            continue

        dateArr.sort()
        return(((AMOUNT1, AMOUNT2), DOIArr, dateArr))

    

    class ScienceDirectArticle:



        # parse a ScienceDirect xml file
        class TableParser(HTMLParser):

            def __init__(self):
                HTMLParser.__init__(self)

                self.skipParsing = False

                self.authorArr = []
                self.year = -1
                self.institution = []
                self.journal = ""

                self.authorFound = False
                self.authorName = False
                self.yearFound = False
                self.institutionFound = False
                self.institutionName = False
                self.journalFound = False
                
                self.titleFound = False
                self.titleText = ""
                self.imgRef = ""
                self.abstractBoldText = ""
                self.boldAbstractTextArr = []

                self.abstractTextFound = False
                self.abstractTextContent = False
                self.abstractText = ""
                self.abstractImageFound = False
                self.boldTextFound = False
                
                self.bodyTextFound = False
                self.bodyText = BodyText()
                self.sectionCount = 0
                self.newSectionFound = False
                self.newSubsection = False
                self.newSectionTitle = False
                self.newSubsectionTitle = False
                self.newParagraphFound = False

                self.tables = []
                self.tableFound = False
                self.tableCaptionFound = False
                self.tableCaptionContent = False

                self.tableGridFound = False
                self.tableHeaderFound = False
                self.headerRowFound = False
                self.headerCellFound = False
                self.spaceHeaderCell = False

                self.tableContentFound = False
                self.contentRowFound = False
                self.contentCellFound = False
                self.spaceContentCell = False




            def handle_starttag(self, tag, attrs):

                if(tag == "ce:author"):
                    self.authorFound = True
                    self.authorArr.append("")
                if(self.authorFound and (tag == "ce:given-name" or tag == "ce:surname")):
                    self.authorName = True
                if(tag == "xocs:cover-date-year"):
                    self.yearFound = True
                if(tag == "ce:affiliation"):
                    self.institutionFound = True
                if(self.institutionFound and tag == "ce:textfn"):
                    self.institutionName = True
                    self.institution.append("")
                if(tag == "xocs:srctitle"):
                    self.journalFound = True

                if(tag == "ce:title"):
                    self.titleFound = True
                if(tag == "ce:abstract"):
                    for attr in attrs:
                        if(attr[0] == "class" and attr[1] == "author"):
                            self.abstractTextFound = True
                            return
                        elif(attr[0] == "class" and attr[1] == "graphical"):
                            self.abstractImageFound = True
                            return
                if(self.abstractTextFound and tag == "ce:simple-para"):
                    self.abstractTextContent = True
                if(self.abstractImageFound and tag == "ce:link"):
                    for attr in attrs:
                        if(attr[0] == "xlink:href"):
                            self.imgRef = attr[1]
                if(self.abstractTextContent and tag == "ce:bold"):
                    self.boldTextFound = True
                    self.abstractBoldText += "<b>"

                if(tag == "ce:sections"):
                    self.bodyTextFound = True
                if(self.bodyTextFound and tag == "ce:section" and self.sectionCount == 0):
                    self.newSectionFound = True
                    self.sectionCount += 1
                    return
                if(self.newSectionFound and tag == "ce:section" and self.sectionCount > 0):
                    self.newSubsection = True
                    self.sectionCount += 1
                if(self.newSectionFound and tag == "ce:section-title" and self.sectionCount == 1):    
                    self.newSectionTitle = True
                if(self.newSectionFound and tag == "ce:section-title" and self.sectionCount > 1):
                    self.newSubsectionTitle = True
                if(self.newSectionFound and tag == "ce:para"):
                    self.newParagraphFound = True
                    if(len(self.bodyText.sections[-1].paragraphs) > 0 and self.bodyText.sections[-1].paragraphs[-1].header != ""):
                        return
                    newParagraph = BodyText.Section.Paragraph("")
                    self.bodyText.sections[-1].paragraphs.append(newParagraph)
                if(tag == "ce:table"):
                    self.tableFound = True
                    newTable = Table()
                    self.tables.append(newTable)
                if(self.tableFound and tag == "ce:caption"):
                    self.tableCaptionFound = True
                if(self.tableCaptionFound and tag == "ce:simple-para"):
                    self.tableCaptionContent = True

                if(self.tableFound and tag == "tgroup"):
                    self.tableGridFound = True
                    newGrid = Table.Grid()
                    for attr in attrs:
                        if(attr[0] == "cols"):
                            newGrid.columnNum = attr[1]
                    self.tables[-1].grid = newGrid
                if(self.tableGridFound and tag == "thead"):
                    self.tableHeaderFound = True
                if(self.tableHeaderFound and tag == "row"):
                    self.headerRowFound = True
                    newRow = Table.Grid.Row()
                    self.tables[-1].grid.header.append(newRow)
                if(self.headerRowFound and tag == "entry"):
                    self.headerCellFound = True
                    self.tables[-1].grid.header[-1].cells.append("")
                if(self.headerCellFound and tag == "cross-ref"):
                    self.spaceHeaderCell = True
                
                if(self.tableGridFound and tag == "tbody"):
                    self.tableContentFound = True
                if(self.tableContentFound and tag == "row"):
                    self.contentRowFound = True
                    newRow = Table.Grid.Row()
                    self.tables[-1].grid.body.append(newRow)
                if(self.contentRowFound and tag == "entry"):
                    self.contentCellFound = True
                    self.tables[-1].grid.body[-1].cells.append("")
                if(self.contentCellFound and tag == "cross-ref"):
                    self.spaceContentCell = True
                


            def handle_data(self, data):

                if(self.authorName):
                    if(len(self.authorArr[-1]) == 0):
                        self.authorArr[-1] += (data.strip() + " ")
                    else:
                        self.authorArr[-1] += data.strip()
                if(self.yearFound):
                    self.year = int(data)
                if(self.institutionName):
                    self.institution[-1] += (data.strip())
                if(self.journalFound):
                    self.journal = data
                
                if(self.spaceHeaderCell):
                    if(len(self.tables[-1].grid.header[-1].cells) != 0):
                        self.tables[-1].grid.header[-1].cells[-1] += " "
                    return
                if(self.spaceContentCell):
                    if(len(self.tables[-1].grid.body[-1].cells) != 0):
                        self.tables[-1].grid.body[-1].cells[-1] += " " 
                    return


                if(self.skipParsing):
                    self.skipParsing = True
                    return
                if(self.boldTextFound):
                    self.boldAbstractTextArr.append(data)
                
                if(self.titleFound):
                    self.titleText = data
                if(self.abstractTextContent):
                    self.abstractText += data
                    self.abstractBoldText += data
                
                if(self.newSectionTitle):
                    newSection = BodyText.Section(data)
                    self.bodyText.sections.append(newSection)
                if(self.newSubsectionTitle):
                    newParagraph = BodyText.Section.Paragraph(data)
                    self.bodyText.sections[-1].paragraphs.append(newParagraph)
                if(self.newParagraphFound):
                    if(len(self.bodyText.sections[-1].paragraphs) == 0):
                        newParagraph = BodyText.Section.Paragraph("")
                        self.bodyText.sections[-1].paragraphs.append(newParagraph)
                    if(len(self.bodyText.sections[-1].paragraphs[-1].contents) == 0):
                        self.bodyText.sections[-1].paragraphs[-1].contents.append(data) 
                        return 
                    else:
                        self.bodyText.sections[-1].paragraphs[-1].contents[-1] += (data)
                
                if(self.tableCaptionContent):
                    self.tables[-1].caption = data
                if(self.headerCellFound):
                    self.tables[-1].grid.header[-1].cells[-1] += data
                if(self.contentCellFound):
                    self.tables[-1].grid.body[-1].cells[-1] += data



            def handle_endtag(self, tag):

                if(self.authorFound and tag == "ce:author"):
                    self.authorFound = False
                if(self.authorName and (tag == "ce:given-name" or tag == "ce:surname")):
                    self.authorName = False
                if(self.yearFound and tag == "xocs:cover-date-year"):
                    self.yearFound = False
                if(self.institutionFound and tag == "ce:affiliation"):
                    self.institutionFound = False
                if(self.institutionName and tag == "ce:textfn"):
                    self.institutionName = False
                if(self.journalFound and tag == "xocs:srctitle"):
                    self.journalFound = False

                if(self.titleFound and tag == "ce:title"):
                    self.titleFound = False
                if(self.abstractTextFound and tag == "ce:abstract"):
                    self.abstractTextFound = False
                if(self.abstractImageFound and tag == "ce:abstract"):
                    self.abstractImageFound = False
                if(self.abstractTextContent and tag == "ce:simple-para"):
                    self.abstractTextContent = False
                if(self.boldTextFound and tag == "ce:bold"):
                    self.boldTextFound = False
                    self.abstractBoldText += "</b>"
                
                if(self.bodyTextFound and tag == "ce:sections"):
                    self.bodyTextFound = False
                if(self.newSectionFound and tag == "ce:section" and self.sectionCount == 1):
                    self.newSectionFound = False
                    self.sectionCount -= 1
                if(self.newSubsection and tag == "ce:section" and self.sectionCount > 1):
                    self.sectionCount -= 1
                    if(self.sectionCount == 1):
                        self.newSubsection = False
                if(self.newSectionTitle and tag == "ce:section-title"):
                    self.newSectionTitle = False
                if(self.newSubsectionTitle and tag == "ce:section-title"):
                    self.newSubsectionTitle = False
                if(self.newParagraphFound and tag == "ce:para"):
                    self.newParagraphFound = False
                
                if(self.tableFound and tag == "ce:table"):
                    self.tableFound = False
                if(self.tableCaptionFound and tag == "ce:caption"):
                    self.tableCaptionFound = False
                if(self.tableCaptionContent and tag == "ce:simple-para"):
                    self.tableCaptionContent = False
                
                if(self.tableGridFound and tag == "tgroup"):
                    self.tableGridFound = False
                if(self.tableHeaderFound and tag == "thead"):
                    self.tableHeaderFound = False
                if(self.headerRowFound and tag == "row"):
                    self.headerRowFound = False
                if(self.headerCellFound and tag == "entry"):
                    self.headerCellFound = False
                if(self.spaceHeaderCell and tag == "cross-ref"):
                    self.spaceHeaderCell = False
                
                if(self.tableContentFound and tag == "tbody"):
                    self.tableContentFound = False
                if(self.contentRowFound and tag == "row"):
                    self.contentRowFound = False
                if(self.contentCellFound and tag == "entry"):
                    self.contentCellFound = False
                if(self.spaceContentCell and tag == "cross-ref"):
                    self.spaceContentCell = False




        # parse to find the link to abstract image
        class ReferenceParser(HTMLParser):

            def __init__(self, ref):
                HTMLParser.__init__(self)

                self.isRequired = False
                self.isHighRes = False
                self.imageFound = False

                self.ref = ref
                self.eid = ""

                self.attachmentFound = False
                self.eidFound = False
                self.locatorFound = False
                self.resolutionFound = False



            def handle_starttag(self, tag, attrs):
                if(tag == "xocs:attachment"):
                    self.attachmentFound = True
                if(self.attachmentFound == True and tag == "xocs:attachment-eid"):
                    self.eidFound = True
                if(self.attachmentFound and tag == "xocs:ucs-locator"):
                    self.locatorFound = True
                if(self.attachmentFound and tag == "xocs:attachment-type"):
                    self.resolutionFound = True



            def handle_data(self, data):
                if(self.eidFound):
                    self.eid = data
                if(self.locatorFound):
                    if(self.ref in data):
                        self.isRequired = True
                    else:
                        self.isRequired = False
                if(self.resolutionFound):
                    if(self.isRequired and data == "IMAGE-HIGH-RES"):
                        self.imageFound = True
                        exitParser(self)
                        
                        

            def handle_endtag(self, tag):
                
                if(self.attachmentFound and tag == "xocs:attachment"):
                    self.attachmentFound = False
                if(self.eidFound and tag == "xocs:attachment-eid"):
                    self.eidFound = False
                if(self.locatorFound and tag == "xocs:ucs-locator"):
                    self.locatorFound = False
                if(self.resolutionFound and tag == "xocs:attachment-type"):
                    self.resolutionFound = False
        


        def __init__(self, articleDOI):

            self.articleDOI = articleDOI

            self.authorArr = []
            self.year = -1
            self.institution = []
            self.paperCited = -1
            self.doi = self.articleDOI
            self.journal = ""
            
            # fullname and abbreviation is used in ic50 extraction in abstract image
            # stores the fullname of the target gene, omit number, e.g. if target is "jak1", fullname is "janus kinase"
            self.FULLNAME = ""
            # stores the abbreviation of the target gene, omit number, e.g. if target is "jak1", abbreviation is "jak"
            self.ABBREVIATION = ""
            # Target name of the article's focus
            self.focusedTarget = ""


            self.tableParser = None            
            # hold title content after parsing html file
            self.titleText = ""
            # hold links to abstract images after parsing html file
            self.imgURL = ""
            # hold abstract content after parsing html file
            self.abstractText = ""

            # BodyText object for holding body text
            self.bodyText = None
            # Table object for holding tables
            self.tables = None



            # hold the molecule name
            self.molecule = ""
            # hold the compound name
            self.compound = ""
            # hold the ic50 value
            self.ic50Value = ""


            # Arr variables provide additional and alternative information, in case the identified molecule, compound, ic50value are incorrect

            # hold all identified molecule names
            self.moleculeArr = []
            # hold all identified compound names
            self.compoundArr = []
            # hold all identified ic50 values
            self.ic50Arr = []

            self.enzymeKeywords = [self.ABBREVIATION, self.FULLNAME, "enzyme", "enzymatic"]
            self.cellKeywords = ["cell", "cellar"]
            self.compoundKeywords = ["compound", "no", "id", "compd", "cpd", "cmp"]

            self.enzymeIc50 = ""
            self.cellIc50 = ""
            self.enzymeKi = ""
            self.cellKi = ""
            self.enzymeKd = ""
            self.cellKd = ""
            self.ec50 = ""
            self.ed50 = ""
            self.auc = ""
            self.herg = ""

            self.retrieve_values()


        

        def retrieve_values(self):
            
            self.get_FULLNAME_ABBREVIATION()
            self.retrieve_article_information()
            self.retrieve_target()

            positionResult = self.retrieve_image_text()
            self.get_ic50_from_image(positionResult)
            self.get_compound_from_image(positionResult)
            self.get_molecule_from_title_abstract()
            self.get_compound_from_abstract()
            self.get_ic50_from_abstract()
            self.get_ic50_from_body()
            self.get_kikd_from_body()
            self.get_single_value_from_body()




        def retrieve_article_information(self):
            
            QUERY_URL = "https://api.elsevier.com/content/article/doi/"
            header = {"X-ELS-APIKey": ScienceDirect.APIKEY, "Accept": "text/xml"}
            response = requests.get(QUERY_URL + self.articleDOI, headers=header)

            tableParser = ScienceDirect.ScienceDirectArticle.TableParser()
            try:
                tableParser.feed(response.text)
            except AssertionError as ae:
                pass

            imgRef = tableParser.imgRef
            imageParser = ScienceDirect.ScienceDirectArticle.ReferenceParser(imgRef)
            try:
                imageParser.feed(response.text)
            except AssertionError as ae:
                pass
            
            IMAGE_QUERY_URL = "https://api.elsevier.com/content/object/eid/"
            self.imgURL = IMAGE_QUERY_URL + imageParser.eid
            self.titleText = tableParser.titleText
            self.abstractText = tableParser.abstractText
            self.bodyText = tableParser.bodyText
            self.tables = tableParser.tables
            self.tableParser = tableParser

            self.authorArr = tableParser.authorArr
            self.year = tableParser.year
            self.institution = tableParser.institution
            self.journal = tableParser.journal

            citedByURL = f"http://api.elsevier.com/content/search/scopus?query=DOI({self.doi})&field=citedby-count"
            header = {"X-ELS-APIKey": ScienceDirect.APIKEY}
            response = requests.get(citedByURL, headers=header)
            responseDict = json.loads(response.text)
            self.paperCited = int(responseDict["search-results"]["entry"][0]["citedby-count"])



        def retrieve_image_text(self):
            header = {"X-ELS-APIKey": ScienceDirect.APIKEY}
            image = requests.get(self.imgURL, headers=header).content
            with open("abstract_image/image.jpeg", "wb") as handler:
                handler.write(image)


            # identify all text within the abstract image
            reader = easyocr.Reader(["en"], gpu = False)
            # retrieve picture through http request
            positionResult = reader.readtext("abstract_image/image.jpeg", "wb")

            return positionResult



        def get_FULLNAME_ABBREVIATION(self):
            
            # trim the number at the end of TARGET
            i = len(ACS.TARGET) - 1
            while(i >= 0):
                if(not ACS.TARGET[i].isalpha()):
                    i -= 1
                else:
                    break
            queryTarget = ACS.TARGET[:i + 1]

            # target name identification is performed through an online database: http://allie.dbcls.jp/
            # at this point, the user might input a fullname or an abbreviation, so it needs to be queried twice

            # queryLongUrl: treat the input as a fullname, find abbreviation
            queryLongUrl = f"https://allie.dbcls.jp/long/exact/Any/{queryTarget.lower()}.html"
            # queryShortUrl: treat the input as an abbreviation, find fullname
            queryShortUrl = f"https://allie.dbcls.jp/short/exact/Any/{queryTarget.lower()}.html"

            longResponse = requests.get(queryLongUrl)
            shortReponse = requests.get(queryShortUrl)

            longParser = ACS.ACSArticle.TargetParser()
            shortParser = ACS.ACSArticle.TargetParser()
            try:
                longParser.feed(longResponse.text)    
            except AssertionError as ae:
                pass

            try:
                shortParser.feed(shortReponse.text)
            except AssertionError as ae:
                pass

            longForm = shortParser.result.lower().strip()
            longFrequency = shortParser.frequency
            shortForm = longParser.result.lower().strip()
            shortFrequency = longParser.frequency

            # if the input is a full name, shortFrequency will be 0, the input will be FULLNAME, vice versa.
            if(shortFrequency > longFrequency):
                self.FULLNAME = queryTarget
                self.ABBREVIATION = shortForm
            else:
                self.FULLNAME = longForm
                self.ABBREVIATION = queryTarget



# retrieve target information
# -------------------------------------------------------------------------------------------------------------- 
        def retrieve_target(self):

            # find occurrences of target fullname and abbreviation in title
            number = ""
            fullIndex = self.titleText.lower().rfind(self.FULLNAME)
            abbrIndex = self.titleText.lower().rfind(self.ABBREVIATION)
            # find the number following the target name, e.g. "jak3", find "3" after "jak"
            if(fullIndex == -1 and abbrIndex == -1):
                pass
            # if only fullname is found
            elif(fullIndex != -1 and (fullIndex + len(self.FULLNAME) + 1) < len(self.titleText)):    
                index = fullIndex + len(self.FULLNAME) + 1
                while(self.titleText[index].isdigit()):
                    number += self.titleText[index]
                    index += 1
            # if only abbreviation is found
            elif(abbrIndex != -1 and (abbrIndex + len(self.FULLNAME) + 1) < len(self.titleText)):
                index = abbrIndex + len(self.ABBREVIATION) + 1
                while(self.titleText[index].isdigit()):
                    number += self.titleText[index]
                    index += 1
            # of both fullname and abbreviation are found
            elif((fullIndex + len(self.FULLNAME) + 1) < len(self.titleText) and (abbrIndex + len(self.ABBREVIATION) + 1) < len(self.titleText)):
                # abbreviation is preferred over fullname
                index = abbrIndex + len(self.ABBREVIATION) + 1
                while(self.titleText[index].isdigit()):
                    number += self.titleText[index]
                    index += 1
                if(not number):
                    index = fullIndex + len(self.FULLNAME) + 1
                    while(self.titleText[index].isdigit()):
                        number += self.titleText[index]
                        index += 1

            # use abbreviation and the identfied number as the target name to look for in the image
            if(number):
                self.focusedTarget = self.ABBREVIATION + number

            # if targetname is not found in the title, search in the abstract text
            if(not self.focusedTarget):
                targetArr = []

                # find every full target name in the abstract text, record its frequency and last occurred position
                index = 0
                while(index >= 0 and index < len(self.abstractText)):
                    index = self.abstractText.lower().find(self.FULLNAME, index)
                    if(index != -1 and (index + len(self.FULLNAME) + 1) < len(self.abstractText)):
                        number = ""
                        index += len(self.FULLNAME) + 1
                        while(index < len(self.abstractText)):
                            if(self.abstractText[index].isdigit()):
                                number += self.abstractText[index]
                                index += 1
                            else:
                                break
                        if(number):
                            targetName = self.ABBREVIATION + number
                            targetFound = False
                            for freqPosTarget in targetArr:
                                if(freqPosTarget[2] == targetName):
                                    freqPosTarget[0] += 1
                                    freqPosTarget[1] = index
                                    targetFound = True
                                    break
                            if(not targetFound):
                                targetArr.append([1, index, targetName])
                    elif(index != -1):
                        index += 1
                            

                # find every abbreviatioin target name in the abstract text, record its frequency and last occurred position
                index = 0
                while(index >= 0 and index < len(self.abstractText)):
                    index = self.abstractText.lower().find(self.ABBREVIATION, index)
                    if(index != -1 and (index + len(self.ABBREVIATION) < len(self.abstractText))):
                        number = ""
                        index += len(self.ABBREVIATION)
                        while(index < len(self.abstractText)):
                            if(self.abstractText[index].isdigit()):
                                number += self.abstractText[index]
                                index += 1
                            else:
                                break
                        if(number):
                            targetName = self.ABBREVIATION + number
                            targetFound = False
                            for freqPosTarget in targetArr:
                                if(freqPosTarget[2] == targetName):
                                    freqPosTarget[0] += 1
                                    freqPosTarget[1] = index
                                    targetFound = True
                                    break
                            if(not targetFound):
                                targetArr.append([1, index, targetName])
                    elif(index != -1):
                        index += 1        
                    
                #sort target names first by frequency, then by last occured position
                if(len(targetArr) > 0):
                    targetArr.sort(reverse=True)
                    self.focusedTarget = targetArr[0][2]   

        

        def get_ic50_from_image(self, positionResult):
            
            # find ic50 keyword location
            xrangeArr = []
            elements = []
            for element in positionResult:
                if(ic50(element[1].lower()) or ("ic" in element[1].lower() and "nm" in element[1].lower())):
                    elements.append(element)
                    leftX = min(element[0][0][0], element[0][3][0])
                    rightX = max(element[0][1][0], element[0][2][0])
                    xrangeArr.append([leftX, rightX, element[1]])        


            # find the rightmost ic50 keyword
            needTarget = False
            position = []
            centerX = 0
            for element in elements:
                if(needTarget):
                    break
                
                localCenterX = (element[0][0][0] + element[0][1][0] + element[0][2][0] + element[0][3][0]) / 4
                for xrange in xrangeArr:
                    if(localCenterX >= xrange[0] and localCenterX <= xrange[1] and element[1] != xrange[2]):
                        needTarget = True
                        break
                if(localCenterX > centerX):
                    centerX = localCenterX
                    position = element


            if((not needTarget) and len(position) > 0):
                # check if ic50 keyword contains the required value
                valueFound = False
                for word in position[1].lower().split():
                    if("nm" in word):
                        valueFound = True
                        break

                # if ic50 keyword contains the value, retrieve the value
                if(valueFound):
                    pos = position[1].find("=")
                    if(pos == -1):
                        pos = position[1].find(":")
                    if(pos == -1 or (pos + 1) >= len(position[1])):
                        valueFound = False
                    else:
                        self.ic50Value = position[1][pos + 1: ]

                # if no value is found in ic50 keyword
                else:
                    # find all keywords conataining "nm"
                    nmArr = []
                    for element in positionResult:
                        # the "nm" keyword has to locate on the right of "ic50" keyword
                        if("nm" in element[1].lower() and (element[0][0][0] + element[0][1][0] + element[0][2][0] + element[0][3][0]) / 4 >= min(position[0][1][0], position[0][2][0])):
                            nmArr.append(list(element))
                            nmArr[0][1] = nmArr[0][1].lower()
                    
                    for element in nmArr:
                        # if the keyword contains only "nm", needs to combine it with the number before it e.g.: keyword(50), keyword(nm), combined into keyword(50nm)
                        if(element[1].strip() == "nm"):

                            downY = max(element[0][2][1], element[0][3][1])
                            topY = min(element[0][0][1], element[0][1][1])
                            leftX = (element[0][0][0] + element[0][3][0]) / 2
                            rightX = (element[0][1][0] + element[0][2][0]) / 2
                            valueElement = []
                            xDistance = element[0][1][0]
                            for localElement in positionResult:
                                localCenterY = (localElement[0][0][1] + localElement[0][1][1] + localElement[0][2][1] + localElement[0][3][1]) / 4
                                # same y level as "nm" keyword
                                if(localCenterY <= downY and localCenterY >= topY):
                                    localRightX = (localElement[0][1][0] + localElement[0][2][0]) / 2
                                    # left of "nm" keyword
                                    if(localRightX < rightX):
                                        localxDistance = leftX - localRightX
                                        # closest to "nm" keyword
                                        if(localxDistance < xDistance):
                                            valueElement = localElement
                                            xDistance = localxDistance
                            
                            # combine keyword "nm" with the number before it
                            element[1] = valueElement[1] + element[1]
                            element[0][0] = valueElement[0][0]
                            element[0][3] = valueElement[0][3]

                    # find the corresponding value for the given "ic50" keyword, e.g. "ic50 = 12nm", find keyword(12nm) on the right of "ic50"
                    downY = max(position[0][2][1], position[0][3][1])
                    topY = min(position[0][0][1], position[0][1][1])
                    leftX = (position[0][0][0] + position[0][3][0]) / 2
                    rightX = (position[0][1][0] + position[0][2][0]) / 2
                    xDistance = position[0][1][0]
                    for element in nmArr:
                        localCenterY = (element[0][0][1] + element[0][1][1] + element[0][2][1] + element[0][3][1]) / 4
                        # same y level as "ic50" keyword
                        if(localCenterY <= downY and localCenterY >= topY):
                            localLeftX = (element[0][0][0] + element[0][3][0]) / 2
                            # right of "ic50" keyword
                            if(localLeftX > leftX):
                                localxDistance = localLeftX - rightX
                                # closest to "ic50" keyword
                                if(localxDistance < xDistance):
                                    self.ic50Value = element[1]
                                    localxDistance = xDistance

                if(self.ic50Value):
                    self.ic50Value = self.ic50Value.strip()
                    if(self.ic50Value[0] in ["=", ":"]):
                        self.ic50Value = self.ic50Value[1:]



            # if multiple ic50 values exist for one compound, need to use target name to identify
            if((not self.ic50Value) and self.focusedTarget):
                targetArr = []

                # find all tokens containing target name
                for element in positionResult:
                    if(self.focusedTarget in element[1].lower()):
                        centerX = (element[0][0][0] + element[0][1][0] + element[0][2][0] + element[0][3][0]) / 4
                        targetArr.append([centerX, element])

                # sort with the rightmost first
                targetArr.sort(reverse=True)

                if(len(targetArr) > 0):
                    for target in targetArr:
                        targetElement = target[1]

                        # if the value is already contained in the token
                        if(":" in targetElement[1] or "=" in targetElement[1]):
                            index = targetElement[1].find(":")
                            if(index == -1):
                                index = targetElement[1].find("=")
                            hasDigit = False
                            for c in range(index, len(targetElement[1])):
                                if(targetElement[1][c].isdigit()):
                                    hasDigit = True
                                    break
                            if(hasDigit):
                                self.ic50Value = targetElement[1]
                                break

                        centerX = targetArr[0][0]
                        topY = min(targetElement[0][0][1], targetElement[0][1][1])
                        downY = max(targetElement[0][2][1], targetElement[0][3][1])

                        # find all tokens to the right of the target name
                        elementArr = []
                        for element in positionResult:
                            localCenterX = (element[0][0][0] + element[0][1][0] + element[0][2][0] + element[0][3][0]) / 4
                            if(localCenterX > centerX):
                                localCenterY = (element[0][0][1] + element[0][1][1] + element[0][2][1] + element[0][3][1]) / 4
                                if(localCenterY >= topY and localCenterY <= downY):
                                    elementArr.append([localCenterX, element])
                        
                        # arrange the identified tokens from left to right, append them all into a string
                        elementArr.sort()
                        if(len(elementArr) > 0):
                            identifiedString = targetElement[1]
                            for element in elementArr:
                                identifiedString += element[1][1]
                                index = identifiedString.find("=")
                                if(index == -1):
                                    index = identifiedString.find(":")
                                if(index != -1 and (index + 1) < len(identifiedString)):
                                    self.ic50Value = identifiedString[index :]
                                else:
                                    self.ic50Value = identifiedString
                                

                                if(":" not in self.ic50Value and "=" not in self.ic50Value):
                                    self.ic50Value = ""
                                
                        # if the rightmost target name has no value, check the target names on its left
                        if(self.ic50Value):
                            break


        
        def get_compound_from_image(self, positionResult):
            # identify all compound names from the abstract image
            contentResult = []
            for element in positionResult:
                contentResult.append(element[1])
            compoundFound = False
            # identify all "compound" keyword and the name after it
            for word in contentResult:
                word = word.lower().strip()
                if(word == "compound"):
                    compoundFound = True
                    continue
                if("compound" in word):
                    pos = word.find("compound")
                    pos += 8
                    if(pos < len(word) and compoundName(word[pos:])):
                        self.compoundArr.append(word[pos:].strip())
                if(compoundFound):
                    if(compoundName(word)):
                        self.compoundArr.append(word)
                    compoundFound = False

            if(len(self.compoundArr) == 1):
                self.compound = self.compoundArr[0]


            if(not self.compound):
                compoundPosArr = []
                # find all keyword in the form of a compound name
                for element in positionResult:
                    if(compoundName(element[1]) and "nm" not in element[1].lower()):
                        compoundPosArr.append(element)
                
                # find the centerX of all identified keyword
                tempArr = []
                for element in compoundPosArr:
                    centerX = (element[0][0][0] + element[0][1][0] + element[0][2][0] + element[0][3][0]) / 4
                    tempArr.append([centerX, element[1]])
                tempArr.sort(reverse=True)

                # use the rightmost keyword as compound name
                if(len(tempArr) > 0):
                    self.compound = tempArr[0][1]

            self.compoundArr.clear()
        
# --------------------------------------------------------------------------------------------------------------
      

        def get_molecule_from_title_abstract(self):
            # find all identified molecule names inside of title
            doc = Document(self.titleText)
            for NR in doc.cems:
                self.moleculeArr.append(NR.text)
            tempArr = []
            for name in self.moleculeArr:
                if(moleculeName(name)):
                    tempArr.append(name)
            self.moleculeArr = tempArr # moleculeArr contains all chemistry named entities found in the title

            if(len(self.moleculeArr) == 1):
                self.molecule = self.moleculeArr[0]
                self.moleculeArr.clear()
            else:
                # if there's multiple named entities in title, then use abstract text to help identification
                titleMoleculeArr = self.moleculeArr.copy()
                self.moleculeArr.clear()
                
                doc = Document(self.abstractText)
                for NR in doc.cems:
                    self.moleculeArr.append(NR.text)
                textArr = []
                for name in self.moleculeArr:
                    if(moleculeName(name)):
                        textArr.append(name)
                
                if(len(titleMoleculeArr) == 0):
                    self.moleculeArr = textArr.copy()
                elif(len(textArr) == 0):
                    self.moleculeArr = titleMoleculeArr.copy()
                else:
                    # find named entities that appear both in title and in abstract text
                    self.moleculeArr = list(set(titleMoleculeArr).intersection(textArr))
                    if(len(self.moleculeArr) == 0):
                        self.moleculeArr = titleMoleculeArr.copy()
                
                if(len(self.moleculeArr) == 1):
                    self.molecule = self.moleculeArr[0]
        

        
        def get_compound_from_abstract(self):
            # identify compound name from abstract text, compound names are always in bold ( <b>keyword</b> )
            self.compoundArr = self.tableParser.boldAbstractTextArr.copy()
            # find all keywords in the form of compound name
            tempArr = []
            for name in self.compoundArr:
                if(compoundName(name)):
                    tempArr.append(name)

            # find the frequency of occurrence of each keyword in abstract text
            self.compoundArr.clear()
            for name in tempArr:
                nameFound = False
                for freqName in self.compoundArr:
                    if(freqName[1] == name):
                        freqName[0] += 1
                        nameFound = True
                        break
                if(not nameFound):
                    self.compoundArr.append([1, name])
            self.compoundArr.sort(reverse=True)

            tempArr.clear()
            if(len(self.compoundArr) > 0):
                # find all keywords with the highest frequency of occurrence
                maxFreq = self.compoundArr[0][0]
                for freqName in self.compoundArr:
                    if(freqName[0] == maxFreq):
                        tempArr.append([-1, freqName[1]])
                
                # find the position where the keyword is in abstract text
                # if there are multiple keywords have the highest frequency, select the one occurs last in text
                for posName in tempArr:
                    position = len(self.tableParser.boldAbstractTextArr) - 1
                    while(position >= 0):
                        if(self.tableParser.boldAbstractTextArr[position] == posName[1]):
                            posName[0] = position
                            break
                        position -= 1
                
                tempArr.sort(reverse=True)
                self.compoundArr = tempArr.copy()
                if(not self.compound and len(self.compoundArr) > 0):
                    self.compound = self.compoundArr[0][1]



        def get_ic50_from_abstract(self):
            # identify all ic50 values from abstract text
            ic50Found = False
            for word in self.abstractText.split():
                word = word.lower().strip()
                
                if(ic50(word)):
                    ic50Found = True
                    self.ic50Arr.append("")
                if(ic50Found):
                    self.ic50Arr[-1] += (word + " ")
                    if("nm" in word):
                        ic50Found = False
        


        # ki and kd values have similar patterns, hence they are generalized here
        # valueName: ki or kd
        def find_enzyme_cell_value_in_table(self, valueName): 
            
            if(not self.compound):
                return ["", ""]
            
            enzymeValue = []
            cellValue = []

            tableNum = 0
            for table in self.tables:
                tableNum += 1
                enzymeFound = False
                cellFound = False
                valueNameFound = False
                
                caption = table.caption.lower()
                descriptions = table.descriptions
                grid = table.grid
                # check if valueName is contained in the table title
                valueNameIndex = 0
                while(valueNameIndex != -1 and valueNameIndex < len(caption)):
                    valueNameIndex = caption.find(valueName, valueNameIndex)
                    if(valueNameIndex != -1):
                        # the character following the valueName cannot be a letter or a number
                        if(valueNameIndex + len(valueName) < len(caption) 
                            and not caption[valueNameIndex + len(valueName)].isalpha()
                            and not caption[valueNameIndex + len(valueName)].isdigit()):

                            valueNameFound = True
                            break
                        else:
                            valueNameIndex += 1

                # Identify the column number of header that contains the valueName and the "compound" keyword
                valueColNum = -1
                compoundColNum = -1
                for row in grid.header:
                    colNum = 0
                    for cell in row.cells:
                        if(valueColNum != -1 and compoundColNum != -1):
                            break
                        # different rules apply to ki and kd, sometimes "kinact/ki" appears in a cell, needs to eliminate
                        if(valueName == "ki"):
                            if("ki" in cell.lower() and "kinact" not in cell.lower()):
                                index = cell.lower().find("ki")
                                if(index + 2 < len(cell) and cell[index + 2].isspace()):
                                    valueColNum = colNum
                        elif(valueName == "kd"):
                            if("kd" in cell.lower()):
                                index = cell.lower().find("kd")
                                if(index + 2 < len(cell) and cell[index + 2].isspace()):
                                    valueColNum = colNum
                        elif(valueName == "ic50"):
                            if("ic50" in cell.lower()):
                                index = cell.lower().find("ic50")
                                if(index + 4 < len(cell) and cell[index + 4].isspace()):
                                    valueColNum = colNum
                        for compoundName in self.compoundKeywords:
                            if(compoundName in cell.lower()):
                                compoundColNum = colNum

                        colNum += 1
                
                # if valueName is not found in the title and not in the header or description, skip the current table
                foundInDescription = False
                if(valueColNum == -1 and not valueNameFound):
                    for description in table.descriptions:
                        if(valueName in description.lower()):
                            foundInDescription = True
                            break
                    if(not foundInDescription):
                        continue


                # try to identify whether the table is about enzyme or about cell from the title
                for enzymeName in self.enzymeKeywords:
                    if(enzymeName in caption):
                        enzymeFound = True
                        break
                if(not enzymeFound):
                    for cellName in self.cellKeywords:
                        if(cellName in caption):
                            cellFound = True
                
                # if the table is not about cell, try to found the header column that contains the target name
                targetColNum = -1
                if(not cellFound and self.focusedTarget):
                    for row in grid.header:
                        colNum = 0
                        for cell in row.cells:
                            if(self.focusedTarget in cell.lower()):
                                targetColNum = colNum
                                break
                            colNum += 1
                
                # if the "compound" keyword is not found in the header, use the leftmost column as the compound column
                # try to find the name of the compound from the compound column and record the row number
                if(compoundColNum == -1):
                    compoundColNum = 0
                compoundRowNum = -1
                rowNum = 0
                for row in grid.body:
                    for cell in row.cells:
                        if(cell.lower().strip() == self.compound):
                            compoundRowNum = rowNum
                            break
                    rowNum += 1
            
                if(not valueNameFound and valueColNum == -1 and foundInDescription and targetColNum != -1):
                    if(compoundRowNum != -1):
                        if(enzymeFound):
                            enzymeValue.append(grid.body[compoundRowNum].cells[targetColNum].strip())
                        else:
                            cellValue.append(grid.body[compoundRowNum].cells[targetColNum].strip())

                elif(not enzymeFound):        
                    if(compoundRowNum != -1):
                        cellValue.append(grid.body[compoundRowNum].cells[valueColNum].strip())
                
                elif(enzymeFound and targetColNum != -1):
                    if(compoundRowNum != -1):
                        enzymeValue.append(grid.body[compoundRowNum].cells[targetColNum].strip())
                
                elif(enzymeFound and targetColNum == -1 and valueColNum != -1):
                    if(compoundRowNum != -1):
                        enzymeValue.append(grid.body[compoundRowNum].cells[valueColNum].strip())
                
                # if neither enzyme keyword nor target name is found, only the title contains the valueName,
                # select one value from the compound row as its value
                elif(valueNameFound):
                    if(compoundRowNum != -1):
                        colNum = 0
                        for cell in grid.body[compoundRowNum].cells:
                            if(colNum != compoundColNum):
                                if(enzymeFound):
                                    enzymeValue.append(cell.strip())
                                else:
                                    cellValue.append(cell.strip())
                                break
                            colNum += 1
            
            if(len(enzymeValue) > 0):
                enzymeValue = enzymeValue[0]
            else:
                enzymeValue = ""
            if(len(cellValue) > 0):
                cellValue = cellValue[0]
            else:
                cellValue = ""
            return [enzymeValue, cellValue]
        


        def find_single_value_in_table(self, valueName):
            
            if(not self.compound):
                return ""

            for table in self.tables:
                
                valueNameFound = False
                index = 0
                while(index >= 0 and index < len(table.caption)):
                    index = table.caption.lower().find(valueName, index)
                    if(index != -1):
                        if((index + len(valueName)) < len(table.caption)):
                            if(table.caption[index + len(valueName)].isspace()):
                                valueNameFound = True
                                break
                        else:
                            valueNameFound = True
                            break
                        index += 1
                
                valueColNum = -1
                for row in table.grid.header:
                    colNum = 0
                    for cell in row.cells:
                        index = cell.lower().find(valueName)
                        if(index != -1):
                            if((index + len(valueName)) < len(cell)):
                                if(cell[index + len(valueName)].isspace()):
                                    valueColNum = colNum
                                    break
                                elif(valueName.lower() == "auc"):
                                    valueColNum = colNum
                                    break
                            else:
                                valueColNum = colNum
                                break
                        colNum += 1
                
                targetColNum = -1
                if(self.focusedTarget):
                    for row in table.grid.header:
                        colNum = 0
                        for cell in row.cells:
                            if(self.focusedTarget in cell.lower()):
                                targetColNum = colNum
                        colNum += 1
                

                if((valueColNum == -1 and not valueNameFound) or (valueNameFound and targetColNum == -1)):
                    continue

                
                compoundColNum = -1
                for row in table.grid.header:
                    colNum = 0
                    for cell in row.cells:
                        for compoundName in self.compoundKeywords:
                            if(compoundName in cell.lower()):
                                compoundColNum = colNum
                                break
                        colNum += 1
                
                if(compoundColNum == -1):
                    compoundColNum = 0
                
                compoundRowNum = -1
                rowNum = 0
                for row in table.grid.body:
                    for cell in row.cells:
                        if(cell.lower().strip() == self.compound):
                            compoundRowNum = rowNum
                            break
                    rowNum += 1

                if(compoundRowNum == -1):
                    continue
                
                if(valueColNum != -1):
                    return table.grid.body[compoundRowNum].cells[valueColNum]
                elif(valueNameFound and targetColNum != -1):
                    return table.grid.body[compoundRowNum].cells[targetColNum]
            
            return ""



        def get_ic50_from_body(self):
            [enzymeValue, cellValue] = self.find_enzyme_cell_value_in_table("ic50")
            if(not self.ic50Value):
                self.enzymeIc50 = enzymeValue
            else:
                self.enzymeIc50 = self.ic50Value
            self.cellIc50 = cellValue


        def get_kikd_from_body(self):
            [enzymeValue, cellValue] = self.find_enzyme_cell_value_in_table("ki")
            self.enzymeKi = enzymeValue
            self.cellKi = cellValue
            [enzymeValue, cellValue] = self.find_enzyme_cell_value_in_table("kd")
            self.enzymeKd = enzymeValue
            self.cellKd = cellValue
        
        
        def get_single_value_from_body(self):
            self.ec50 = self.find_single_value_in_table("ec50")
            self.ed50 = self.find_single_value_in_table("ed50")
            self.auc = self.find_single_value_in_table("auc")
            self.herg = self.find_single_value_in_table("herg")





def all_to_json(targetName):

    ACS.TARGET = targetName
    
    ACSUrl = ACS.prepare_query_url(targetName)

    (paper_count, queryResponse) = ACS.get_article_amount_and_response(ACSUrl)

    addressArr =  ACS.get_article_URLs(queryResponse)

    (dateArr, tableAddressArr, drug_molecule_count) = ACS.get_drug_molecule_paper(addressArr)


    result = {}
    result["target_name"] = targetName
    result["paper_count"] = paper_count
    result["paper_count_year"] = dateArr
    result["drug_molecule_count"] = drug_molecule_count
    result["drug_molecule_paper"] = []
    
    i = 0
    for articleURL in tableAddressArr:


        article = ACS.ACSArticle(articleURL)
        
        articleDict = {}
        articleDict["paper_id"] = i
        articleDict["paper_title"] = article.titleText
        articleDict["paper_author"] = article.authorArr
        articleDict["paper_year"] = article.year
        articleDict["paper_institution"] = article.instituition
        articleDict["paper_cited"] = article.paperCited
        articleDict["doi"] = article.doi
        articleDict["paper_journal"] = article.journal
        articleDict["paper_abstract_image"] = article.imgArr[0]
        articleDict["compound_name"] = article.compound

        medicinalDict = {}
        medicinalDict["Ki"] = article.enzymeKi
        medicinalDict["Kd"] = article.enzymeKd
        medicinalDict["IC50"] = article.enzymeIc50
        medicinalDict["selectivity"] = article.enzymeSelectivity
        vitroDict = {}
        vitroDict["Ki"] = article.cellKi
        vitroDict["Kd"] = article.cellKd
        vitroDict["IC50"] = article.cellIc50
        vitroDict["ec50"] = article.ec50
        vitroDict["selectivity"] = article.cellSelectivity
        vitroDict["hERG"] = article.herg
        vitroDict["solubility"] = article.cellSolubility
        vivoDict = {}
        vivoDict["ed50"] = article.ed50
        vivoDict["AUC"] = article.auc
        vivoDict["solubility"] = article.vivoSolubility

        articleDict["medicinal_chemistry_metrics"] = medicinalDict
        articleDict["pharm_metrics_vitro"] = vitroDict
        articleDict["pharm_metrics_vivo"] = vivoDict

        result["drug_molecule_paper"].append(articleDict)

        i += 1



    ScienceDirect.TARGET = targetName
    ScienceDirect.initialize_conditions(targetName)

    ((paper_count, drug_molecule_count), doiArr, paper_count_year) = ScienceDirect.retrieve_article_amount_and_doi()


    result["paper_count"] += paper_count
    result["drug_molecule_count"] += drug_molecule_count
    for SDYearCount in paper_count_year:
        yearFound = False
        for ACSyearCount in result["paper_count_year"]:
            if(ACSyearCount[0] > SDYearCount[0]):
                break
            elif(ACSyearCount[0] < SDYearCount[0]):
                continue
            else:
                ACSyearCount[1] += SDYearCount[1]
                yearFound = True
        
        if(not yearFound):
            result["paper_count_year"].append(SDYearCount)
        

    for articleDOI in doiArr:

        article = ScienceDirect.ScienceDirectArticle(articleDOI)


        articleDict = {}
        articleDict["paper_id"] = i
        articleDict["paper_title"] = article.titleText
        articleDict["paper_author"] = article.authorArr
        articleDict["paper_year"] = article.year
        articleDict["paper_institution"] = article.institution
        articleDict["paper_cited"] = article.paperCited
        articleDict["doi"] = article.doi
        articleDict["paper_journal"] = article.journal
        articleDict["paper_abstract_image"] = article.imgURL
        articleDict["compound_name"] = article.compound

        medicinalDict = {}
        medicinalDict["Ki"] = article.enzymeKi
        medicinalDict["Kd"] = article.enzymeKd
        medicinalDict["IC50"] = article.enzymeIc50
        vitroDict = {}
        vitroDict["Ki"] = article.cellKi
        vitroDict["Kd"] = article.cellKd
        vitroDict["IC50"] = article.cellIc50
        vitroDict["ec50"] = article.ec50
        vitroDict["hERG"] = article.herg
        vivoDict = {}
        vivoDict["ed50"] = article.ed50
        vivoDict["AUC"] = article.auc

        articleDict["medicinal_chemistry_metrics"] = medicinalDict
        articleDict["pharm_metrics_vitro"] = vitroDict
        articleDict["pharm_metrics_vivo"] = vivoDict

        result["drug_molecule_paper"].append(articleDict)

        i += 1



if __name__ == '__main__':
    all_to_json("janus kinase")
