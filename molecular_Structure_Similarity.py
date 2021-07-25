import urllib
import chemschematicresolver as csr
from rdkit import Chem
from rdkit import DataStructs
import easyocr


def downloadPicture(image_path, local_image_path):
    opener = urllib.request.build_opener()
    opener.addheaders = [('User-Agent',
                          'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.106 Safari/537.36')]
    urllib.request.install_opener(opener)
    urllib.request.urlretrieve(image_path, local_image_path)

# 两两计算相似性
def molecularSimilarity(local_image_path1, local_image_path2):
    try:
        result1 = csr.extract_image(local_image_path1)
    except:
        return 10

    try:
        result2 = csr.extract_image(local_image_path2)
    except:
        return 10

    if len(result1)<1 or len(result2)<1:
        return 10
    if len(result1)>1:
        reader = easyocr.Reader(['en'], gpu = False)
        result = reader.readtext(local_image_path1)
        location=[]
        for i in len(result1):
            label=result1[i][0][0]
            flag=0
            for j in len(result):
                if label == result[j][1]:
                    location.append(result[j][0][0][0])
                    flag=1
                    break
        if flag==0:
            for j in len(result):
                if label in result[j][1]:
                    location.append(result[j][0][0][0])
                    break
        max_index=location.index(max(location))
        result1=result1[max_index]
    else:
        result1=result1[0]

    if len(result2)>1:
        reader = easyocr.Reader(['en'], gpu = False)
        result = reader.readtext(local_image_path2)
        location=[]
        for i in len(result2):
            label = result2[i][0][0]
            flag = 0
            for j in len(result):
                if label == result[j][1]:
                    location.append(result[j][0][0][0])
                    flag = 1
                    break
        if flag == 0:
            for j in len(result):
                if label in result[j][1]:
                    location.append(result[j][0][0][0])
                    break
        max_index = location.index(max(location))
        result2 = result2[max_index]
    else:
        result2 = result2[0]

    m1 = Chem.MolFromSmiles(result1[1])
    fps1 = Chem.RDKFingerprint(m1)
    m2 = Chem.MolFromSmiles(result2[1])
    fps2 = Chem.RDKFingerprint(m2)
    return DataStructs.FingerprintSimilarity(fps1, fps2)

def molecularSimilaritybySmiles(smiles1,smiles2):
    m1 = Chem.MolFromSmiles(smiles1)
    fps1 = Chem.RDKFingerprint(m1)
    m2 = Chem.MolFromSmiles(smiles2)
    fps2 = Chem.RDKFingerprint(m2)

    return DataStructs.FingerprintSimilarity(fps1, fps2)

def molecularSimles(local_image_path):
    
    result = []
    
    try:
        result1 = csr.extract_image(local_image_path)
    except:
        return ('', result)

    if len(result1)<1:
        return ('', result)
    if len(result1)>1:
        reader = easyocr.Reader(['en'], gpu = False)
        result = reader.readtext(local_image_path)
        location=[]
        for i in range(len(result1)):
            label=result1[i][0][0]
            flag=0
            for j in range(len(result)):
                if label == result[j][1]:
                    location.append(result[j][0][0][0])
                    flag=1
                    break
        if flag==0:
            for j in range(len(result)):
                if label in result[j][1]:
                    location.append(result[j][0][0][0])
                    break
        max_index=location.index(max(location))
        result1=result1[max_index]
    else:
        result1=result1[0]

    return (result1[1], result)
