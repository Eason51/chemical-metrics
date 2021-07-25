import requests
import json
import datetime
from itertools import chain, groupby
from operator import itemgetter

def getloadClinicalData(drug_name):
    headers = {
        'Accept': 'text/html',
        'User-agent': 'Mozilla/5.0'
    }
    base_url = 'https://clinicaltrials.gov/api/query/study_fields?expr='+drug_name
    fields = '&fields=Phase%2COverallStatus%2CBriefTitle%2COverallOfficialAffiliation%2CFlowAchievementComment%' \
             '2CFlowDropWithdrawComment%2CFlowDropWithdrawType%2CFlowReasonComment%2CEventGroupSeriousNumAffected' \
             '%2CEventGroupSeriousNumAtRisk%2CCompletionDate&min_rnk=1' \
             '&max_rnk=1000&fmt=json'
    all_url=base_url+fields
    r = requests.get(all_url, stream=True, headers=headers, timeout=30)
    if r.status_code == 200:
        return r.json()
    else:
        return json.dumps({})

# 0 Not yet recruiting; 1 Recruiting; 2 Enrolling by invitation; 3 Active, not recruiting; 4 Suspended; 5 Terminated; 6 Completed;
# 7 Withdrawn; 8 Unknown status
def interPhaseProcess(pn_company):
    for i in range(len(pn_company)-1,-1,-1):
        all=set()
        for j in range(0,i):
            # 取并集
            all = all | pn_company[j]

        pn_company[i] = pn_company[i] - all

    return pn_company

def getMaxMerge(a,b):
    get_key, get_val = itemgetter(0), itemgetter(1)
    merged_data = sorted(chain(a.items(), b.items()), key=get_key)
    output = {k: max(map(get_val, g)) for k, g in groupby(merged_data, key=get_key)}

    return output

def getNearstDate(pn_statn_company):
    for i in range(len(pn_statn_company.values())):
        if len(list(pn_statn_company.values())[i])>1:
            # 只保留最近的date
            key = list(pn_statn_company.keys())[i]
            pn_statn_company[key] = max(pn_statn_company.values()[i])
        else:
            key = list(pn_statn_company.keys())[i]
            pn_statn_company[key] = list(pn_statn_company.values())[i][0]

    return pn_statn_company

# Not yet recruiting; Recruiting; Enrolling by invitation; Active, not recruiting; Suspended; Terminated; Completed;
# Withdrawn; Unknown status
def study_num_Phase(results):
    statistics={'p1_company_num': 0, 'p1_stat_company_num' : [0,0,0,0,0,0,0,0,0], 'p1_company' : [], 'p1_terminate_reason':{},'p1_withdraw_reason':{},'p1_adverse_event':{},
                'p2_company_num': 0, 'p2_stat_company_num' : [0,0,0,0,0,0,0,0,0], 'p2_company' : [], 'p2_terminate_reason':{},'p2_withdraw_reason':{},'p2_adverse_event':{},
                'p3_company_num': 0, 'p3_stat_company_num' : [0,0,0,0,0,0,0,0,0], 'p3_company' : [], 'p3_terminate_reason':{},'p3_withdraw_reason':{},'p3_adverse_event':{}}

    p1_stat1_company = []
    p1_stat2_company = []
    p1_stat3_company = []
    p1_stat4_company = []
    p1_stat5_company = []
    p1_stat6_company = {}
    p1_stat7_company = {}
    p1_stat8_company = {}
    p1_stat9_company = {}

    p2_stat1_company = []
    p2_stat2_company = []
    p2_stat3_company = []
    p2_stat4_company = []
    p2_stat5_company = []
    p2_stat6_company = {}
    p2_stat7_company = {}
    p2_stat8_company = {}
    p2_stat9_company = {}

    p3_stat1_company = []
    p3_stat2_company = []
    p3_stat3_company = []
    p3_stat4_company = []
    p3_stat5_company = []
    p3_stat6_company = {}
    p3_stat7_company = {}
    p3_stat8_company = {}
    p3_stat9_company = {}

    for i in results['StudyFieldsResponse']['StudyFields']:
        if 'Phase 1' in i['Phase'] and 'Phase 2' in i['Phase']:
            if i['OverallStatus'][0] == 'Not yet recruiting':
                if i['OverallOfficialAffiliation']:
                    p2_stat1_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Recruiting':
                if i['OverallOfficialAffiliation']:
                    p2_stat2_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Enrolling by invitation':
                if i['OverallOfficialAffiliation']:
                    p2_stat3_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Active, not recruiting':
                if i['OverallOfficialAffiliation']:
                    p2_stat4_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Suspended':
                if i['OverallOfficialAffiliation']:
                    p2_stat5_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Terminated':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p2_stat6_company.keys()):
                        p2_stat6_company[company] = []
                        try:
                            p2_stat6_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p2_stat6_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p2_stat6_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p2_stat6_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    if i['FlowDropWithdrawType'] and company not in list(statistics['p2_terminate_reason']):
                        statistics['p2_terminate_reason'][company] = i['FlowDropWithdrawType'][0]
                    if i['EventGroupSeriousNumAffected'] and i['EventGroupSeriousNumAtRisk'] and company not in list(statistics['p2_adverse_event']):
                        statistics['p2_adverse_event'][company] = float(i['EventGroupSeriousNumAffected'][0])/float(i['EventGroupSeriousNumAtRisk'][0])
                    # p2_stat6_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Completed':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p2_stat7_company.keys()):
                        p2_stat7_company[company] = []
                        try:
                            p2_stat7_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p2_stat7_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p2_stat7_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p2_stat7_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    if i['EventGroupSeriousNumAffected'] and i['EventGroupSeriousNumAtRisk'] and company not in list(statistics['p2_adverse_event']):
                        statistics['p2_adverse_event'][company] = float(i['EventGroupSeriousNumAffected'][0])/float(i['EventGroupSeriousNumAtRisk'][0])
                    # p2_stat7_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Withdrawn':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p2_stat8_company.keys()):
                        p2_stat8_company[company] = []
                        try:
                            p2_stat8_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p2_stat8_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p2_stat8_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p2_stat8_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    if i['FlowDropWithdrawType'] and company not in list(statistics['p2_withdraw_reason']):
                        statistics['p2_withdraw_reason'][company] = i['FlowDropWithdrawType'][0]
                    if i['EventGroupSeriousNumAffected'] and i['EventGroupSeriousNumAtRisk'] and company not in list(statistics['p2_adverse_event']):
                        statistics['p2_adverse_event'][company] = float(i['EventGroupSeriousNumAffected'][0])/float(i['EventGroupSeriousNumAtRisk'][0])
                    # p2_stat8_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Unknown status':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p2_stat9_company.keys()):
                        p2_stat9_company[company] = []
                        try:
                            p2_stat9_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p2_stat9_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p2_stat9_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p2_stat9_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    # p2_stat9_company.append(i['OverallOfficialAffiliation'][0])
        elif 'Phase 2' in i['Phase'] and 'Phase 3' in i['Phase']:
            if i['OverallStatus'][0] == 'Not yet recruiting':
                if i['OverallOfficialAffiliation']:
                    p3_stat1_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Recruiting':
                if i['OverallOfficialAffiliation']:
                    p3_stat2_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Enrolling by invitation':
                if i['OverallOfficialAffiliation']:
                    p3_stat3_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Active, not recruiting':
                if i['OverallOfficialAffiliation']:
                    p3_stat4_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Suspended':
                if i['OverallOfficialAffiliation']:
                    p3_stat5_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Terminated':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p3_stat6_company.keys()):
                        p3_stat6_company[company] = []
                        try:
                            p3_stat6_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p3_stat6_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p3_stat6_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p3_stat6_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    if i['FlowDropWithdrawType'] and company not in list(statistics['p3_terminate_reason']):
                        statistics['p3_terminate_reason'][company] = i['FlowDropWithdrawType'][0]
                    if i['EventGroupSeriousNumAffected'] and i['EventGroupSeriousNumAtRisk'] and company not in list(statistics['p3_adverse_event']):
                        statistics['p3_adverse_event'][company] = float(i['EventGroupSeriousNumAffected'][0])/float(i['EventGroupSeriousNumAtRisk'][0])
                    # p3_stat6_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Completed':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p3_stat7_company.keys()):
                        p3_stat7_company[company] = []
                        try:
                            p3_stat7_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p3_stat7_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p3_stat7_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p3_stat7_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                        if i['EventGroupSeriousNumAffected'] and i[
                            'EventGroupSeriousNumAtRisk'] and company not in list(statistics['p3_adverse_event']):
                            statistics['p3_adverse_event'][company] = float(
                                i['EventGroupSeriousNumAffected'][0]) / float(i['EventGroupSeriousNumAtRisk'][0])
                        # p3_stat7_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Withdrawn':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p3_stat8_company.keys()):
                        p3_stat8_company[company] = []
                        try:
                            p3_stat8_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p3_stat8_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p3_stat8_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p3_stat8_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    if i['FlowDropWithdrawType'] and company not in list(statistics['p3_withdraw_reason']):
                        statistics['p3_withdraw_reason'][company] = i['FlowDropWithdrawType'][0]
                    if i['EventGroupSeriousNumAffected'] and i['EventGroupSeriousNumAtRisk'] and company not in list(statistics['p3_adverse_event']):
                        statistics['p3_adverse_event'][company] = float(i['EventGroupSeriousNumAffected'][0])/float(i['EventGroupSeriousNumAtRisk'][0])
                    # p3_stat8_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Unknown status':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p3_stat9_company.keys()):
                        p3_stat9_company[company] = []
                        try:
                            p3_stat9_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p3_stat9_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p3_stat9_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p3_stat9_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    # p3_stat9_company.append(i['OverallOfficialAffiliation'][0])
        elif 'Phase 1' in i['Phase']:
            if i['OverallStatus'][0] == 'Not yet recruiting':
                if i['OverallOfficialAffiliation']:
                    p1_stat1_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Recruiting':
                if i['OverallOfficialAffiliation']:
                    p1_stat2_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Enrolling by invitation':
                if i['OverallOfficialAffiliation']:
                    p1_stat3_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Active, not recruiting':
                if i['OverallOfficialAffiliation']:
                    p1_stat4_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Suspended':
                if i['OverallOfficialAffiliation']:
                    p1_stat5_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Terminated':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p1_stat6_company.keys()):
                        p1_stat6_company[company] = []
                        try:
                            p1_stat6_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p1_stat6_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p1_stat6_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p1_stat6_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    if i['FlowDropWithdrawType'] and company not in list(statistics['p1_terminate_reason']):
                        statistics['p1_terminate_reason'][company] = i['FlowDropWithdrawType'][0]
                    if i['EventGroupSeriousNumAffected'] and i['EventGroupSeriousNumAtRisk'] and company not in list(statistics['p1_adverse_event']):
                        statistics['p1_adverse_event'][company] = float(i['EventGroupSeriousNumAffected'][0])/float(i['EventGroupSeriousNumAtRisk'][0])
                    # p1_stat6_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Completed':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p1_stat7_company.keys()):
                        p1_stat7_company[company] = []
                        try:
                            p1_stat7_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p1_stat7_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p1_stat7_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p1_stat7_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                        if i['EventGroupSeriousNumAffected'] and i[
                            'EventGroupSeriousNumAtRisk'] and company not in list(statistics['p1_adverse_event']):
                            statistics['p1_adverse_event'][company] = float(
                                i['EventGroupSeriousNumAffected'][0]) / float(i['EventGroupSeriousNumAtRisk'][0])
                        # p1_stat7_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Withdrawn':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p1_stat8_company.keys()):
                        p1_stat8_company[company] = []
                        try:
                            p1_stat8_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p1_stat8_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p1_stat8_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p1_stat8_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    if i['FlowDropWithdrawType'] and company not in list(statistics['p1_withdraw_reason']):
                        statistics['p1_withdraw_reason'][company] = i['FlowDropWithdrawType'][0]
                    if i['EventGroupSeriousNumAffected'] and i['EventGroupSeriousNumAtRisk'] and company not in list(statistics['p1_adverse_event']):
                        statistics['p1_adverse_event'][company] = float(i['EventGroupSeriousNumAffected'][0])/float(i['EventGroupSeriousNumAtRisk'][0])
                    # p1_stat8_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Unknown status':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p1_stat9_company.keys()):
                        p1_stat9_company[company] = []
                        try:
                            p1_stat9_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p1_stat9_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p1_stat9_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p1_stat9_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    # p1_stat9_company.append(i['OverallOfficialAffiliation'][0])
        elif 'Phase 2' in i['Phase']:
            if i['OverallStatus'][0] == 'Not yet recruiting':
                if i['OverallOfficialAffiliation']:
                    p2_stat1_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Recruiting':
                if i['OverallOfficialAffiliation']:
                    p2_stat2_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Enrolling by invitation':
                if i['OverallOfficialAffiliation']:
                    p2_stat3_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Active, not recruiting':
                if i['OverallOfficialAffiliation']:
                    p2_stat4_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Suspended':
                if i['OverallOfficialAffiliation']:
                    p2_stat5_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Terminated':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p2_stat6_company.keys()):
                        p2_stat6_company[company] = []
                        try:
                            p2_stat6_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p2_stat6_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p2_stat6_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p2_stat6_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    if i['FlowDropWithdrawType'] and company not in list(statistics['p2_terminate_reason']):
                        statistics['p2_terminate_reason'][company] = i['FlowDropWithdrawType'][0]
                    if i['EventGroupSeriousNumAffected'] and i['EventGroupSeriousNumAtRisk'] and company not in list(statistics['p2_adverse_event']):
                        statistics['p2_adverse_event'][company] = float(i['EventGroupSeriousNumAffected'][0])/float(i['EventGroupSeriousNumAtRisk'][0])
                    # p2_stat6_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Completed':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p2_stat7_company.keys()):
                        p2_stat7_company[company] = []
                        try:
                            p2_stat7_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p2_stat7_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p2_stat7_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p2_stat7_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    if i['EventGroupSeriousNumAffected'] and i['EventGroupSeriousNumAtRisk'] and company not in list(statistics['p2_adverse_event']):
                        statistics['p2_adverse_event'][company] = float(i['EventGroupSeriousNumAffected'][0])/float(i['EventGroupSeriousNumAtRisk'][0])
                    # p2_stat7_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Withdrawn':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p2_stat8_company.keys()):
                        p2_stat8_company[company] = []
                        try:
                            p2_stat8_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p2_stat8_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p2_stat8_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p2_stat8_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    if i['FlowDropWithdrawType'] and company not in list(statistics['p2_withdraw_reason']):
                        statistics['p2_withdraw_reason'][company] = i['FlowDropWithdrawType'][0]
                    if i['EventGroupSeriousNumAffected'] and i['EventGroupSeriousNumAtRisk'] and company not in list(statistics['p2_adverse_event']):
                        statistics['p2_adverse_event'][company] = float(i['EventGroupSeriousNumAffected'][0])/float(i['EventGroupSeriousNumAtRisk'][0])
                    # p2_stat8_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Unknown status':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p2_stat9_company.keys()):
                        p2_stat9_company[company] = []
                        try:
                            p2_stat9_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p2_stat9_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p2_stat9_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p2_stat9_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    # p2_stat9_company.append(i['OverallOfficialAffiliation'][0])
        elif 'Phase 3' in i['Phase']:
            if i['OverallStatus'][0] == 'Not yet recruiting':
                if i['OverallOfficialAffiliation']:
                    p3_stat1_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Recruiting':
                if i['OverallOfficialAffiliation']:
                    p3_stat2_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Enrolling by invitation':
                if i['OverallOfficialAffiliation']:
                    p3_stat3_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Active, not recruiting':
                if i['OverallOfficialAffiliation']:
                    p3_stat4_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Suspended':
                if i['OverallOfficialAffiliation']:
                    p3_stat5_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Terminated':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p3_stat6_company.keys()):
                        p3_stat6_company[company] = []
                        try:
                            p3_stat6_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p3_stat6_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p3_stat6_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p3_stat6_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    if i['FlowDropWithdrawType'] and company not in list(statistics['p3_terminate_reason']):
                        statistics['p3_terminate_reason'][company] = i['FlowDropWithdrawType'][0]
                    if i['EventGroupSeriousNumAffected'] and i['EventGroupSeriousNumAtRisk'] and company not in list(statistics['p3_adverse_event']):
                        statistics['p3_adverse_event'][company] = float(i['EventGroupSeriousNumAffected'][0])/float(i['EventGroupSeriousNumAtRisk'][0])
                    # p3_stat6_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Completed':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p3_stat7_company.keys()):
                        p3_stat7_company[company] = []
                        try:
                            p3_stat7_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p3_stat7_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p3_stat7_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p3_stat7_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                        if i['EventGroupSeriousNumAffected'] and i[
                            'EventGroupSeriousNumAtRisk'] and company not in list(statistics['p3_adverse_event']):
                            statistics['p3_adverse_event'][company] = float(
                                i['EventGroupSeriousNumAffected'][0]) / float(i['EventGroupSeriousNumAtRisk'][0])
                        # p3_stat7_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Withdrawn':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p3_stat8_company.keys()):
                        p3_stat8_company[company] = []
                        try:
                            p3_stat8_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p3_stat8_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p3_stat8_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p3_stat8_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    if i['FlowDropWithdrawType'] and company not in list(statistics['p3_withdraw_reason']):
                        statistics['p3_withdraw_reason'][company] = i['FlowDropWithdrawType'][0]
                    if i['EventGroupSeriousNumAffected'] and i['EventGroupSeriousNumAtRisk'] and company not in list(statistics['p3_adverse_event']):
                        statistics['p3_adverse_event'][company] = float(i['EventGroupSeriousNumAffected'][0])/float(i['EventGroupSeriousNumAtRisk'][0])
                    # p3_stat8_company.append(i['OverallOfficialAffiliation'][0])
            elif i['OverallStatus'][0] == 'Unknown status':
                if i['OverallOfficialAffiliation']:
                    company = i['OverallOfficialAffiliation'][0]
                    if company not in list(p3_stat9_company.keys()):
                        p3_stat9_company[company] = []
                        try:
                            p3_stat9_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p3_stat9_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    else:
                        try:
                            p3_stat9_company[company].append(datetime.datetime.strptime(i['CompletionDate'][0], '%B %d, %Y'))
                        except:
                            p3_stat9_company[company].append(
                                datetime.datetime.strptime(i['CompletionDate'][0], '%B %Y'))
                    # p3_stat9_company.append(i['OverallOfficialAffiliation'][0])

    p1_stat6_company = getNearstDate(p1_stat6_company)
    p1_stat7_company = getNearstDate(p1_stat7_company)
    p1_stat8_company = getNearstDate(p1_stat8_company)
    p1_stat9_company = getNearstDate(p1_stat9_company)

    overall = getMaxMerge(p1_stat6_company, p1_stat7_company)
    overall = getMaxMerge(overall, p1_stat8_company)
    overall = getMaxMerge(overall, p1_stat9_company)

    p1_stat6_company = {x: p1_stat6_company[x] for x in p1_stat6_company if
                        x in overall and p1_stat6_company[x] == overall[x]}
    p1_stat7_company = {x: p1_stat7_company[x] for x in p1_stat7_company if
                        x in overall and p1_stat7_company[x] == overall[x]}
    p1_stat8_company = {x: p1_stat8_company[x] for x in p1_stat8_company if
                        x in overall and p1_stat8_company[x] == overall[x]}
    p1_stat9_company = {x: p1_stat9_company[x] for x in p1_stat9_company if
                        x in overall and p1_stat9_company[x] == overall[x]}

    p1_stat6_company = list(p1_stat6_company.keys())
    p1_stat7_company = list(p1_stat7_company.keys())
    p1_stat8_company = list(p1_stat8_company.keys())
    p1_stat9_company = list(p1_stat9_company.keys())

    p2_stat6_company = getNearstDate(p2_stat6_company)
    p2_stat7_company = getNearstDate(p2_stat7_company)
    p2_stat8_company = getNearstDate(p2_stat8_company)
    p2_stat9_company = getNearstDate(p2_stat9_company)

    overall = getMaxMerge(p2_stat6_company, p2_stat7_company)
    overall = getMaxMerge(overall, p2_stat8_company)
    overall = getMaxMerge(overall, p2_stat9_company)

    p2_stat6_company = {x: p2_stat6_company[x] for x in p2_stat6_company if
                        x in overall and p2_stat6_company[x] == overall[x]}
    p2_stat7_company = {x: p2_stat7_company[x] for x in p2_stat7_company if
                        x in overall and p2_stat7_company[x] == overall[x]}
    p2_stat8_company = {x: p2_stat8_company[x] for x in p2_stat8_company if
                        x in overall and p2_stat8_company[x] == overall[x]}
    p2_stat9_company = {x: p2_stat9_company[x] for x in p2_stat9_company if
                        x in overall and p2_stat9_company[x] == overall[x]}

    p2_stat6_company = list(p2_stat6_company.keys())
    p2_stat7_company = list(p2_stat7_company.keys())
    p2_stat8_company = list(p2_stat8_company.keys())
    p2_stat9_company = list(p2_stat9_company.keys())

    p3_stat6_company = getNearstDate(p3_stat6_company)
    p3_stat7_company = getNearstDate(p3_stat7_company)
    p3_stat8_company = getNearstDate(p3_stat8_company)
    p3_stat9_company = getNearstDate(p3_stat9_company)

    overall = getMaxMerge(p3_stat6_company, p3_stat7_company)
    overall = getMaxMerge(overall, p3_stat8_company)
    overall = getMaxMerge(overall, p3_stat9_company)

    p3_stat6_company = {x: p3_stat6_company[x] for x in p3_stat6_company if
                        x in overall and p3_stat6_company[x] == overall[x]}
    p3_stat7_company = {x: p3_stat7_company[x] for x in p3_stat7_company if
                        x in overall and p3_stat7_company[x] == overall[x]}
    p3_stat8_company = {x: p3_stat8_company[x] for x in p3_stat8_company if
                        x in overall and p3_stat8_company[x] == overall[x]}
    p3_stat9_company = {x: p3_stat9_company[x] for x in p3_stat9_company if
                        x in overall and p3_stat9_company[x] == overall[x]}

    p3_stat6_company = list(p3_stat6_company.keys())
    p3_stat7_company = list(p3_stat7_company.keys())
    p3_stat8_company = list(p3_stat8_company.keys())
    p3_stat9_company = list(p3_stat9_company.keys())

    statistics['p1_company'].append(set(p1_stat1_company))
    statistics['p1_company'].append(set(p1_stat2_company))
    statistics['p1_company'].append(set(p1_stat3_company))
    statistics['p1_company'].append(set(p1_stat4_company))
    statistics['p1_company'].append(set(p1_stat5_company))
    statistics['p1_company'].append(set(p1_stat6_company))
    statistics['p1_company'].append(set(p1_stat7_company))
    statistics['p1_company'].append(set(p1_stat8_company))
    statistics['p1_company'].append(set(p1_stat9_company))

    statistics['p2_company'].append(set(p2_stat1_company))
    statistics['p2_company'].append(set(p2_stat2_company))
    statistics['p2_company'].append(set(p2_stat3_company))
    statistics['p2_company'].append(set(p2_stat4_company))
    statistics['p2_company'].append(set(p2_stat5_company))
    statistics['p2_company'].append(set(p2_stat6_company))
    statistics['p2_company'].append(set(p2_stat7_company))
    statistics['p2_company'].append(set(p2_stat8_company))
    statistics['p2_company'].append(set(p2_stat9_company))

    statistics['p3_company'].append(set(p3_stat1_company))
    statistics['p3_company'].append(set(p3_stat2_company))
    statistics['p3_company'].append(set(p3_stat3_company))
    statistics['p3_company'].append(set(p3_stat4_company))
    statistics['p3_company'].append(set(p3_stat5_company))
    statistics['p3_company'].append(set(p3_stat6_company))
    statistics['p3_company'].append(set(p3_stat7_company))
    statistics['p3_company'].append(set(p3_stat8_company))
    statistics['p3_company'].append(set(p3_stat9_company))

    statistics['p3_company'] = interPhaseProcess(statistics['p3_company'])

    all = set()
    for i in range(len(statistics['p3_company'])):
        all = all | statistics['p3_company'][i]
        statistics['p3_company'][i] = list(statistics['p3_company'][i])

    statistics['p2_company'][6] = statistics['p2_company'][6] | all
    for i in range(len(statistics['p2_company'])):
        if i != 6:
            statistics['p2_company'][i] = statistics['p2_company'][i] - all
    statistics['p2_company'] = interPhaseProcess(statistics['p2_company'])

    all = set()
    for i in range(len(statistics['p2_company'])):
        all = all | statistics['p2_company'][i]
        statistics['p2_company'][i] = list(statistics['p2_company'][i])

    statistics['p1_company'][6] = statistics['p1_company'][6] | all
    for i in range(len(statistics['p1_company'])):
        if i != 6:
            statistics['p1_company'][i] = statistics['p1_company'][i] - all
    statistics['p1_company'] = interPhaseProcess(statistics['p1_company'])
    for i in range(len(statistics['p1_company'])):
        statistics['p1_company'][i] = list(statistics['p1_company'][i])

    for j in range(len(statistics['p1_company'])):
        statistics['p1_stat_company_num'][j]=len(statistics['p1_company'][j])
    for j in range(len(statistics['p2_company'])):
        statistics['p2_stat_company_num'][j]=len(statistics['p2_company'][j])
    for j in range(len(statistics['p3_company'])):
        statistics['p3_stat_company_num'][j]=len(statistics['p3_company'][j])

    for j in range(len(statistics['p1_stat_company_num'])):
        statistics['p1_company_num']=statistics['p1_company_num']+statistics['p1_stat_company_num'][j]
    for j in range(len(statistics['p2_stat_company_num'])):
        statistics['p2_company_num']=statistics['p2_company_num']+statistics['p2_stat_company_num'][j]
    for j in range(len(statistics['p3_stat_company_num'])):
        statistics['p3_company_num']=statistics['p3_company_num']+statistics['p3_stat_company_num'][j]

    return statistics
