from six import b
import molecular_Structure_Similarity as similarity
import paper_count_per_year
from torch.nn.functional import fractional_max_pool2d_with_indices
import re
from numpy.core.arrayprint import format_float_scientific
import requests
from html.parser import HTMLParser
from chemdataextractor import Document
import easyocr
import json
from elsapy.elsclient import ElsClient
from elsapy.elsdoc import FullDoc
import chemschematicresolver as csr
import Clinical_View as clinical
import itertools
from molecular_Structure_Similarity import molecularSimles
import nlp_implementation as nlp
import os
import traceback
import find_index
import sys
import glob


modelDict = nlp.load_pre_trained_nlp_model()

outputArr = []

acsSmilesArr = []
sdSmilesArr = []

FILEID = 0

TARGETNAME = sys.argv[1]


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
            if(c == "-"):
                continue
            if(not onlyDigit and not c.isalpha()):
                return False
            if(onlyDigit and c.isalpha()):
                onlyDigit = False
            if(not c.isdigit() and not c.isalpha()):
                return False
        return True
    if(len(string) >= 2 and string[0].isalpha()):
        onlyLetter = True
        for c in string:
            if(c == "-"):
                continue
            if(not onlyLetter and not c.isdigit()):
                return False
            if(onlyLetter and c.isdigit()):
                onlyLetter = False
            if(not c.isalpha() and not c.isdigit()):
                return False
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
            
            self.imgURL = ""
            self.keywordFound = False

            self.kFound = False



        def handle_starttag(self, tag, attrs):
            if(self.keywordFound and self.imgURL):
                exitParser(self)

            if (self.complete):
                return
            elif (tag == "div" and len(attrs) == 1 and "NLM_p" in attrs[0][1]):
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
            if(tag == "div" and len(attrs) == 1 and attrs[0][1] == "article_content"):
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
                    self.imgURL = ACS.DOMAIN + link
            

        
        def handle_data(self, data):
            if (self.complete):
                return
            
            if(self.contentFound):
                stringList = ["IC50", "EC50", "ED50"]            
                if(any(substring in data for substring in stringList)):
                    self.keywordFound = True
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
                        self.keywordFound = True
                elif(self.ICFound):
                    if(len(data) >= 2 and data[:2] == "50"):
                        self.keywordFound = True
                    else:
                        self.ICFound = False
                elif(len(data) >= 2 and (data[-2:] in ["IC", "EC", "ED"])):
                    self.ICFound = True
                if(len(data) >= 1 and (data[-1].lower() == "k")):
                    self.kFound = True
                elif(self.kFound):
                    if(len(data) >= 1 and (data[0].lower() == "i" or data[0].lower() == "d")):
                        self.kFound = False
                        self.keywordFound = True
                    else:
                        self.kFound = False
                
                elif(self.dateFound):
                    self.date = data.split()[-1]


        
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
        if(not ACS.QueryParser.nextPageURL):
            ACS.QueryParser.hasNextPage = False
        while(ACS.QueryParser.hasNextPage):
            response = requests.get(ACS.QueryParser.nextPageURL, headers = {"User-Agent": "Mozilla/5.0"})
            queryParser.feed(response.text)
            if(not ACS.QueryParser.nextPageURL):
                ACS.QueryParser.hasNextPage = False

        return queryParser.addressArr



    def get_drug_molecule_paper(addressArr):
        
        global FILEID
        global outputArr

        print("2.1")
        drugPaperCount = 0
        tableAddressArr = []
        dateArr = []
        simlesDict = {}
        positionResultDict = {}
        print("2.2")


        outputArr.append("all acs articles")

        for address in addressArr:

            outputArr.append(f"fileId: {address}")

            print(f"address: {address}")
            print("2.3")
            contentParser = ACS.ContentParser()
            print("2.4")
            simles = ""
            positionResult = []
            try:                
                # articleResponse = requests.get(address, headers = {"User-Agent": "Mozilla/5.0"})
                # contentParser.feed(articleResponse.text)
                print("2.5")
                with open(f"files/{ACS.TARGET}/file{address}.html", encoding="utf-8") as inputFile:
                    contentParser.feed(inputFile.read())
                    print("2.6")
            except AssertionError as ae:
                pass
                print("2.7")

            print("2.8")
            found = False
            for yearOccur in dateArr:
                if (yearOccur[0] == contentParser.date):
                    found = True
                    yearOccur[1] += 1
                    break
            if(not found):
                dateArr.append([contentParser.date, 1]) 
            print("2.9")    
            
            print(f"keywordFound: {contentParser.keywordFound}")
            print(f"imgURL: {bool(contentParser.imgURL)}")
            if(contentParser.keywordFound and contentParser.imgURL):

                # image = requests.get(contentParser.imgURL).content
                # with open("abstract_image/image.jpeg", "wb") as handler:
                #     handler.write(image)
                print("2.10")
                try:
                    (simles, positionResult) = molecularSimles(f"images/{ACS.TARGET}/image{address}.jpeg")
                except:
                    simles = ""
                    print("2.11")
                print("2.12")

            print(f"smiles: {bool(simles)}")
            outputArr.append(f"smiles: {bool(simles)}")
            print("2.13")
            # if(simles):
                
            print("2.14")
            # os.rename("abstract_image/image.jpeg", f"abstract_image/image{FILEID}.jpeg")

            hasImage = True
            if(len(positionResult) == 0):
                reader = easyocr.Reader(["en"], gpu=False)
                try:
                    positionResult = reader.readtext(f"images/{ACS.TARGET}/image{address}.jpeg")
                except:
                    hasImage = False
            
            if(hasImage):
                drugPaperCount += 1
                tableAddressArr.append(address)
                simlesDict[address] = simles
                positionResultDict[address] = positionResult

            
            FILEID += 1
        
        print("2.15")
        dateArr.sort()
        return (dateArr, tableAddressArr, drugPaperCount, simlesDict, positionResultDict)



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
                self.altInstitution = ""
                self.paperCited = -1
                self.doi = ""
                self.journal = ""

                self.authorFound = False
                self.dateFound = False
                self.institutionFound = False
                self.altInstitutionFound = False
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
                self.boldParagraphText = ""
                self.boldParagraphFound = False
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
                if(not self.altInstitution and tag == "div" and len(attrs) == 1 and attrs[0][1] == "loa-info-affiliations-info"):
                    self.altInstitutionFound = True



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
                    self.abstractBoldText += "<b> "

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
                    self.boldParagraphFound = True
                    self.boldParagraphText += "<b> "

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
                if(self.altInstitutionFound):
                    self.altInstitution = data


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
                    self.boldParagraphText += data
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
                if(self.altInstitutionFound and tag == "div"):
                    self.altInstitutionFound = False


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
                    self.abstractBoldText += " </b>"
                
                # handle body text
                
                if(self.boldParagraphFound and tag == "b"):
                    self.boldParagraphText += " </b>"
                    self.boldParagraphFound = False
                if(self.sectionTitleFound and tag == "div"):
                    self.sectionTitleFound = False
                # found the end of a paragraph, append the content to the last section
                if(self.paragraphFound and tag == "div" and self.paragraphDivCount == 1):
                    if(len(self.bodyText.sections) == 0):
                        newSection = BodyText.Section("")
                        self.bodyText.sections.append(newSection)
                    if(len(self.bodyText.sections[-1].paragraphs) == 0):
                        newParagraph = BodyText.Section.Paragraph()
                        self.bodyText.sections[-1].paragraphs.append(newParagraph)
                    self.bodyText.sections[-1].paragraphs[-1].contents.append(self.paragraphText)
                    self.bodyText.sections[-1].paragraphs[-1].boldContents.append(self.boldParagraphText)
                    self.paragraphText = ""
                    self.boldParagraphText = ""
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
                    self.paragraphBoldText += " </b>"
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
        def __init__(self, articleURL, positionResult):

            self.articleURL = articleURL
            self.positionResult = positionResult

            self.authorArr = []
            self.year = -1
            self.institution = ""
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

            self.compoundSet = set()
            self.compoundDict = {}


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


            self.compoundNameDrug = ""

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
            self.tHalf = ""
            self.bioavailability = ""

            self.nlpCompound = False

            print("3.1.1")
            self.retrieve_values()




        def retrieve_values(self):

            print("3.1.2")
            if(not self.ABBREVIATION or not self.FULLNAME):
                self.get_FULLNAME_ABBREVIATION()
            print("3.1.3")
            self.retrieve_article_information()
            print("3.1.3.1")
            self.retrieve_nlp_data()
            print("3.1.4")
            # if(not self.focusedTarget):
            self.retrieve_target()

            print("3.1.4.1")
            self.retrieve_compound_amount()
            # positionResult = self.retrieve_image_text()
            print("3.1.5")
            # if(not self.enzymeIc50 and not self.cellIc50):
            self.get_ic50_from_image(self.positionResult)
            print("3.1.6")
            # if(not self.compound):
            self.get_compound_from_image(self.positionResult)
            print("3.1.7")
            self.get_molecule_from_title_abstract()
            print("3.1.8")
            self.get_compound_from_abstract()
            print("3.1.9")
            # if(not self.enzymeIc50 and not self.cellIc50):
            self.get_ic50_from_abstract()
            print("3.1.10")
            self.get_multiple_values_from_body()
            print("3.1.11")
            self.get_single_value_from_body()
            print("3.1.12")
        


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

            global outputArr

            self.tableParser = ACS.ACSArticle.TableParser()
            # open a file locally, should be retrieved through http request in real programs
            # response = requests.get(self.articleURL)

            # parse the given html file with TableParser()
            try:
                with open(f"files/{ACS.TARGET}/file{self.articleURL}.html", encoding="utf-8") as inputFile:
                    self.tableParser.feed(inputFile.read())
                # self.tableParser.feed(response.text)
            except AssertionError as ae:
                pass
            

            self.titleText = self.tableParser.title
            self.imgArr = self.tableParser.imgArr
            self.abstractText = self.tableParser.abstractText
            self.bodyText = self.tableParser.bodyText
            self.tables = self.tableParser.tables
            self.authorArr = self.tableParser.authorArr
            self.year = self.tableParser.year

            if(len(self.tableParser.institution) == 0):
                self.institution = ""
            else:
                self.institution = self.tableParser.institution[0]
            
            if(not self.institution):
                self.institution = self.tableParser.altInstitution

            for table in self.tables:
                if(not table.grid.header and len(table.grid.body) >= 2):
                    table.grid.header.append(table.grid.body[0])
                    table.grid.body = table.grid.body[1:]
            
            self.paperCited = self.tableParser.paperCited
            self.doi = self.tableParser.doi
            self.journal = self.tableParser.journal

            outputArr.append(f"title: {self.titleText}")




        def retrieve_nlp_data(self):

            global outputArr
            
            print("3.1.3.2")
            nlpDict = nlp.get_nlp_results(self.tableParser, **modelDict)
            print(f"doi: {self.doi}")
            print(f"single_dict: {nlpDict['single_dict']}")
            print(f"original_dict: {nlpDict['original_dict']}")
            nlpDict = nlpDict["single_dict"]
            
            outputArr.append(nlpDict)
            
            print("3.1.3.3")
            if("compound" in nlpDict):
                
                compound = ""
                for token in nlp.def_tokenizer(nlpDict["compound"]):
                    
                    if(token == "<b>"):
                        continue
                    if(token == "</b>"):
                        break
                    compound += token
                
                if(compound and compoundName(compound)):
                    self.compound = compound
                    self.nlpCompound = True
            
            print("3.1.3.4")
            if("compound_drug" in nlpDict):

                compound_drug = ""
                for token in nlp.def_tokenizer(nlpDict["compound"]):

                    if(token == "<b>" or token == "</b>"):
                        continue
                    compound_drug += token
                
                if(compound_drug and self.is_compound_name_drug(compound_drug)):
                    self.compoundNameDrug = compound_drug

            print("3.1.3.5")
            if("target" in nlpDict):

                tokenArr = nlp.def_tokenizer(nlpDict["target"])
                if(len(tokenArr) == 1):
                    
                    target = tokenArr[0].strip()
                    letterFound = False
                    digitFound = False
                    isTargetName = True
                    for c in target:
                        if(not digitFound and c.isalpha()):
                            letterFound = True
                        elif(letterFound and c.isdigit()):
                            digitFound = True
                        else:
                            isTargetName = False
                            break
                    
                    if(not letterFound or not digitFound):
                        isTargetName = False

                    if(isTargetName):
                        self.focusedTarget = target.lower().strip()

            global TARGETNAME
            self.focusedTarget = TARGETNAME.lower()
            self.ABBREVIATION = TARGETNAME.lower()
            self.FULLNAME = TARGETNAME.lower()
            
            nmKeyArr = ["ic50_mc", "ki_mc", "kd_mc", "ic50_ce", "ki_ce", "kd_ce", "ec50_ce"]            
            
            print("3.1.3.6")
            for key in nmKeyArr:
                if(key in nlpDict):

                    value = ""
                    unit = ""
                    valueFound = False
                    for token in nlp.def_tokenizer(nlpDict[key]):

                        if(not value and not valueFound and token.isdigit()):
                            value += token
                            valueFound = True                        
                        elif(valueFound and (token.isdigit() or token == ".")):
                            value += token
                        elif(valueFound and not token.isdigit()):
                            for c in token:
                                if(c.isdigit() or c == "."):
                                    value += c
                                else:
                                    break
                            valueFound = False
                        if("nm" in token.lower() or "μm" in token.lower()):
                            unit = token
                        if(value and unit and not valueFound):
                            break
                    
                    if(value):
                        try:
                            value = float(value)
                        except ValueError:
                            value = -1
                        
                        if(value != -1 and (not unit or (unit and "m" in unit.lower()))):
                            if(unit and unit.lower().strip() == "μm"):
                                value *= 1000

                            if(key == "ic50_mc"):
                                self.enzymeIc50 = value
                            elif(key == "ki_mc"):
                                self.enzymeKi = value
                            elif(key == "kd_mc"):
                                self.enzymeKd = value
                            elif(key == "ic50_ce"):
                                self.cellIc50 = value
                            elif(key == "ki_ce"):
                                self.cellKi = value
                            elif(key == "kd_ce"):
                                self.cellKd = value
                            elif(key == "ec50_ce"):
                                self.ec50 = value
            

            selectivityKeyArr = ["selectivity_mc", "selectivity_ce"]

            print("3.1.3.7")
            for key in selectivityKeyArr:
                if(key in nlpDict):
                    
                    tokenArr = nlp.def_tokenizer(nlpDict[key])

                    digits = ""
                    for token in tokenArr:

                        if(digits):
                            break

                        if("fold" in token):
                            for c in token:
                                if(c.isdigit() or c == "."):
                                    digits += c
                    
                    
                    if(digits):

                        try:
                            digits = int(digits)
                        except ValueError:
                            digits = -1

                        if(digits != -1):
                            if(key == "selectivity_mc"):
                                self.enzymeSelectivity = digits
                            elif(key == "selectivity_ce"):
                                self.cellSelectivity = digits

            
            microUnitArr = ["herg_ce", "solubility_ce", "ed50_an", "solubility_an"]
            
            print("3.1.3.8")
            for key in microUnitArr:
                if(key in nlpDict):

                    value = ""
                    unit = ""
                    valueFound = False
                    tokenArr = nlp.def_tokenizer(nlpDict[key])
                    for token in tokenArr:

                        if(not value and not valueFound and token.isdigit()):
                            value += token
                            valueFound = True
                        elif(valueFound and (token.isdigit() or token == ".")):
                            value += token
                        elif(valueFound and not token.isdigit()):
                            for c in token:
                                if(c.isdigit() or c == "."):
                                    value += c
                                else:
                                    break
                            valueFound = False
                        if("nm" in token.lower() or "μm" in token.lower() or "mm" in token.lower()
                            or "ng" in token.lower() or "μg" in token.lower() or "mg" in token.lower()):
                            unit = token
                        if(value and unit and not valueFound):
                            break

                    
                    if(value):
                        try:
                            value = float(value)
                        except ValueError:
                            value = -1
                        
                        if(value != -1):
                            if(unit and ("nm" in unit.lower() or "ng" in unit.lower())):
                                value /= 1000
                            if(unit and ("mm" in unit.lower() or "mg" in unit.lower())):
                                value *= 1000
                            
                            if(key == "herg_ce"):
                                self.herg = value
                            elif(key == "solubility_ce"):
                                self.cellSolubility = value
                            elif(key == "ed50_an"):
                                self.ed50 = value
                            elif(key == "solubility_an"):
                                self.vivoSolubility = value
            
            print("3.1.3.9")
            if("t_half_an" in nlpDict):

                tokenArr = nlp.def_tokenizer(nlpDict["t_half_an"])
                value = ""
                unit = ""
                valueFound = False
                for token in tokenArr:
                        if(not value and not valueFound and token.isdigit()):
                            value += token
                            valueFound = True
                        elif(valueFound and (token.isdigit() or token == ".")):
                            value += token
                        elif(valueFound and not token.isdigit()):
                            for c in token:
                                if(c.isdigit() or c == "."):
                                    value += c
                                else:
                                    break
                            valueFound = False
                        if("min" in token.lower() or "h" in token.lower()):
                            unit = token
                        if(value and unit and not valueFound):
                            break
                        
                if(value):
                    try:
                        value = float(value)
                    except ValueError:
                        value = -1
                    
                    if(value != -1):
                        if(unit and unit.lower() == "min"):
                            value /= 60
                        
                        self.tHalf = value
            
            print("3.1.3.10")
            if("auc_an" in nlpDict):

                tokenArr = nlp.def_tokenizer(nlpDict["auc_an"])
                value = ""
                unit = ""
                valueFound = False
                for token in tokenArr:
                    if(not value and not valueFound and token.isdigit()):
                        value += token
                        valueFound = True
                    elif(valueFound and (token.isdigit() or token == ".")):
                        value += token
                    elif(valueFound and not token.isdigit()):
                        for c in token:
                            if(c.isdigit() or c == "."):
                                value += c
                            else:
                                break
                        valueFound = False
                    if("g" in token.lower() and "l" in token.lower() and "/" in token.lower()):
                        unit = token
                    if(value and unit and not valueFound):
                        break

                if(value):
                    try:
                        value = float(value)
                    except ValueError:
                        value = -1

                    if(value != -1):
                        if(unit):
                            if("μg" in unit.lower()):
                                value *= 1000
                            if("ml" not in unit.lower() and "l" in unit.lower()):
                                value /= 1000
                        
                        self.auc = value

            print("3.1.3.11")
            if("bioavailability_an" in nlpDict):

                tokenArr = nlp.def_tokenizer(nlpDict["bioavailability_an"])

                value = ""
                valueFound = False
                for token in tokenArr:
                    if(not value and not valueFound and token.isdigit()):
                        value += token
                        valueFound = True
                    elif(valueFound and (token.isdigit() or token == ".")):
                        value += token
                    elif(valueFound and not token.isdigit()):
                        for c in token:
                            if(c.isdigit() or c == "."):
                                value += c
                            else:
                                break
                        valueFound = False
                        break
 
                
                if(value):
                    try:
                        value = float(value)
                    except ValueError:
                        value = -1
                    
                    if(value != -1):
                        self.bioavailability = value            





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



        # def retrieve_image_text(self):
        #     image = requests.get(self.imgArr[0]).content
        #     with open("abstract_image/image.jpeg", "wb") as handler:
        #         handler.write(image)

        #     # identify all text within the abstract image
        #     reader = easyocr.Reader(["en"], gpu = False)
        #     # retrieve picture through http request
        #     positionResult = reader.readtext("abstract_image/image.jpeg")

        #     return positionResult
        
        def retrieve_compound_amount(self):

            boldContentSet = set()

            abstractBoldArr = re.findall("<b>.*?</b>", self.tableParser.abstractBoldText)
            for token in abstractBoldArr:
                token = token.replace("(", " ")
                token = token.replace(")", " ")
                index = token.find("</b>")
                name = token[3:index].strip()
                boldContentSet.add(name)
                if(name in self.compoundDict):
                    self.compoundDict[name] += 1
                else:
                    self.compoundDict[name] = 1
            
            for section in self.bodyText.sections:
                for paragraph in section.paragraphs:
                    for token in paragraph.boldContents:
                        abstractBoldArr = re.findall("<b>.*?</b>", token)
                        for item in abstractBoldArr:
                            item = item.replace("(", " ")
                            item = item.replace(")", " ")
                            index = item.find("</b>")
                            name = item[3:index].strip()
                            boldContentSet.add(name)
                            if(name in self.compoundDict):
                                self.compoundDict[name] += 1
                            else:
                                self.compoundDict[name] = 1

            self.compoundSet = boldContentSet

            # for table in self.tables:
                
            #     compoundColNum = -1
            #     for row in table.grid.header:

            #         if(compoundColNum != -1):
            #             break

            #         colNum = 0
            #         for cell in row.cells:

            #             if(compoundColNum != -1):
            #                 break

            #             for keyword in self.compoundKeywords:
            #                 if(keyword in cell.lower()):
            #                     compoundColNum = colNum
            #                     break
                        
            #             colNum += 1
                    
            #     if(compoundColNum == -1):
            #         continue
                
            #     for row in table.grid.body:
            #         if(compoundColNum >= len(row.cells)):
            #             continue
            #         if(compoundName(row.cells[compoundColNum])):
            #             self.compoundSet.add(row.cells[compoundColNum])



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
        def is_compound_name_drug(self, name):

            if(not name):
                return False
            
            name = name.strip()
            letterFound = False
            digitFound = False
            for c in name:
                if(not digitFound and c.isalpha()):
                    letterFound = True
                elif(c.isdigit()):
                    digitFound = True
                if(digitFound and c.isalpha()):
                    return False
            
            if(letterFound and digitFound):
                return True
            else:
                return False



        def get_molecule_from_title_abstract(self):
            # find all identified molecule names inside of title
            doc = Document(self.titleText)
            for NR in doc.cems:
                self.moleculeArr.append(NR.text)
                if(not self.compoundNameDrug and self.is_compound_name_drug(NR.text)):
                    self.compoundNameDrug = NR.text.strip()
            
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

            if(self.nlpCompound):
                return

            # identify compound name from abstract text, compound names are always in bold ( <b>keyword</b> )
            self.compoundArr = self.tableParser.boldAbstractTextArr.copy()
            # find all keywords in the form of compound name
            tempArr = []
            for name in self.compoundArr:
                if(compoundName(name)):
                    tempArr.append(name)

            if(len(tempArr) == 0):
                if(len(self.compoundDict) == 0 or self.compound in self.compoundDict):
                    return
                else:
                    name = ""
                    maxFreq = -1
                    for key in self.compoundDict.keys():
                        if(self.compoundDict[key] > maxFreq):
                            maxFreq = self.compoundDict[key]
                            name = key
                    self.compound = name.strip()
                    return


            compoundFound = False
            if(self.compound):
                for name in tempArr:
                    if(self.compound in name):
                        compoundFound = True
                        break
            
            if(not compoundFound):
                self.compound = ""            


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
        
        


        def find_values_in_table(self, valueName):

            if(not self.compound):
                return ["", "", ""]
            
            mediValue = ""
            vitroValue = ""
            vivoValue = ""

            print(f"\n\nvalueName: {valueName}")
            for table in self.tables:
  
                print(f"\n\ntitle: {table.caption}")
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
                print(f"titleFound: {titleFound}")

                valueColNum = -1
                valueUnit = ""
                for row in table.grid.header:
                    
                    if(valueColNum != -1):
                        break
                    
                    colNum = 0
                    for cell in row.cells:
                        
                        index = cell.find(valueName)
                        if(index != -1):

                            if(valueName[-1].isdigit() or (index + len(valueName)) >= len(cell)):
                                valueColNum = colNum

                                if("nm" in cell.lower()):
                                    valueUnit = "nano"
                                elif("μm" in cell.lower()):
                                    valueUnit = "micro"

                                break

                            else:
                                if(cell[index + len(valueName)].isspace()):
                                    valueColNum = colNum

                                    if("nm" in cell.lower()):
                                        valueUnit = "nano"
                                    elif("μm" in cell.lower()):
                                        valueUnit = "micro"

                                    break


                        colNum += 1
                
                print(f"valueColNum: {valueColNum}")


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
                
                print(f"1: compoundColNum: {compoundColNum}")
                

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
                            colNum += 1
                            continue
                        
                        if(cell.lower().strip() == self.compound):
                            compoundRowNum = rowNum
                            break

                        colNum += 1
                    rowNum += 1

                
                print(f"compounRowNum: {compoundRowNum}")
                

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
                or "vivo" in table.caption.lower() or "preclinical" in table.caption.lower() 
                or "pk" in table.caption.lower()):
                    vivoFound = True

                print(f"1: medifound: {mediFound}, vitroFound: {vitroFound}, vivoFound: {vivoFound}")


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

                
                print(f"targetColNum: {targetColNum}")


                if(valueColNum == -1 and targetColNum == -1):
                    if(not vitroFound):
                        continue
                    else:
                        if(not titleFound):
                            continue


                value = ""
                extractColNum = -1
                if(titleFound):
                    if(targetColNum != -1):
                        value = table.grid.body[compoundRowNum].cells[targetColNum]
                        extractColNum = targetColNum

                    else:
                        if(valueColNum != -1):
                            value = table.grid.body[compoundRowNum].cells[valueColNum]
                            extractColNum = valueColNum
                else:
                    if(valueColNum != -1):
                        value = table.grid.body[compoundRowNum].cells[valueColNum]
                        extractColNum = valueColNum
                
                if(valueColNum == -1 and targetColNum == -1 and vitroFound 
                and table.grid.columnNum > 1):
                    
                    for colNum in range(0, table.grid.columnNum):
                        
                        if(colNum == compoundColNum):
                            continue
                        value = table.grid.body[compoundRowNum].cells[colNum]
                        extractColNum = colNum
                        break

                
                
                if(value and not valueUnit):
                    microFound = False
                    for row in table.grid.header:

                        if(microFound):
                            break
                        
                        colNum = 0
                        for cell in row.cells:
                            if(colNum != extractColNum):
                                colNum += 1
                                continue
                            if("μm" in cell.lower()):
                                microFound = True
                                break
                            colNum += 1
                    
                    if(microFound):
                        value = "μm" + value

                
                if(valueUnit):
                    if(valueUnit == "micro"):
                        value = "μm" + value
                
                
                if(not mediFound and not vitroFound and not vivoFound):
                    for row in table.grid.header:
                        cell = ""
                        if(extractColNum >= len(row.cells)):
                            cell = row.cells[-1]
                        else:
                            cell = row.cells[extractColNum]
                        
                        if("enzyme" in cell.lower() or "enzymatic" in cell.lower()):
                            mediFound = True
                            break
                        elif("cell" in cell.lower() or "cellular" in cell.lower() 
                        or "vitro" in cell.lower()):
                            vitroFound = True
                            break
                        elif("pharmacokinetic" in cell.lower() or "preliminary" in cell.lower()
                        or "vivo" in cell.lower() or "preclinical" in cell.lower()
                        or "pk" in cell.lower()):
                            vivoFound = True
                            break
                        
                print(f"2: medifound: {mediFound}, vitroFound: {vitroFound}, vivoFound: {vivoFound}")

                if(not mediFound and not vitroFound and not vivoFound):
                    mediFound = True
                
                if(mediFound):
                    mediValue = value
                elif(vitroFound):
                    vitroValue = value
                else:
                    vivoValue = value


            return[mediValue, vitroValue, vivoValue]



        def find_single_value_in_table(self, valueName):

            print(f"\n\nvalueName: {valueName}")
            
            if(not self.compound):
                return ""

            value = ""

            for table in self.tables:

                print(f"\n\n{table.caption}")
                
                valueNameFound = False
                index = 0
                while(index >= 0 and index < len(table.caption)):
                    index = table.caption.find(valueName, index)
                    if(index != -1):
                        if((index + len(valueName)) < len(table.caption)):
                            if(table.caption[index + len(valueName)].isspace()):
                                valueNameFound = True
                                break
                        else:
                            valueNameFound = True
                            break
                        index += 1
                
                valueUnit = ""
                valueColNum = -1

                for row in table.grid.header:

                    if(valueColNum != -1):
                        break

                    colNum = 0
                    for cell in row.cells:
                        index = cell.find(valueName)
                        if(index != -1):
                            if((index + len(valueName)) < len(cell)):
                                if(cell[index + len(valueName)].isspace()):
                                    valueColNum = colNum

                                    if("nm" in cell.lower()):
                                        valueUnit = "nano"
                                    elif("μm" in cell.lower()):
                                        valueUnit = "micro"

                                    break
                                elif(valueName == "AUC"):
                                    valueColNum = colNum
                                    break
                            else:
                                valueColNum = colNum

                                if("nm" in cell.lower()):
                                    valueUnit = "nano"
                                elif("μm" in cell.lower()):
                                    valueUnit = "micro"

                                break

                        if(index == -1 and valueName == "bioavailability"):
                            if("F" in cell and "%" in cell):
                                valueColNum = colNum
                                break
                        elif(index == -1 and valueName == "t_half"):
                            if(("half" in cell.lower() and "life" in cell.lower()) 
                                or ("t" in cell.lower() and "1/2" in cell.lower())):
                                valueColNum = colNum
                                break
                        
                        colNum += 1

                print(f"valueColNum: {valueColNum}")
                
                targetColNum = -1
                if(self.focusedTarget):
                    for row in table.grid.header:
                        colNum = 0
                        for cell in row.cells:
                            if(self.focusedTarget in cell):
                                targetColNum = colNum
                        colNum += 1
                

                print(f"targetColNum: {targetColNum}")

                if((valueColNum == -1 and not valueNameFound) or (valueNameFound and targetColNum == -1)):
                    continue

                
                compoundColNum = -1
                for row in table.grid.header:
                    colNum = 0
                    for cell in row.cells:
                        for compoundName in self.compoundKeywords:
                            if(compoundName in cell):
                                compoundColNum = colNum
                                break
                        colNum += 1
                
                if(compoundColNum == -1):
                    compoundColNum = 0

                print(f"compoundColNum: {compoundColNum}")
                
                compoundRowNum = -1
                rowNum = 0
                for row in table.grid.body:
                    if(compoundRowNum != -1):
                        break

                    colNum = 0
                    for cell in row.cells:
                        if(colNum != compoundColNum):
                            colNum += 1
                            continue
                        if(cell.strip() == self.compound):
                            compoundRowNum = rowNum
                            break
                        colNum += 1
                    rowNum += 1

                print(f"compoundRowNum: {compoundRowNum}")

                if(compoundRowNum == -1):
                    continue

                
                
                value = ""
                if(valueColNum != -1):
                    value = table.grid.body[compoundRowNum].cells[valueColNum]
                elif(valueNameFound and targetColNum != -1):
                    value = table.grid.body[compoundRowNum].cells[targetColNum]


                if(value and not valueUnit):
                    microFound = False
                    for row in table.grid.header:

                        if(microFound):
                            break

                        for cell in row.cells:
                            if("μm" in cell.lower()):
                                microFound = True
                                break
                    
                    if(microFound):
                        value = "μm" + value

                    return value

                
                if(valueUnit):
                    if(valueUnit == "micro"):
                        value = "μm" + value
                    
                    return value

            
            return value



        def get_multiple_values_from_body(self):
            
            [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("IC50")
            # if(not self.enzymeIc50):
            #     if(not self.ic50Value):
            #         self.enzymeIc50 = enzymeValue
            #     else:
            #         self.enzymeIc50 = self.ic50Value
            # if(not self.cellIc50):
            #     self.cellIc50 = cellValue
            if(enzymeValue):
                self.enzymeIc50 = enzymeValue
            if(cellValue):
                self.cellIc50 = cellValue
            
            [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("Ki")
            # if(not self.enzymeKi):
            #     self.enzymeKi = enzymeValue
            # if(not self.cellKi):    
            #     self.cellKi = cellValue
            if(enzymeValue):
                self.enzymeKi = enzymeValue
            if(cellValue):
                self.cellKi = cellValue
            
            [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("Kd")
            # if(not self.enzymeKd):    
            #     self.enzymeKd = enzymeValue
            # if(not self.cellKd):
            #     self.cellKd = cellValue
            if(enzymeValue):
                self.enzymeKd = enzymeValue
            if(cellValue):
                self.cellKd = cellValue

            # if(not self.enzymeKd or not self.cellKd):
            #     [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("KD")
            #     if(not self.enzymeKd):    
            #         self.enzymeKd = enzymeValue
            #     if(not self.cellKd):
            #         self.cellKd = cellValue       
            if(not self.enzymeKd or not self.cellKd):
                [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("KD")
                if(enzymeValue):
                    self.enzymeKd = enzymeValue
                if(cellValue):
                    self.cellKd = cellValue         
            
            [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("selectivity")
            # if(not self.enzymeSelectivity):
            #     self.enzymeSelectivity = enzymeValue
            # if(not self.cellSelectivity):    
            #     self.cellSelectivity = cellValue
            if(enzymeValue):
                self.enzymeSelectivity = enzymeValue
            if(cellValue):
                self.cellSelectivity = cellValue
            
            [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("solubility")
            # if(not self.cellSolubility):
            #     self.cellSolubility = cellValue
            # if(not self.vivoSolubility):    
            #     self.vivoSolubility = vivoValue
            if(cellValue):
                self.cellSolubility = cellValue
            if(vivoValue):
                self.vivoSolubility = vivoValue


        def get_vivo_value_in_table(self, valueName):

            print("\n\nget_vivo_value_in_table")
            print(valueName)
            
            if(not self.compound):
                return ""
            
            value = ""
            
            for table in self.tables:

                print(table.caption)

                if(value):
                    break

                titleWordArr = table.caption.split(" ")
                compoundFound = False
                for word in titleWordArr:
                    if(word.strip().lower() == self.compound):
                        compoundFound = True
                        break

                print(f"compoundFound: {compoundFound}")
                
                if(not compoundFound):
                    continue

                valueColNum = -1
                for row in table.grid.header:

                    if(valueColNum != -1):
                        break

                    colNum = 0
                    for cell in row.cells:

                        if(valueName.lower() in cell.lower()):
                            valueColNum = colNum
                            break
                        elif(valueName == "t_half"):
                            if(("t" in cell.lower() and "1/2" in cell.lower())
                            or ("half" in cell.lower() and "life" in cell.lower())):
                                valueColNum = colNum
                                break
                        elif(valueName == "bioavailability"):
                            if("F" in cell and "%" in cell):
                                valueColNum = colNum
                                break

                        colNum += 1

                print(f"valueColNum: {valueColNum}")

                if(valueColNum == -1):
                    continue

                isColumnTable = True
                for row in table.grid.header:
                    if(not isColumnTable):
                        break
                    for cell in row.cells:
                        if(not isColumnTable):
                            break
                        for keyword in self.compoundKeywords:
                            if(keyword in cell.lower()):
                                isColumnTable = False
                                break

                print(f"isColumnTable: {isColumnTable}")

                if(not isColumnTable):
                    continue
                if(len(table.grid.body) == 0):
                    continue
                if(len(table.grid.body[0].cells) == 0):
                    continue

                value = table.grid.body[0].cells[valueColNum]

            return value



        
        def get_single_value_from_body(self):
            # if(not self.ec50):    
            #     self.ec50 = self.find_single_value_in_table("EC50")
            # if(not self.ed50):
            #     self.ed50 = self.find_single_value_in_table("ED50")
            # if(not self.auc):
            #     self.auc = self.find_single_value_in_table("AUC")
            # if(not self.herg):
            #     self.herg = self.find_single_value_in_table("hERG")
            # if(not self.tHalf):
            #     self.tHalf = self.find_single_value_in_table("t_half")
            # if(not self.bioavailability):
            #     self.bioavailability = self.find_single_value_in_table("bioavailability")
            ec50 = self.find_single_value_in_table("EC50")
            if(ec50):
                self.ec50 = ec50
            ed50 = self.find_single_value_in_table("ED50")
            if(ed50):
                self.ed50 = ed50
            auc = self.find_single_value_in_table("AUC")
            if(auc):
                self.auc = auc
            else:
                auc = self.get_vivo_value_in_table("AUC")
                if(auc):
                    self.auc = auc
            herg = self.find_single_value_in_table("hERG")
            if(herg):
                self.herg = herg
            else:
                herg = self.get_vivo_value_in_table("hERG")
                if(herg):
                    self.herg = herg
            tHalf = self.find_single_value_in_table("t_half")
            if(tHalf):
                self.tHalf = tHalf
            else:
                tHalf = self.get_vivo_value_in_table("t_half")
                if(tHalf):
                    self.tHalf = tHalf
            bioavailability = self.find_single_value_in_table("bioavailability")
            if(bioavailability):
                self.bioavailability = bioavailability
            else:
                bioavailability = self.get_vivo_value_in_table("bioavailability")
                if(bioavailability):
                    self.bioavailability = bioavailability





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
    


    def retrieve_article_amount_and_doi(targetFullName):

        AMOUNT1 = 0
        AMOUNT2 = 0
        DOIArr = []
        dateArr = []
        
        global outputArr
        outputArr.append("find keywords: ")

        for condition in ScienceDirect.conditions:

            offset = 0

            url = "https://api.elsevier.com/content/search/sciencedirect"
            header = {"x-els-apikey": "7f59af901d2d86f78a1fd60c1bf9426a", "Accept": "application/json", "Content-Type": "application/json"}
            payload = {
            "qs": f"{condition[0]}",
            "pub": f"\"{condition[1]}\"",
            "display": {
                    "offset": offset,
                    "show": 100
                }   
            }

            response = requests.put(url, headers=header, json=payload)
            result = json.loads(response.text)
            AMOUNT1 += result["resultsFound"]

            while(True):
                if ("results" in result and len(result["results"]) > 0):
                    for article in result["results"]:

                        date = article["publicationDate"][:4]
                        found = False
                        for yearOccur in dateArr:
                            if(yearOccur[0] == date):
                                yearOccur[1] += 1
                                found = True
                                break
                        if(not found):
                            dateArr.append([date, 1])

                        if (article["doi"]):

                            if(not find_index.check_sciencedirect_article(article["doi"], targetFullName)):
                                AMOUNT1 -= 1
                                continue 
                            
                            doc = FullDoc(doi = article["doi"])
                            stringList = ["IC50", "EC50", "ED50", "IC 50", "EC 50", "ED 50"]
                            keywordFound = False
                            if(doc.read(ScienceDirect.client)):

                                if(type(doc.data["originalText"]) != str):
                                    continue
                                if(any(substring in doc.data["originalText"] for substring in stringList)):
                                    keywordFound = True
                                
                                index1 = 0
                                index2 = 0
                                index3 = 0
                                index4 = 0
                                while(not keywordFound and 
                                    (index1 < len(doc.data["originalText"]) or 
                                    index2 < len(doc.data["originalText"]) or
                                    index3 < len(doc.data["originalText"]) or
                                    index4 < len(doc.data["originalText"]))):
                                    
                                    if(not keywordFound):

                                        index1 = doc.data["originalText"].find("Ki", index1)
                                        index2 = doc.data["originalText"].find("Kd", index2)
                                        index3 = doc.data["originalText"].find("K d", index3)
                                        index4 = doc.data["originalText"].find("K d", index4)
                                        if(index1 != -1 and index1 < len(doc.data["originalText"])):
                                            if((index1 + 2) >= len(doc.data["originalText"])):
                                                keywordFound = True
                                            else:
                                                if(not doc.data["originalText"][index1 + 2].isalpha()):
                                                    keywordFound = True
                                        if(not keywordFound and index2 != -1 and index2 < len(doc.data["originalText"])):
                                            if((index2 + 2) >= len(doc.data["originalText"])):
                                                keywordFound = True
                                            else:
                                                if(not doc.data["originalText"][index2 + 2].isalpha()):
                                                    keywordFound = True 
                                        if(not keywordFound and index3 != -1 and index3 < len(doc.data["originalText"])):
                                            if((index3 + 3) >= len(doc.data["originalText"])):
                                                keywordFound = True
                                            else:
                                                if(not doc.data["originalText"][index3 + 3].isalpha()):
                                                    keywordFound = True
                                        if(not keywordFound and index4 != -1 and index4 < len(doc.data["originalText"])):
                                            if((index4 + 3) >= len(doc.data["originalText"])):
                                                keywordFound = True
                                            else:
                                                if(not doc.data["originalText"][index4 + 3].isalpha()):
                                                    keywordFound = True  

                                    
                                    if(not keywordFound):
                                        if(index1 == -1):
                                            index1 = len(doc.data["originalText"])
                                        else:    
                                            index1 = index1 + 2
                                        if(index2 == -1):
                                            index2 = len(doc.data["originalText"])
                                        else:
                                            index2 = index2 + 2
                                        if(index3 == -1):
                                            index3 = len(doc.data["originalText"])
                                        else:
                                            index3 = index3 + 3
                                        if(index4 == -1):
                                            index4 = len(doc.data["originalText"])
                                        else:
                                            index4 = index4 + 3

                                                            
                            if(keywordFound):   
                                AMOUNT2 += 1
                                DOIArr.append(article["doi"])
                                outputArr.append(f"doi: {article['doi']}")

                else:
                    break

                offset += 100
                display = {
                    "offset": offset,
                    "show": 100
                }
                payload = {
                "qs": f"{condition[0]}",
                "pub": f"\"{condition[1]}\"",
                "display": display
                }
                response = requests.put(url, headers=header, json=payload)
                result = json.loads(response.text)


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
                self.boldParagraphFound = False

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

                self.title = ""




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
                    self.abstractBoldText += "<b> "

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
                if(self.newParagraphFound and tag == "ce:bold"):
                    self.boldParagraphFound = True
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
                            newGrid.columnNum = int(attr[1])
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
                    self.titleText += data
                    self.title += data
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
                    boldData = data
                    if(self.boldParagraphFound):
                        boldData = "<b> " + boldData + " </b>"
                    if(len(self.bodyText.sections[-1].paragraphs) == 0):
                        newParagraph = BodyText.Section.Paragraph("")
                        self.bodyText.sections[-1].paragraphs.append(newParagraph)
                    if(len(self.bodyText.sections[-1].paragraphs[-1].contents) == 0):
                        self.bodyText.sections[-1].paragraphs[-1].contents.append(data)
                        self.bodyText.sections[-1].paragraphs[-1].boldContents.append(boldData)
                        return 
                    else:
                        self.bodyText.sections[-1].paragraphs[-1].contents[-1] += (data)
                        self.bodyText.sections[-1].paragraphs[-1].boldContents[-1] += (boldData)

                
                if(self.tableCaptionContent):
                    self.tables[-1].caption += data
                if(self.headerCellFound):
                    self.tables[-1].grid.header[-1].cells[-1] += data.strip()
                if(self.contentCellFound):
                    self.tables[-1].grid.body[-1].cells[-1] += data.strip()



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
                    self.abstractBoldText += " </b>"
                
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
                if(self.boldParagraphFound and tag == "ce:bold"):
                    self.boldParagraphFound = False
                
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
                        index = data.find(self.ref)
                        if((index + len(self.ref)) < len(data)):
                            if(not data[index + len(self.ref)].isdigit()):
                                self.isRequired = True
                            else:
                                self.isRequired = False
                        else:
                            self.isRequired = False
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
            self.valid = True
            self.simles = ""

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

            self.compoundSet = set()
            self.compoundDict = {}

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

            self.compoundNameDrug = ""

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
            self.tHalf = ""
            self.bioavailability = ""

            self.nlpCompound = False

            global TARGETNAME
            self.focusedTarget = TARGETNAME.lower()
            self.ABBREVIATION = TARGETNAME.lower()
            self.FULLNAME = TARGETNAME.lower()
            self.retrieve_values()


        

        def retrieve_values(self):
            
            print("e1")
            if(not self.ABBREVIATION or not self.FULLNAME):
                self.get_FULLNAME_ABBREVIATION()
            print("e2")
            self.retrieve_article_information()
            if(not self.valid):
                return
            print("e3")
            positionResult = self.retrieve_image_text()
            if(not self.valid):
                return
            print("e4")
            self.retrieve_nlp_data()

            print("e5")
            # if(not self.focusedTarget):
            self.retrieve_target()

            print("e6")
            self.retrieve_compound_amount()
            print("e7")
            # if(not self.enzymeIc50 and not self.cellIc50):
            self.get_ic50_from_image(positionResult)
            print("e8")
            # if(not self.compound):
            self.get_compound_from_image(positionResult)
            print("e9")
            self.get_molecule_from_title_abstract()
            print("e10")
            self.get_compound_from_abstract()
            print("e11")
            # if(not self.enzymeIc50 and not self.cellIc50):
            self.get_ic50_from_abstract()
            
            print("e12")
            self.get_multiple_values_from_body()
            print("e13")
            self.get_single_value_from_body()
            print("e14")




        def retrieve_article_information(self):

            global outputArr
            
            QUERY_URL = "https://api.elsevier.com/content/article/doi/"
            header = {"X-ELS-APIKey": ScienceDirect.APIKEY, "Accept": "text/xml"}
            response = requests.get(QUERY_URL + self.articleDOI, headers=header)

            tableParser = ScienceDirect.ScienceDirectArticle.TableParser()
            try:
                tableParser.feed(response.text)
            except AssertionError as ae:
                pass

            imgRef = tableParser.imgRef
            outputArr.append(f"imgRef: {imgRef}")
            if(not imgRef):
                self.valid = False
                return

            imageParser = ScienceDirect.ScienceDirectArticle.ReferenceParser(imgRef)
            try:
                imageParser.feed(response.text)
            except AssertionError as ae:
                pass

            if(not imageParser.eid):
                self.valid = False
                return
            
            IMAGE_QUERY_URL = "https://api.elsevier.com/content/object/eid/"
            self.imgURL = IMAGE_QUERY_URL + imageParser.eid
            self.titleText = tableParser.titleText
            self.abstractText = tableParser.abstractText
            self.bodyText = tableParser.bodyText
            self.tables = tableParser.tables
            self.tableParser = tableParser

            self.authorArr = tableParser.authorArr
            self.year = tableParser.year

            for table in self.tables:
                if(not table.grid.header and len(table.grid.body) >= 2):
                    table.grid.header.append(table.grid.body[0])
                    table.grid.body = table.grid.body[1:]

            if(len(tableParser.institution) == 0):
                self.institution = ""
            else:
                self.institution = tableParser.institution[0]

            self.journal = tableParser.journal

            citedByURL = f"http://api.elsevier.com/content/search/scopus?query=DOI({self.doi})&field=citedby-count"
            header = {"X-ELS-APIKey": ScienceDirect.APIKEY}
            response = requests.get(citedByURL, headers=header)
            responseDict = json.loads(response.text)
            try:
                self.paperCited = int(responseDict["search-results"]["entry"][0]["citedby-count"])
            except:
                self.paperCited = 0



        def retrieve_image_text(self):

            global outputArr

            header = {"X-ELS-APIKey": ScienceDirect.APIKEY}
            image = requests.get(self.imgURL, headers=header).content
            
            fileName = ""
            for c in self.doi.strip():
                if(c.isalpha() or c.isdigit()):
                    fileName += c
                else:
                    fileName += "_"
            
            try:
                with open(f"ScienceDirectImage/{ScienceDirect.TARGET}/abstract_image/{fileName}.jpeg", "wb") as handler:
                    handler.write(image)
            except:
                self.valid = False
                return

            simles = ""
            positionResult = []

            try:
                (simles, positionResult) = molecularSimles(f"ScienceDirectImage/{ScienceDirect.TARGET}/abstract_image/{fileName}.jpeg")
            except:
                # self.valid = False
                pass
            outputArr.append(f"simles: {bool(simles)}")
            # if(not simles):
            #     self.valid = False
            
            # if(not self.valid):
            #     return
            
            self.simles = simles

            if(len(positionResult) == 0):
                reader = easyocr.Reader(["en"], gpu=False)
                positionResult = reader.readtext(f"ScienceDirectImage/{ScienceDirect.TARGET}/abstract_image/{fileName}.jpeg")

            return positionResult




        def get_FULLNAME_ABBREVIATION(self):
            
            # trim the number at the end of TARGET
            i = len(ScienceDirect.TARGET) - 1
            while(i >= 0):
                if(not ScienceDirect.TARGET[i].isalpha()):
                    i -= 1
                else:
                    break
            queryTarget = ScienceDirect.TARGET[:i + 1]

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





        def retrieve_nlp_data(self):

            global outputArr
            
            print("3.1.3.2")
            nlpDict = nlp.get_nlp_results(self.tableParser, **modelDict)
            nlpDict = nlpDict["single_dict"]
            print(nlpDict)
            
            outputArr.append(nlpDict)
            
            print("3.1.3.3")
            if("compound" in nlpDict):
                
                compound = ""
                for token in nlp.def_tokenizer(nlpDict["compound"]):
                    
                    if(token == "<b>"):
                        continue
                    if(token == "</b>"):
                        break
                    compound += token
                
                if(compound and compoundName(compound)):
                    self.compound = compound
                    self.nlpCompound = True
            
            print("3.1.3.4")
            if("compound_drug" in nlpDict):

                compound_drug = ""
                for token in nlp.def_tokenizer(nlpDict["compound"]):

                    if(token == "<b>" or token == "</b>"):
                        continue
                    compound_drug += token
                
                if(compound_drug and self.is_compound_name_drug(compound_drug)):
                    self.compoundNameDrug = compound_drug

            print("3.1.3.5")
            if("target" in nlpDict):

                tokenArr = nlp.def_tokenizer(nlpDict["target"])
                if(len(tokenArr) == 1):
                    
                    target = tokenArr[0].strip()
                    letterFound = False
                    digitFound = False
                    isTargetName = True
                    for c in target:
                        if(not digitFound and c.isalpha()):
                            letterFound = True
                        elif(letterFound and c.isdigit()):
                            digitFound = True
                        else:
                            isTargetName = False
                            break
                    
                    if(not letterFound or not digitFound):
                        isTargetName = False

                    if(isTargetName):
                        self.focusedTarget = target.lower().strip()

            global TARGETNAME
            self.focusedTarget = TARGETNAME.lower()
            self.ABBREVIATION = TARGETNAME.lower()
            self.FULLNAME = TARGETNAME.lower()
            
            nmKeyArr = ["ic50_mc", "ki_mc", "kd_mc", "ic50_ce", "ki_ce", "kd_ce", "ec50_ce"]            
            
            print("3.1.3.6")
            for key in nmKeyArr:
                if(key in nlpDict):

                    value = ""
                    unit = ""
                    valueFound = False
                    for token in nlp.def_tokenizer(nlpDict[key]):

                        if(not value and not valueFound and token.isdigit()):
                            value += token
                            valueFound = True                        
                        elif(valueFound and (token.isdigit() or token == ".")):
                            value += token
                        elif(valueFound and not token.isdigit()):
                            for c in token:
                                if(c.isdigit() or c == "."):
                                    value += c
                                else:
                                    break
                            valueFound = False
                        if("nm" in token.lower() or "μm" in token.lower()):
                            unit = token
                        if(value and unit and not valueFound):
                            break
                    
                    if(value):
                        try:
                            value = float(value)
                        except ValueError:
                            value = -1
                        
                        if(value != -1 and (not unit or (unit and "m" in unit.lower()))):
                            if(unit and unit.lower().strip() == "μm"):
                                value *= 1000

                            if(key == "ic50_mc"):
                                self.enzymeIc50 = value
                            elif(key == "ki_mc"):
                                self.enzymeKi = value
                            elif(key == "kd_mc"):
                                self.enzymeKd = value
                            elif(key == "ic50_ce"):
                                self.cellIc50 = value
                            elif(key == "ki_ce"):
                                self.cellKi = value
                            elif(key == "kd_ce"):
                                self.cellKd = value
                            elif(key == "ec50_ce"):
                                self.ec50 = value
            

            selectivityKeyArr = ["selectivity_mc", "selectivity_ce"]

            print("3.1.3.7")
            for key in selectivityKeyArr:
                if(key in nlpDict):
                    
                    tokenArr = nlp.def_tokenizer(nlpDict[key])

                    digits = ""
                    for token in tokenArr:

                        if(digits):
                            break

                        if("fold" in token):
                            for c in token:
                                if(c.isdigit() or c == "."):
                                    digits += c
                    
                    
                    if(digits):

                        try:
                            digits = int(digits)
                        except ValueError:
                            digits = -1

                        if(digits != -1):
                            if(key == "selectivity_mc"):
                                self.enzymeSelectivity = digits
                            elif(key == "selectivity_ce"):
                                self.cellSelectivity = digits

            
            microUnitArr = ["herg_ce", "solubility_ce", "ed50_an", "solubility_an"]
            
            print("3.1.3.8")
            for key in microUnitArr:
                if(key in nlpDict):

                    value = ""
                    unit = ""
                    valueFound = False
                    tokenArr = nlp.def_tokenizer(nlpDict[key])
                    for token in tokenArr:

                        if(not value and not valueFound and token.isdigit()):
                            value += token
                            valueFound = True
                        elif(valueFound and (token.isdigit() or token == ".")):
                            value += token
                        elif(valueFound and not token.isdigit()):
                            for c in token:
                                if(c.isdigit() or c == "."):
                                    value += c
                                else:
                                    break
                            valueFound = False
                        if("nm" in token.lower() or "μm" in token.lower() or "mm" in token.lower()
                            or "ng" in token.lower() or "μg" in token.lower() or "mg" in token.lower()):
                            unit = token
                        if(value and unit and not valueFound):
                            break

                    
                    if(value):
                        try:
                            value = float(value)
                        except ValueError:
                            value = -1
                        
                        if(value != -1):
                            if(unit and ("nm" in unit.lower() or "ng" in unit.lower())):
                                value /= 1000
                            if(unit and ("mm" in unit.lower() or "mg" in unit.lower())):
                                value *= 1000
                            
                            if(key == "herg_ce"):
                                self.herg = value
                            elif(key == "solubility_ce"):
                                self.cellSolubility = value
                            elif(key == "ed50_an"):
                                self.ed50 = value
                            elif(key == "solubility_an"):
                                self.vivoSolubility = value
            
            print("3.1.3.9")
            if("t_half_an" in nlpDict):

                tokenArr = nlp.def_tokenizer(nlpDict["t_half_an"])
                value = ""
                unit = ""
                valueFound = False
                for token in tokenArr:
                        if(not value and not valueFound and token.isdigit()):
                            value += token
                            valueFound = True
                        elif(valueFound and (token.isdigit() or token == ".")):
                            value += token
                        elif(valueFound and not token.isdigit()):
                            for c in token:
                                if(c.isdigit() or c == "."):
                                    value += c
                                else:
                                    break
                            valueFound = False
                        if("min" in token.lower() or "h" in token.lower()):
                            unit = token
                        if(value and unit and not valueFound):
                            break
                        
                if(value):
                    try:
                        value = float(value)
                    except ValueError:
                        value = -1
                    
                    if(value != -1):
                        if(unit and unit.lower() == "min"):
                            value /= 60
                        
                        self.tHalf = value
            
            print("3.1.3.10")
            if("auc_an" in nlpDict):

                tokenArr = nlp.def_tokenizer(nlpDict["auc_an"])
                value = ""
                unit = ""
                valueFound = False
                for token in tokenArr:
                    if(not value and not valueFound and token.isdigit()):
                        value += token
                        valueFound = True
                    elif(valueFound and (token.isdigit() or token == ".")):
                        value += token
                    elif(valueFound and not token.isdigit()):
                        for c in token:
                            if(c.isdigit() or c == "."):
                                value += c
                            else:
                                break
                        valueFound = False
                    if("g" in token.lower() and "l" in token.lower() and "/" in token.lower()):
                        unit = token
                    if(value and unit and not valueFound):
                        break

                if(value):
                    try:
                        value = float(value)
                    except ValueError:
                        value = -1

                    if(value != -1):
                        if(unit):
                            if("μg" in unit.lower()):
                                value *= 1000
                            if("ml" not in unit.lower() and "l" in unit.lower()):
                                value /= 1000
                        
                        self.auc = value

            print("3.1.3.11")
            if("bioavailability_an" in nlpDict):

                tokenArr = nlp.def_tokenizer(nlpDict["bioavailability_an"])

                value = ""
                valueFound = False
                for token in tokenArr:
                    if(not value and not valueFound and token.isdigit()):
                        value += token
                        valueFound = True
                    elif(valueFound and (token.isdigit() or token == ".")):
                        value += token
                    elif(valueFound and not token.isdigit()):
                        for c in token:
                            if(c.isdigit() or c == "."):
                                value += c
                            else:
                                break
                        valueFound = False
                        break
 
                
                if(value):
                    try:
                        value = float(value)
                    except ValueError:
                        value = -1
                    
                    if(value != -1):
                        self.bioavailability = value            
 







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




        def retrieve_compound_amount(self):

            boldContentSet = set()

            abstractBoldArr = re.findall("<b>.*?</b>", self.tableParser.abstractBoldText)
            for token in abstractBoldArr:
                token = token.replace("(", " ")
                token = token.replace(")", " ")
                index = token.find("</b>")
                name = token[3:index].strip()
                boldContentSet.add(name)
                if(name in self.compoundDict):
                    self.compoundDict[name] += 1
                else:
                    self.compoundDict[name] = 1
            
            for section in self.bodyText.sections:
                for paragraph in section.paragraphs:
                    for token in paragraph.boldContents:
                        abstractBoldArr = re.findall("<b>.*?</b>", token)
                        for item in abstractBoldArr:
                            item = item.replace("(", " ")
                            item = item.replace(")", " ")
                            index = item.find("</b>")
                            name = item[3:index].strip()
                            boldContentSet.add(name)
                            if(name in self.compoundDict):
                                self.compoundDict[name] += 1
                            else:
                                self.compoundDict[name] = 1

            self.compoundSet = boldContentSet

            # for table in self.tables:
                
            #     compoundColNum = -1
            #     for row in table.grid.header:

            #         if(compoundColNum != -1):
            #             break

            #         colNum = 0
            #         for cell in row.cells:

            #             if(compoundColNum != -1):
            #                 break

            #             for keyword in self.compoundKeywords:
            #                 if(keyword in cell.lower()):
            #                     compoundColNum = colNum
            #                     break
                        
            #             colNum += 1
                    
            #     if(compoundColNum == -1):
            #         continue
                
            #     for row in table.grid.body:
            #         if(compoundColNum >= len(row.cells)):
            #             continue
            #         if(compoundName(row.cells[compoundColNum])):
            #             self.compoundSet.add(row.cells[compoundColNum])



        

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
      

        def is_compound_name_drug(self, name):

            if(not name):
                return False
            
            name = name.strip()
            letterFound = False
            digitFound = False
            for c in name:
                if(not digitFound and c.isalpha()):
                    letterFound = True
                elif(c.isdigit()):
                    digitFound = True
                if(digitFound and c.isalpha()):
                    return False
            
            if(letterFound and digitFound):
                return True
            else:
                return False



        def get_molecule_from_title_abstract(self):
            # find all identified molecule names inside of title
            doc = Document(self.titleText)
            for NR in doc.cems:
                self.moleculeArr.append(NR.text)
                if(not self.compoundNameDrug and self.is_compound_name_drug(NR.text)):
                    self.compoundNameDrug = NR.text.strip()
 
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
            
            if(self.nlpCompound):
                return

            # identify compound name from abstract text, compound names are always in bold ( <b>keyword</b> )
            self.compoundArr = self.tableParser.boldAbstractTextArr.copy()
            # find all keywords in the form of compound name
            tempArr = []
            for name in self.compoundArr:
                if(compoundName(name)):
                    tempArr.append(name)

            if(len(tempArr) == 0):
                if(len(self.compoundDict) == 0 or self.compound in self.compoundDict):
                    return
                else:
                    name = ""
                    maxFreq = -1
                    for key in self.compoundDict.keys():
                        if(self.compoundDict[key] > maxFreq):
                            maxFreq = self.compoundDict[key]
                            name = key
                    self.compound = name.strip()
                    return

            compoundFound = False
            if(self.compound):
                for name in tempArr:
                    if(self.compound in name):
                        compoundFound = True
                        break
            
            if(not compoundFound):
                self.compound = "" 

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
        
        


        def find_values_in_table(self, valueName):

            if(not self.compound):
                return ["", "", ""]
            
            mediValue = ""
            vitroValue = ""
            vivoValue = ""

            print(f"\n\nvalueName: {valueName}")
            for table in self.tables:
  
                print(f"\n\ntitle: {table.caption}")
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
                print(f"titleFound: {titleFound}")

                valueColNum = -1
                valueUnit = ""
                for row in table.grid.header:
                    
                    if(valueColNum != -1):
                        break
                    
                    colNum = 0
                    for cell in row.cells:
                        
                        index = cell.find(valueName)
                        if(index != -1):

                            if(valueName[-1].isdigit() or (index + len(valueName)) >= len(cell)):
                                valueColNum = colNum

                                if("nm" in cell.lower()):
                                    valueUnit = "nano"
                                elif("μm" in cell.lower()):
                                    valueUnit = "micro"

                                break

                            else:
                                if(cell[index + len(valueName)].isspace()):
                                    valueColNum = colNum

                                    if("nm" in cell.lower()):
                                        valueUnit = "nano"
                                    elif("μm" in cell.lower()):
                                        valueUnit = "micro"

                                    break


                        colNum += 1
                
                print(f"valueColNum: {valueColNum}")


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
                
                print(f"1: compoundColNum: {compoundColNum}")
                

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
                            colNum += 1
                            continue
                        
                        if(cell.lower().strip() == self.compound):
                            compoundRowNum = rowNum
                            break

                        colNum += 1
                    rowNum += 1

                
                print(f"compounRowNum: {compoundRowNum}")
                

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
                or "vivo" in table.caption.lower() or "preclinical" in table.caption.lower()
                or "pk" in table.caption.lower()):
                    vivoFound = True

                print(f"1: medifound: {mediFound}, vitroFound: {vitroFound}, vivoFound: {vivoFound}")


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

                
                print(f"targetColNum: {targetColNum}")


                if(valueColNum == -1 and targetColNum == -1):
                    if(not vitroFound):
                        continue
                    else:
                        if(not titleFound):
                            continue


                value = ""
                extractColNum = -1
                if(titleFound):
                    if(targetColNum != -1):
                        value = table.grid.body[compoundRowNum].cells[targetColNum]
                        extractColNum = targetColNum

                    else:
                        if(valueColNum != -1):
                            value = table.grid.body[compoundRowNum].cells[valueColNum]
                            extractColNum = valueColNum
                else:
                    if(valueColNum != -1):
                        value = table.grid.body[compoundRowNum].cells[valueColNum]
                        extractColNum = valueColNum
                
                if(valueColNum == -1 and targetColNum == -1 and vitroFound 
                and table.grid.columnNum > 1):
                    
                    for colNum in range(0, table.grid.columnNum):
                        
                        if(colNum == compoundColNum):
                            continue
                        value = table.grid.body[compoundRowNum].cells[colNum]
                        extractColNum = colNum
                        break

                
                
                if(value and not valueUnit):
                    microFound = False
                    for row in table.grid.header:

                        if(microFound):
                            break
                        
                        colNum = 0
                        for cell in row.cells:
                            if(colNum != extractColNum):
                                colNum += 1
                                continue
                            if("μm" in cell.lower()):
                                microFound = True
                                break
                            colNum += 1
                    
                    if(microFound):
                        value = "μm" + value

                
                if(valueUnit):
                    if(valueUnit == "micro"):
                        value = "μm" + value
                
                
                if(not mediFound and not vitroFound and not vivoFound):
                    for row in table.grid.header:
                        cell = ""
                        if(extractColNum >= len(row.cells)):
                            cell = row.cells[-1]
                        else:
                            cell = row.cells[extractColNum]
                        
                        if("enzyme" in cell.lower() or "enzymatic" in cell.lower()):
                            mediFound = True
                            break
                        elif("cell" in cell.lower() or "cellular" in cell.lower() 
                        or "vitro" in cell.lower()):
                            vitroFound = True
                            break
                        elif("pharmacokinetic" in cell.lower() or "preliminary" in cell.lower()
                        or "vivo" in cell.lower() or "preclinical" in cell.lower()
                        or "pk" in cell.lower()):
                            vivoFound = True
                            break
                        
                print(f"2: medifound: {mediFound}, vitroFound: {vitroFound}, vivoFound: {vivoFound}")

                if(not mediFound and not vitroFound and not vivoFound):
                    mediFound = True
                
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

            value = ""

            for table in self.tables:
                
                valueNameFound = False
                index = 0
                while(index >= 0 and index < len(table.caption)):
                    index = table.caption.find(valueName, index)
                    if(index != -1):
                        if((index + len(valueName)) < len(table.caption)):
                            if(table.caption[index + len(valueName)].isspace()):
                                valueNameFound = True
                                break
                        else:
                            valueNameFound = True
                            break
                        index += 1
                
                valueUnit = ""
                valueColNum = -1
                for row in table.grid.header:

                    if(valueColNum != -1):
                        break

                    colNum = 0
                    for cell in row.cells:
                        index = cell.find(valueName)
                        if(index != -1):
                            if((index + len(valueName)) < len(cell)):
                                if(cell[index + len(valueName)].isspace()):
                                    valueColNum = colNum

                                    if("nm" in cell.lower()):
                                        valueUnit = "nano"
                                    elif("μm" in cell.lower()):
                                        valueUnit = "micro"

                                    break
                                elif(valueName == "AUC"):
                                    valueColNum = colNum
                                    break
                            else:
                                valueColNum = colNum

                                if("nm" in cell.lower()):
                                    valueUnit = "nano"
                                elif("μm" in cell.lower()):
                                    valueUnit = "micro"

                                break

                        if(index == -1 and valueName == "bioavailability"):
                            if("F" in cell and "%" in cell):
                                valueColNum = colNum
                                break
                        elif(index == -1 and valueName == "t_half"):
                            if(("half" in cell.lower() and "life" in cell.lower()) 
                                or ("t" in cell.lower() and "1/2" in cell.lower())):
                                valueColNum = colNum
                                break
                        
                        colNum += 1
                
                targetColNum = -1
                if(self.focusedTarget):
                    for row in table.grid.header:
                        colNum = 0
                        for cell in row.cells:
                            if(self.focusedTarget in cell):
                                targetColNum = colNum
                        colNum += 1
                

                if((valueColNum == -1 and not valueNameFound) or (valueNameFound and targetColNum == -1)):
                    continue

                
                compoundColNum = -1
                for row in table.grid.header:
                    colNum = 0
                    for cell in row.cells:
                        for compoundName in self.compoundKeywords:
                            if(compoundName in cell):
                                compoundColNum = colNum
                                break
                        colNum += 1
                
                if(compoundColNum == -1):
                    compoundColNum = 0
                
                compoundRowNum = -1
                rowNum = 0
                for row in table.grid.body:
                    if(compoundRowNum != -1):
                        break

                    colNum = 0
                    for cell in row.cells:
                        if(colNum != compoundColNum):
                            colNum += 1
                            continue
                        if(cell.strip() == self.compound):
                            compoundRowNum = rowNum
                            break
                        colNum += 1
                    rowNum += 1

                if(compoundRowNum == -1):
                    continue
                
                
                value = ""
                if(valueColNum != -1):
                    value = table.grid.body[compoundRowNum].cells[valueColNum]
                elif(valueNameFound and targetColNum != -1):
                    value = table.grid.body[compoundRowNum].cells[targetColNum]


                if(value and not valueUnit):
                    microFound = False
                    for row in table.grid.header:

                        if(microFound):
                            break

                        for cell in row.cells:
                            if("μm" in cell.lower()):
                                microFound = True
                                break
                    
                    if(microFound):
                        value = "μm" + value

                    return value

                
                if(valueUnit):
                    if(valueUnit == "micro"):
                        value = "μm" + value
                    
                    return value

            
            return value





        def get_multiple_values_from_body(self):
            
            print("e12.1")
            [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("IC50")
            # if(not self.enzymeIc50):
            #     if(not self.ic50Value):
            #         self.enzymeIc50 = enzymeValue
            #     else:
            #         self.enzymeIc50 = self.ic50Value
            # if(not self.cellIc50):
            #     self.cellIc50 = cellValue
            if(enzymeValue):
                self.enzymeIc50 = enzymeValue
            if(cellValue):
                self.cellIc50 = cellValue
            
            print("e12.2")
            [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("Ki")
            # if(not self.enzymeKi):    
            #     self.enzymeKi = enzymeValue
            # if(not self.cellKi):
            #     self.cellKi = cellValue
            if(enzymeValue):
                self.enzymeKi = enzymeValue
            if(cellValue):
                self.cellKi = cellValue
            
            print("e12.3")
            [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("Kd")
            # if(not self.enzymeKd):
            #     self.enzymeKd = enzymeValue
            # if(not self.cellKd):
            #     self.cellKd = cellValue
            if(enzymeValue):
                self.enzymeKd = enzymeValue
            if(cellValue):
                self.cellKd = cellValue

            # if(not self.enzymeKd or not self.cellKd):
            #     [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("KD")
            #     if(not self.enzymeKd):
            #         self.enzymeKd = enzymeValue
            #     if(not self.cellKd):
            #         self.cellKd = cellValue
            if(not self.enzymeKd or not self.cellKd):
                [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("KD")
                if(enzymeValue):
                    self.enzymeKd = enzymeValue
                if(not self.cellKd):
                    self.cellKd = cellValue

            
            print("e12.4")
            [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("selectivity")
            # if(not self.enzymeSelectivity):
            #     self.enzymeSelectivity = enzymeValue
            # if(not self.cellSelectivity):
            #     self.cellSelectivity = cellValue
            if(enzymeValue):
                self.enzymeSelectivity = enzymeValue
            if(cellValue):
                self.cellSelectivity = cellValue
            
            print("e12.5")
            [enzymeValue, cellValue, vivoValue] = self.find_values_in_table("solubility")
            # if(not self.cellSolubility):
            #     self.cellSolubility = cellValue
            # if(not self.vivoSolubility):
            #     self.vivoSolubility = vivoValue
            if(cellValue):
                self.cellSolubility = cellValue
            if(vivoValue):
                self.vivoSolubility = vivoValue


        def get_vivo_value_in_table(self, valueName):

            print("\n\nget_vivo_value_in_table")
            print(valueName)
            
            if(not self.compound):
                return ""
            
            value = ""
            
            for table in self.tables:

                print(table.caption)

                if(value):
                    break

                titleWordArr = table.caption.split(" ")
                compoundFound = False
                for word in titleWordArr:
                    if(word.strip().lower() == self.compound):
                        compoundFound = True
                        break

                print(f"compoundFound: {compoundFound}")
                
                if(not compoundFound):
                    continue

                valueColNum = -1
                for row in table.grid.header:

                    if(valueColNum != -1):
                        break

                    colNum = 0
                    for cell in row.cells:

                        if(valueName.lower() in cell.lower()):
                            valueColNum = colNum
                            break
                        elif(valueName == "t_half"):
                            if(("t" in cell.lower() and "1/2" in cell.lower())
                            or ("half" in cell.lower() and "life" in cell.lower())):
                                valueColNum = colNum
                                break
                        elif(valueName == "bioavailability"):
                            if("F" in cell and "%" in cell):
                                valueColNum = colNum
                                break

                        colNum += 1

                print(f"valueColNum: {valueColNum}")

                if(valueColNum == -1):
                    continue

                isColumnTable = True
                for row in table.grid.header:
                    if(not isColumnTable):
                        break
                    for cell in row.cells:
                        if(not isColumnTable):
                            break
                        for keyword in self.compoundKeywords:
                            if(keyword in cell.lower()):
                                isColumnTable = False
                                break

                print(f"isColumnTable: {isColumnTable}")

                if(not isColumnTable):
                    continue
                if(len(table.grid.body) == 0):
                    continue
                if(len(table.grid.body[0].cells) == 0):
                    continue

                value = table.grid.body[0].cells[valueColNum]

            return value




        
        def get_single_value_from_body(self):
            
            # print("e13.1")
            # if(not self.ec50):
            #     self.ec50 = self.find_single_value_in_table("EC50")
            # print("e13.2")
            # if(not self.ed50):
            #     self.ed50 = self.find_single_value_in_table("ED50")
            # print("e13.3")
            # if(not self.auc):
            #     self.auc = self.find_single_value_in_table("AUC")
            # print("e13.4")
            # if(not self.herg):
            #     self.herg = self.find_single_value_in_table("hERG")
            # print("e13.5")
            # if(not self.tHalf):
            #     self.tHalf = self.find_single_value_in_table("t_half")
            # print("e13.6")
            # if(not self.bioavailability):
            #     self.bioavailability = self.find_single_value_in_table("bioavailability")
            ec50 = self.find_single_value_in_table("EC50")
            if(ec50):
                self.ec50 = ec50
            ed50 = self.find_single_value_in_table("ED50")
            if(ed50):
                self.ed50 = ed50
            auc = self.find_single_value_in_table("AUC")
            if(auc):
                self.auc = auc
            else:
                auc = self.get_vivo_value_in_table("AUC")
                if(auc):
                    self.auc = auc
            herg = self.find_single_value_in_table("hERG")
            if(herg):
                self.herg = herg
            else:
                herg = self.get_vivo_value_in_table("hERG")
                if(herg):
                    self.herg = herg
            tHalf = self.find_single_value_in_table("t_half")
            if(tHalf):
                self.tHalf = tHalf
            else:
                tHalf = self.get_vivo_value_in_table("t_half")
                if(tHalf):
                    self.tHalf = tHalf
            bioavailability = self.find_single_value_in_table("bioavailability")
            if(bioavailability):
                self.bioavailability = bioavailability
            else:
                bioavailability = self.get_vivo_value_in_table("bioavailability")
                if(bioavailability):
                    self.bioavailability = bioavailability
            





def convertToInt(num):

    if(not num):
        return 0
    if(type(num) is int):
        return num

    if(num.strip().isdigit()):
        return int(num.strip())
    
    digitStr = ""
    digitFound = False
    for c in num.strip():
        if(not digitFound and c.isdigit()):
            digitFound = True
        if(digitFound and not c.isdigit()):
            break
        if(digitFound and c.isdigit()):
            digitStr += c
    
    if(digitStr):
        try:
            return int(digitStr)
        except ValueError:
            print(f"conversion error: {num}")
            return 0
    else:
        return 0


def convertToFloat(num):

    num = num.strip()

    if(not num):
        return 0.0
    if(type(num) is float):
        return num

    try:
        return float(num)
    except ValueError:
        pass

    num = num.strip()
    if(num and not num[0].isdigit()):
        index = num.find(":")
        if(index != -1):
            num = num[index + 1:].strip()
        index = num.find("=")
        if(index != -1):
            num = num[index + 1:].strip()

    numStr = ""
    for c in num.strip():
        if(c.isdigit() or c == "."):
            numStr += c
        else:
            break
    
    if(numStr):
        try:
            return float(numStr)
        except ValueError:
            print(f"conversion error: {numStr}")
            return 0.0
    else:
        return 0.0


def convert_value(valueDict, key, convertFunc, checkMicro):

    if(type(valueDict[key]) != str):
        return

    if(not checkMicro):
        if(len(valueDict[key]) >= 2 and valueDict[key][:2] == "μm"):
            valueDict[key] = valueDict[key][2:]
        valueDict[key] = convertFunc(valueDict[key])
    else:
        isMicro = False
        if(len(valueDict[key]) >= 2 and valueDict[key][:2] == "μm"):
            isMicro = True
            valueDict[key] = valueDict[key][2:]
        value = convertFunc(valueDict[key])
        
        if(isMicro and value):
            value *= 1000
        
        valueDict[key] = value


def check_json_value_format(articleDict):

    mediDict = articleDict["medicinal_chemistry_metrics"]
    convert_value(mediDict, "IC50", convertToFloat, True)
    convert_value(mediDict, "Ki", convertToFloat, True)
    convert_value(mediDict, "Kd", convertToFloat, True)
    convert_value(mediDict, "selectivity", convertToInt, False)

    vitroDict = articleDict["pharm_metrics_vitro"]
    convert_value(vitroDict, "IC50", convertToFloat, True)
    convert_value(vitroDict, "Ki", convertToFloat, True)
    convert_value(vitroDict, "Kd", convertToFloat, True)
    convert_value(vitroDict, "EC50", convertToFloat, True)
    convert_value(vitroDict, "selectivity", convertToInt, False)
    convert_value(vitroDict, "hERG", convertToFloat, False)
    convert_value(vitroDict, "solubility", convertToFloat, False)

    vivoDict = articleDict["pharm_metrics_vivo"]
    convert_value(vivoDict, "ED50", convertToFloat, False)
    convert_value(vivoDict, "t_half", convertToFloat, False)
    convert_value(vivoDict, "AUC", convertToFloat, False)
    convert_value(vivoDict, "bioavailability", convertToFloat, False)
    convert_value(vivoDict, "solubility", convertToFloat, False)

    # checkUnitkeyArr = ["IC50", "Ki", "Kd", "EC50"]
    # dictArr = [mediDict, vitroDict]
    # for valueDict in dictArr:
    #     for key in checkUnitkeyArr:
            
    #         if(key in valueDict):
                
    #             value = valueDict[key]
    #             if(value > 0 and value < 1):
    #                 value *= 1000
    #                 valueDict[key] = value

runACS = True
runSD = False
fileId = 653
doi = "10.1016/j.ejmech.2017.06.016"

if(runACS):
    ACS.TARGET = TARGETNAME

    articleURL = fileId

    reader = easyocr.Reader(["en"], gpu=False)
    positionResult = reader.readtext(f"images/{ACS.TARGET}/image{articleURL}.jpeg")

    article = ACS.ACSArticle(articleURL, positionResult)
    articleDict = {}
    articleDict["paper_title"] = article.titleText
    articleDict["paper_author"] = article.authorArr
    articleDict["paper_year"] = article.year
    articleDict["paper_institution"] = article.institution
    articleDict["paper_cited"] = article.paperCited
    articleDict["doi"] = article.doi
    articleDict["paper_journal"] = article.journal
    articleDict["paper_abstract_image"] = article.imgArr[0]
    articleDict["compound_count"] = len(article.compoundSet)
    articleDict["compound_name"] = article.compound
    articleDict["compound_name_drug"] = article.compoundNameDrug

    medicinalDict = {}
    medicinalDict["Ki"] = article.enzymeKi
    medicinalDict["Kd"] = article.enzymeKd
    medicinalDict["IC50"] = article.enzymeIc50
    medicinalDict["selectivity"] = article.enzymeSelectivity
    vitroDict = {}
    vitroDict["Ki"] = article.cellKi
    vitroDict["Kd"] = article.cellKd
    vitroDict["IC50"] = article.cellIc50
    vitroDict["EC50"] = article.ec50
    vitroDict["selectivity"] = article.cellSelectivity
    vitroDict["hERG"] = article.herg
    vitroDict["solubility"] = article.cellSolubility
    vivoDict = {}
    vivoDict["ED50"] = article.ed50
    vivoDict["AUC"] = article.auc
    vivoDict["solubility"] = article.vivoSolubility
    vivoDict["t_half"] = article.tHalf
    vivoDict["bioavailability"] = article.bioavailability

    articleDict["medicinal_chemistry_metrics"] = medicinalDict
    articleDict["pharm_metrics_vitro"] = vitroDict
    articleDict["pharm_metrics_vivo"] = vivoDict

    print(articleDict)
    check_json_value_format(articleDict)
    print(articleDict)
    print("end")



if(runSD):
    ScienceDirect.TARGET = TARGETNAME

    # doi = "10.1016/j.ejmech.2021.113711"
    try:
        article = ScienceDirect.ScienceDirectArticle(doi)
    except Exception as e:
        print(e)

    articleDict = {}
    articleDict["paper_title"] = article.titleText
    articleDict["paper_author"] = article.authorArr
    articleDict["paper_year"] = article.year
    articleDict["paper_institution"] = article.institution
    articleDict["paper_cited"] = article.paperCited
    articleDict["doi"] = article.doi
    articleDict["paper_journal"] = article.journal
    articleDict["paper_abstract_image"] = article.imgURL
    articleDict["compound_count"] = len(article.compoundSet)
    articleDict["compound_name"] = article.compound
    articleDict["compound_name_drug"] = article.compoundNameDrug

    medicinalDict = {}
    medicinalDict["Ki"] = article.enzymeKi
    medicinalDict["Kd"] = article.enzymeKd
    medicinalDict["IC50"] = article.enzymeIc50
    medicinalDict["selectivity"] = article.enzymeSelectivity
    vitroDict = {}
    vitroDict["Ki"] = article.cellKi
    vitroDict["Kd"] = article.cellKd
    vitroDict["IC50"] = article.cellIc50
    vitroDict["EC50"] = article.ec50
    vitroDict["selectivity"] = article.cellSelectivity
    vitroDict["hERG"] = article.herg
    vitroDict["solubility"] = article.cellSolubility
    vivoDict = {}
    vivoDict["ED50"] = article.ed50
    vivoDict["AUC"] = article.auc
    vivoDict["solubility"] = article.vivoSolubility
    vivoDict["t_half"] = article.tHalf
    vivoDict["bioavailability"] = article.bioavailability

    articleDict["medicinal_chemistry_metrics"] = medicinalDict
    articleDict["pharm_metrics_vitro"] = vitroDict
    articleDict["pharm_metrics_vivo"] = vivoDict

    print(articleDict)
    check_json_value_format(articleDict)
    print(articleDict)
    print("end")



 
