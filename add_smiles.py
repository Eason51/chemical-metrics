from findImage import TARGETNAME
import json
import cv2
import os
from PIL import Image
import chemschematicresolver as csr
from molecular_Structure_Similarity import molecularSimles


inputName = ""
outputName = ""
TARGET = ""
tempImagePath = ""

def scale(filePath, width=None, height=None):
    """指定宽或高，得到按比例缩放后的宽高

    :param filePath:图片的绝对路径
    :param width:目标宽度
    :param height:目标高度
    :return:按比例缩放后的宽和高
    """
    if not width and not height:
        width, height = Image.open(filePath).size  # 原图片宽高
    if not width or not height:
        _width, _height = Image.open(filePath).size
        height = width * _height / _width if width else height
        width = height * _width / _height if height else width
    return int(width), int(height)

with open(f"results/{TARGETNAME.lower()}/{inputName}",'r',encoding='utf-8')as fp:
    json_data = json.load(fp)

drug_molecule_paper = json_data["drug_molecule_paper"]
for i in drug_molecule_paper:
    if i['compound_smiles'] == "":
        imageId = i["paper_id"]
        imagePath = f'imagePaths/{TARGET}/{imageId}.jpeg'
        if scale(imagePath)[0] >= scale(imagePath)[1]:
            width, height = scale(imagePath, width=1500)
            img = Image.open(imagePath)
            # resize
            out = img.resize((width, height))
            out.save(tempImagePath)
            # 从resize的图片抽smiles molecularSimles()
            (simles, positionResult) = molecularSimles(tempImagePath)
            i['compound_smiles'] = simles
            if i['compound_smiles'] == "":
                width, height = scale(imagePath, width=1300)
                img = Image.open(imagePath)
                # resize
                out = img.resize((width, height))
                out.save(tempImagePath)
                # 从resize的图片抽smiles
                (simles, positionResult) = molecularSimles(tempImagePath)
                i['compound_smiles'] = simles

                if i['compound_smiles'] == "":
                    width, height = scale(imagePath, width=1100)
                    img = Image.open(imagePath)
                    # resize
                    out = img.resize((width, height))
                    out.save(tempImagePath)
                    # 从resize的图片抽smiles
                    (simles, positionResult) = molecularSimles(tempImagePath)
                    i['compound_smiles'] = simles
                    if i['compound_smiles'] == "":
                        width, height = scale(imagePath, width=900)
                        img = Image.open(imagePath)
                        # resize
                        out = img.resize((width, height))
                        out.save(tempImagePath)
                        # 从resize的图片抽smiles
                        smiles = ""
        else:
            width, height = scale(imagePath, height=1500)
            img = Image.open(imagePath)
            # resize
            out = img.resize((width, height))
            out.save(tempImagePath)
            # 从resize的图片抽smiles
            (simles, positionResult) = molecularSimles(tempImagePath)
            i['compound_smiles'] = simles
            if i['compound_smiles'] == "":
                width, height = scale(imagePath, height=1300)
                img = Image.open(imagePath)
                # resize
                out = img.resize((width, height))
                out.save(tempImagePath)
                # 从resize的图片抽smiles
                (simles, positionResult) = molecularSimles(tempImagePath)
                i['compound_smiles'] = simles

                if i['compound_smiles'] == "":
                    width, height = scale(imagePath, height=1100)
                    img = Image.open(imagePath)
                    # resize
                    out = img.resize((width, height))
                    out.save(tempImagePath)
                    # 从resize的图片抽smiles
                    (simles, positionResult) = molecularSimles(tempImagePath)
                    i['compound_smiles'] = simles
                    if i['compound_smiles'] == "":
                        width, height = scale(imagePath, height=900)
                        img = Image.open(imagePath)
                        # resize
                        out = img.resize((width, height))
                        out.save(tempImagePath)
                        # 从resize的图片抽smiles
                        (simles, positionResult) = molecularSimles(tempImagePath)
                        i['compound_smiles'] = simles


with open(f'results/{TARGET}/{outputName}','w', encoding="utf-8")as fp:
    jsonString = json.dumps(json_data, ensure_ascii=False)
    fp.write(jsonString)


# imagePath = '/Users/chuhanshi/Desktop/try.jpeg'
# print(scale(imagePath)[0])
