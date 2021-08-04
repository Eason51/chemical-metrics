import json

with open('output.json','r',encoding='utf-8')as fp:
    json_data = json.load(fp)

drug_molecule_paper = json_data["drug_molecule_paper"]
metrics_paper_count={'IC50_MC':0, 'Ki_MC':0, 'Kd_MC':0, 'Selectivity_MC':0, 'IC50_Ph':0, 'Ki_Ph':0, 'Kd_Ph':0, 'EC50_Ph':0,
                     'Selectivity_Ph':0, 'hERG_Ph':0, 'solubility_Ph':0, 'ED50_Cl':0, 'thalf_Cl':0, 'AUC_Cl':0, 'bio_Cl':0,
                     'solubility_Cl':0,'adverse_1': 0, 'adverse_2': 0, 'adverse_3': 0}
metrics_distribution={'IC50_MC':[], 'Ki_MC':[], 'Kd_MC':[], 'Selectivity_MC':[], 'IC50_Ph':[], 'Ki_Ph':[], 'Kd_Ph':[], 'EC50_Ph':[],
                     'Selectivity_Ph':[], 'hERG_Ph':[], 'solubility_Ph':[], 'ED50_Cl':[], 'thalf_Cl':[], 'AUC_Cl':[], 'bio_Cl':[],
                     'solubility_Cl':[], 'adverse_1': [], 'adverse_2': [], 'adverse_3': []}
for i in drug_molecule_paper:
    if i['medicinal_chemistry_metrics']['IC50']!=0.0:
        metrics_paper_count['IC50_MC'] = metrics_paper_count['IC50_MC']+1
        metrics_distribution['IC50_MC'].append(i['medicinal_chemistry_metrics']['IC50'])
    if i['medicinal_chemistry_metrics']['Ki'] != 0.0:
        metrics_paper_count['Ki_MC'] = metrics_paper_count['Ki_MC'] + 1
        metrics_distribution['Ki_MC'].append(i['medicinal_chemistry_metrics']['Ki'])
    if i['medicinal_chemistry_metrics']['Kd'] != 0.0:
        metrics_paper_count['Kd_MC'] = metrics_paper_count['Kd_MC'] + 1
        metrics_distribution['Kd_MC'].append(i['medicinal_chemistry_metrics']['Kd'])
    if i['medicinal_chemistry_metrics']['selectivity'] != 0:
        metrics_paper_count['Selectivity_MC'] = metrics_paper_count['Selectivity_MC'] + 1
        metrics_distribution['Selectivity_MC'].append(i['medicinal_chemistry_metrics']['selectivity'])
    if i['pharm_metrics_vitro']['IC50']!=0.0:
        metrics_paper_count['IC50_Ph'] = metrics_paper_count['IC50_Ph']+1
        metrics_distribution['IC50_Ph'].append(i['pharm_metrics_vitro']['IC50'])
    if i['pharm_metrics_vitro']['Ki']!=0.0:
        metrics_paper_count['Ki_Ph'] = metrics_paper_count['Ki_Ph']+1
        metrics_distribution['IC50_Ph'].append(i['pharm_metrics_vitro']['IC50'])
    if i['pharm_metrics_vitro']['Kd']!=0.0:
        metrics_paper_count['Kd_Ph'] = metrics_paper_count['Kd_Ph']+1
        metrics_distribution['Kd_Ph'].append(i['pharm_metrics_vitro']['Kd'])
    if i['pharm_metrics_vitro']['selectivity']!=0:
        metrics_paper_count['Selectivity_Ph'] = metrics_paper_count['Selectivity_Ph']+1
        metrics_distribution['Selectivity_Ph'].append(i['pharm_metrics_vitro']['selectivity'])
    if i['pharm_metrics_vitro']['EC50']!=0.0:
        metrics_paper_count['EC50_Ph'] = metrics_paper_count['EC50_Ph']+1
        metrics_distribution['EC50_Ph'].append(i['pharm_metrics_vitro']['EC50'])
    if i['pharm_metrics_vitro']['hERG']!=0.0:
        metrics_paper_count['hERG_Ph'] = metrics_paper_count['hERG_Ph']+1
        metrics_distribution['hERG_Ph'].append(i['pharm_metrics_vitro']['hERG'])
    if i['pharm_metrics_vitro']['solubility']!=0.0:
        metrics_paper_count['solubility_Ph'] = metrics_paper_count['solubility_Ph']+1
        metrics_distribution['solubility_Ph'].append(i['pharm_metrics_vitro']['solubility'])
    if i['pharm_metrics_vivo']['ED50']!=0.0:
        metrics_paper_count['ED50_Cl'] = metrics_paper_count['ED50_Cl']+1
        metrics_distribution['ED50_Cl'].append(i['pharm_metrics_vivo']['ED50'])
    if i['pharm_metrics_vivo']['t_half']!=0.0:
        metrics_paper_count['thalf_Cl'] = metrics_paper_count['thalf_Cl']+1
        metrics_distribution['thalf_Cl'].append(i['pharm_metrics_vivo']['t_half'])
    if i['pharm_metrics_vivo']['AUC']!=0.0:
        metrics_paper_count['AUC_Cl'] = metrics_paper_count['AUC_Cl']+1
        metrics_distribution['AUC_Cl'].append(i['pharm_metrics_vivo']['AUC'])
    if i['pharm_metrics_vivo']['bioavailability']!=0.0:
        metrics_paper_count['bio_Cl'] = metrics_paper_count['bio_Cl']+1
        metrics_distribution['bio_Cl'].append(i['pharm_metrics_vivo']['bioavailability'])
    if i['pharm_metrics_vivo']['solubility']!=0.0:
        metrics_paper_count['solubility_Cl'] = metrics_paper_count['solubility_Cl']+1
        metrics_distribution['solubility_Cl'].append(i['pharm_metrics_vivo']['solubility'])
    if i['clinical_statistics']:
        metrics_paper_count['adverse_1'] = metrics_paper_count['adverse_1']+ i['clinical_statistics']['p1_company_num']
        for j in list(i['clinical_statistics']['p1_adverse_event'].values()):
            metrics_distribution['adverse_1'].append(j)
        metrics_paper_count['adverse_2'] = metrics_paper_count['adverse_2'] + i['clinical_statistics']['p2_company_num']
        for j in list(i['clinical_statistics']['p2_adverse_event'].values()):
            metrics_distribution['adverse_2'].append(j)
        metrics_paper_count['adverse_3'] = metrics_paper_count['adverse_3'] + i['clinical_statistics']['p3_company_num']
        for j in list(i['clinical_statistics']['p3_adverse_event'].values()):
            metrics_distribution['adverse_3'].append(j)


json_data['metrics_paper_count'] = metrics_paper_count
json_data['metrics_distribution'] = metrics_distribution

with open('processedOutput.json','w')as fp:
    json.dump(json_data,fp)
