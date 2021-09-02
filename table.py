from html.parser import HTMLParser


# Parsers cannot exit from inside, the reset() method needs to be called from outside
def exitParser(parser):
    parser.reset()

ACSDOMAIN = "https://pubs.acs.org"

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




class ACSTableParser(HTMLParser):
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
                    link = ACSDOMAIN + attr[1]
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







# parse a ScienceDirect xml file
class ScienceDirectTableParser(HTMLParser):

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