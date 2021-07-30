
from typing import Union

from table import ACSTableParser, ScienceDirectTableParser


def def_tokenizer(input_str: str):
    special_tag = ['[CLS]', '[SEP]', '<unk>', '<pad>']
    raw_split = input_str.strip().split()
    split_symbol_list = ['.', ',', '?', '!', '(', ')']
    num_list = [f'{str(i)}' for i in range(10)] + ['.', '%']
    final_list = []
    for r in raw_split:
        if r in special_tag:
            final_list.append(r)
            continue

        todo_list = []
        if any([w in r for w in split_symbol_list]):
            to_add = ''
            for w in r:
                if w in split_symbol_list:
                    if len(to_add) > 0:
                        todo_list.append(to_add)
                    todo_list.append(w)
                    to_add = ''
                else:
                    to_add += w
            if len(to_add) > 0:
                todo_list.append(to_add)
        else:
            todo_list.append(r)

        for t in todo_list:
            if all([w in num_list for w in t]):
                for tt in t:
                    final_list.append(tt)
            else:
                final_list.append(t)

    return final_list


def get_nlp_results(table_parser: Union[ACSTableParser, ScienceDirectTableParser]) -> dict:
    result_dict = {}

    title = table_parser.title.lower()
    if title == \
            'inhibition of the signal transducer and activator of transcription-3 (stat3) ' \
            'signaling pathway by 4-oxo-1-phenyl-1,4-dihydroquinoline-3-carboxylic acid esters':
        result_dict['target'] = 'stat3'
        result_dict['compound'] = '<b> 8 </b>'
        result_dict['EC50_Ce'] = '1 7 0 nm'
    elif title == \
        'discovery of 5-chloro-n2-[(1s)-1-(5-fluoropyrimidin-2-yl)ethyl]-n4-(5-methyl-1h-pyrazol-3-yl) ' \
            'pyrimidine-2,4-diamine (azd1480) as a novel inhibitor of the jak/stat pathway':
        result_dict['target'] = ''
        result_dict['compound'] = '<b> 8 </b>'
        result_dict['Ki_MC'] = 'azd1480'
        result_dict['IC50_Ce'] = '<b> 9e </b>'
        result_dict['Ki_Ce'] = 'therapeutic target in the mpns . herein , we disclose the discovery of a series of ' \
                               'pyrazol-3-yl pyrimidin-4-amines and the identification of <b> 9e </b>'
    elif title == \
            'discovery and preclinical profiling of 3-[4-(morpholin-4-yl)-7h-pyrrolo[2,3-d]pyrimidin-5-yl]' \
            'benzonitrile (pf-06447475), a highly potent, selective, brain penetrant, and in vivo active lrrk2 ' \
            'kinase inhibitor':
        result_dict['target'] = '<unk>'
        result_dict['compound'] = '<b> 1 4 </b>'
        result_dict['hERG_Ce'] = '<b> 1 4 </b>'
    elif title == 'nimbolide, a neem limonoid, is a promising candidate for the anticancer drug arsenal':
        result_dict['compound'] = 'nimbolide'
    elif title == 'discovery and optimization of c-2 methyl imidazopyrrolopyridines as potent and orally ' \
                  'bioavailable jak1 inhibitors with selectivity over jak2':
        result_dict['target'] = 'jak2'
        result_dict['compound'] = '<b> 4 </b> exhibited not only improved jak1 potency relative to unsubstituted ' \
                                  'compound <b> 3 </b>'
        result_dict['Ki_MC'] = '20-fold and >33-fold in biochemical and cell-based assays , respectively ) .'
    elif title == 'discovery of 4-arylindolines containing a thiazole moiety as potential antitumor agents ' \
                  'inhibiting the programmed cell death-1/programmed cell death-ligand 1 interaction':
        result_dict['compound'] = '<b> a30 </b>'
    elif title == 'discovery of stat3 and histone deacetylase (hdac) dual-pathway inhibitors for the ' \
                  'treatment of solid cancer':
        result_dict['target'] = 'stat3'
        result_dict['compound'] = '<b> 1 4 </b>'
        result_dict['Kd_MC'] = '3 3 nm'
        result_dict['IC50_Ce'] = '2 3 . 1 5 nm'
        result_dict['Kd_Ce'] = '3 3 nm'
    elif title == 'discovery of novel azetidine amides as potent small-molecule stat3 inhibitors':
        result_dict['target'] = 'stat3'
        result_dict['compound'] = '<b> 5a , 5o </b> , and <b> 8i </b>'
        result_dict['Kd_MC'] = '8 8 0 nm'
        result_dict['Ki_Ce'] = '1 8 μm'
        result_dict['Kd_Ce'] = '8 8 0 nm'
        result_dict['selectivity_Ce'] = '1 8 μm'
    elif title == 'discovery of (e)-n1-(3-fluorophenyl)-n3-(3-(2-(pyridin-2-yl)vinyl)-1h-indazol-6-yl)malonamide ' \
                  '(chmfl-kit-033) as a novel c-kit t670i mutant selective kinase inhibitor for gastrointestinal ' \
                  'stromal tumors (gists)':
        result_dict['target'] = ''
        result_dict['compound'] = '<b> 2 4 </b>'
        result_dict['selectivity_Ce'] = '12-fold'
    elif title == 'structural modification of natural product tanshinone i leading to discovery of novel ' \
                  'nitrogen-enriched derivatives with enhanced anticancer profile and improved drug-like properties':
        result_dict['target'] = ''
        result_dict['compound'] = '<b> 22h </b> demonstrated the most potent'
        result_dict['selectivity_Ce'] = '1 5 . 7 mg/ml'
        result_dict['solubility_An'] = '1 5 . 7 mg/ml'
    return result_dict


