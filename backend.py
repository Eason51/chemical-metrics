from re import L
import requests
from html.parser import HTMLParser
from chemdataextractor import Document
import easyocr



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
                stringList = ["ic50", "ec50", "ki", "kd", "ed50"]            
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
                elif(len(data) >= 2 and (data.lower()[-2:] in ["ic", "ec", "ed"])):
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
        
        return (ACS.ContentParser.dateArr, ACS.ContentParser.tableAddressArr, ACS.ContentParser.drugPaperCount)



# --------------------------------------------------------------------------------------------------------------


    
    class ACSArticle:        
        

        # Parse the reponse from online enquiry and store useful information
        class TargetParser(HTMLParser):
            def __init__(self, outer):
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
            def __init__(self, outer):
                HTMLParser.__init__(self)
                
                self.outer = outer

                # enable this flag to skip handle_data for the next element
                self.disableRead = False

                # the link(s) to access abstract image
                self.imgArr = []
                # complete abstract text content
                self.abstractText = ""
                # all elements in abstract text in bold (<b></b>)
                self.boldAbstractTextArr = []

                self.abstractFound = False
                self.figureFound = False
                self.imgLinkFound = False
                self.textFound = False
                self.boldTextFound = False

                self.titleFound = False
                self.titleText = False

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
                
                # handle title, abstract image and abstract text

                if(tag == "div" and len(attrs) >= 1):
                    for attr in attrs:
                        if (attr[0] == "class" and attr[1] == "article_abstract-content hlFld-Abstract"):
                            self.abstractFound = True
                            break
                if(tag == "div" and len(attrs) == 1 and attrs[0][1] == "article_content"):
                    self.abstractText += " . "
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

                # handle title and abstract

                if(self.textFound):
                    self.abstractText += data
                if(self.titleText):
                    self.outer.titleText += data
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

            self.enzymeKi = ""
            self.cellKi = ""
            self.enzymeKd = ""
            self.cellKd = ""


            self.retrieve_values()




        def retrieve_values(self):

            print("get_FULLNAME_ABBREVIATION")
            self.get_FULLNAME_ABBREVIATION()
            print("retrieve_article_information")
            self.retrieve_article_information()
            print("retrieve_target")
            self.retrieve_target()

            print("retrieve_image_text")
            positionResult = self.retrieve_image_text()
            print("get_ic50_from_image")
            self.get_ic50_from_image(positionResult)
            print("get_compound_from_image")
            self.get_compound_from_image(positionResult)
            print("get_molecule_from_title_abstract")
            self.get_molecule_from_title_abstract()
            print("get_compound_from_abstract")
            self.get_compound_from_abstract()
            print("get_ic50_from_abstract")
            self.get_ic50_from_abstract()
            print("get_kikd_from_body")
            self.get_kikd_from_body()
        


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

            longParser = ACS.ACSArticle.TargetParser(self)
            shortParser = ACS.ACSArticle.TargetParser(self)
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
            self.tableParser = ACS.ACSArticle.TableParser(self)
            # open a file locally, should be retrieved through http request in real programs
            response = requests.get(self.articleURL)

            # parse the given html file with TableParser()
            try:
                self.tableParser.feed(response.text)
            except AssertionError as ae:
                pass

            self.imgArr = self.tableParser.imgArr
            self.abstractText = self.tableParser.abstractText
            self.bodyText = self.tableParser.bodyText
            self.tables = self.tableParser.tables


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
            # TODO: 
            # 

            return []
        

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
        def kikd(self, valueName): 
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
                            if("ki " in cell.lower() and "kinact" not in cell.lower()):
                                valueColNum = colNum
                        elif(valueName == "kd"):
                            if("kd " in cell.lower()):
                                valueColNum = colNum
                        for compoundName in self.compoundKeywords:
                            if(compoundName in cell.lower()):
                                compoundColNum = colNum

                        colNum += 1
                
                # if valueName is not found in the title and not in the header, skip the current table
                if(valueColNum == -1 and not valueNameFound):
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
                        if(cell.lower() == self.compound):
                            compoundRowNum = rowNum
                            break
                    rowNum += 1
            

                if(not enzymeFound):        
                    if(compoundRowNum != -1):
                        cellValue.append(grid.body[compoundRowNum].cells[valueColNum])
                
                elif(enzymeFound and targetColNum != -1):
                    if(compoundRowNum != -1):
                        enzymeValue.append(grid.body[compoundRowNum].cells[targetColNum])
                
                elif(enzymeFound and targetColNum == -1 and valueColNum != -1):
                    if(compoundRowNum != -1):
                        enzymeValue.append(grid.body[compoundRowNum].cells[valueColNum])
                
                # if neither enzyme keyword nor target name is found, only the title contains the valueName,
                # select one value from the compound row as its value
                elif(valueNameFound):
                    if(compoundRowNum != -1):
                        colNum = 0
                        for cell in grid.body[compoundRowNum].cells:
                            if(colNum != compoundColNum):
                                if(enzymeFound):
                                    enzymeValue.append(cell)
                                else:
                                    cellValue.append(cell)
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



        def get_kikd_from_body(self):
            [enzymeValue, cellValue] = self.kikd("ki")
            self.enzymeKi = enzymeValue
            self.cellKi = cellValue
            [enzymeValue, cellValue] = self.kikd("kd")
            self.enzymeKd = enzymeValue
            self.cellkd = cellValue












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
        if(len(article.imgArr) == 0):
            continue
        
        articleDict = {}
        articleDict["paper_id"] = i
        articleDict["paper_title"] = article.titleText
        articleDict["paper_abstract_image"] = article.imgArr[0]
        articleDict["compound_name"] = article.compound

        medicinalDict = {}
        medicinalDict["ki"] = article.enzymeKi
        medicinalDict["kd"] = article.enzymeKd
        pharmDict = {}
        pharmDict["ki"] = article.cellKi
        pharmDict["kd"] = article.cellkd

        articleDict["medicinal_chemistry_metrics"] = medicinalDict
        articleDict["pharm_metrics_vitro"] = pharmDict

        result["drug_molecule_paper"].append(articleDict)

        i += 1
    
    return result


all_to_json("janus kinase")
