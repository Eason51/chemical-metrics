from html.parser import HTMLParser


TARGET = "janus kinase"
fileId = 0
DOMAIN = "https://pubs.acs.org"

titleText = ""


def exitParser(parser):
    parser.reset()


class BodyText:
    
    class Section:
        
        class Paragraph:
            def __init__(self, header = ""):
                self.header = header
                self.contents = [] # list[str]
        
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



class TableParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)

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
                    link = DOMAIN + attr[1]
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
            global titleText
            titleText += data
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
        
    

tableParser = TableParser()
# open a file locally, should be retrieved through http request in real programs
with open(f"files/{TARGET}/file{fileId}.html", encoding="utf-8") as inputFile:

    try: 
        tableParser.feed(inputFile.read())
    except AssertionError as ae:
        pass
    imgArr = tableParser.imgArr
    abstractText = tableParser.abstractText
    
    bodyText = tableParser.bodyText
    for section in bodyText.sections:
        print("\n\n\n")
        print(f"section header: {section.title}")
        for paragraph in section.paragraphs:
            print(f"sub header: {paragraph.header}")
            print()
            for content in paragraph.contents:
                print(content)
                print()

    tables = tableParser.tables
    for table in tables:
        print("\n\n\n")
        print(f"table caption: {table.caption}")
        
        print()
        print("table descriptions: ")
        for description in table.descriptions:
            print(description)
            print()
        
        print()
        print("table grid: ")
        print(f"column number: {table.grid.columnNum}")
        
        print()
        print("grid header: ")
        for row in table.grid.header:
            print("row: ", end="   ")
            for cell in row.cells:
                print(cell, end="   ")
            print()
        
        print()
        print("grid body: ")
        for row in table.grid.body:
            print("row: ", end="   ")
            for cell in row.cells:
                print(cell, end="   ")
            print()

