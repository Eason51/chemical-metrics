import requests
import json
from html.parser import HTMLParser
from elsapy.elsclient import ElsClient
from elsapy.elsdoc import FullDoc
import sys


## Load configuration
con_file = open("config.json")
config = json.load(con_file)
con_file.close()
APIKEY = config['apikey']

## Initialize client
client = ElsClient(APIKEY)

JOURNAL1 = "European Journal of Medicinal Chemistry"
JOURNAL2 = "Drug Discovery Today"
conditions = []

for i in range(1, len(sys.argv)):
    conditions.append((sys.argv[i], JOURNAL1))
    conditions.append((sys.argv[i], JOURNAL2))


for condition in conditions:

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
                stringList = ["ic50", "ec50", "ki50", "kd50", "ed50"]
                if(doc.read(client) and any(substring in doc.data["originalText"].lower() for substring in stringList)):
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

    print(f"""
    {condition[0]} in {condition[1]}:
    {AMOUNT2} out of {AMOUNT1}

    """)

    print("\n\n (year, occurrence) pairs: ")
    dateArr.sort()
    for pair in dateArr:
        print(tuple(pair))
    print("\n\n")



    class TableParser(HTMLParser):
            def __init__(self):
                HTMLParser.__init__(self)

                self.tableFound = False
                self.headerFound = False
                self.headerRowFound = False
                self.firstHeaderFound = False
                self.firstHeader = []

                self.bodyFound = False
                self.bodyRowFound = False
                self.firstColumn = False
                self.firstColumnContent = []

                self.labelFound = False
                self.label = ""
                self.compoundSet = set()
                
            def handle_starttag(self, tag, attrs):
                if(tag == "ce:table"):
                    self.tableFound = True
                    self.label = ""
                if(self.tableFound and tag == "thead"):
                    self.headerFound = True
                if(self.headerFound and tag == "row"):
                    self.headerRowFound = True
                if(self.headerRowFound and tag == "entry"):
                    self.firstHeaderFound = True

                if(self.tableFound and tag == "tbody"):
                    self.bodyFound = True
                if(self.bodyFound and tag == "row"):
                    self.bodyRowFound = True
                if(self.bodyRowFound and tag == "entry"):
                    self.firstColumn = True

                if(self.tableFound and tag == "ce:label" and (not self.label)):
                    self.labelFound = True


            
            def handle_data(self, data):
                if(self.firstHeaderFound):
                    self.firstHeader.append(data)
                    self.firstHeaderFound = self.headerRowFound = False
                if(self.firstColumn):
                    if(not data or data.isspace()):
                        return
                    self.firstColumnContent.append(data)
                    self.firstColumn = False
                    self.bodyRowFound = False
                if(self.labelFound):
                    self.label = data

            
            def handle_endtag(self, tag):
                if(self.tableFound and tag == "ce:table"):
                    self.tableFound = False

                    nameList = ["compound", "no", "id", "compd", "cpd", "cmp"]
                    compoundFound = False
                    for name1 in nameList:
                        if(compoundFound):
                            break
                        for name2 in self.firstHeader:
                            if(name1 in name2.lower() or name2.lower() in name1):
                                compoundFound = True
                                break
                    
                    if(not compoundFound):
                        for name in self.firstColumnContent:
                            if(len(name) > 1 and name[:-2].isnumeric() and name[-1].isalpha()):
                                compoundFound = True
                                break

                    if(compoundFound):
                        for name in self.firstColumnContent:
                            self.compoundSet.add(name)

                    self.firstHeader.clear()
                    self.firstColumnContent.clear()
                    self.label = ""


                if(self.headerFound and tag == "thead"):
                    self.headerFound = False
                if(self.headerRowFound and tag == "row"):
                    self.headerRowFound = False
                if(self.firstHeaderFound and tag == "entry"):
                    self.firstHeaderFound = False
                
                if(self.bodyFound and tag == "tbody"):
                    self.bodyFound = False
                if(self.bodyRowFound and tag == "row"):
                    self.bodyRowFound = False
                if(self.firstColumn and tag == "entry"):
                    self.firstColumn = False
                if(self.labelFound and tag == "ce:label"):
                    self.labelFound = False
    
    URL = "https://api.elsevier.com/content/article/doi/"
    for DOI in DOIArr:

        header = {"X-ELS-APIKey": APIKEY,
                    "Accept": "text/xml"}
        response = requests.get(URL + DOI, headers=header)           


        tableParser = TableParser()
        print("\n\n")
        print("DOI: " + DOI)
        tableParser.feed(response.text)
        print(f"number of compounds: {len(tableParser.compoundSet)}")
    