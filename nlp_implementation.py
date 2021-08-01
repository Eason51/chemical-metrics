
from typing import Union
from collections import Counter

import fastNLP
import torch

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


def load_pre_trained_nlp_model(
        data_set_filename: str='/data4/chuhan/github-code/chemical-metrics/saved_pickle/train_data_set_qa.pkl',
        model_filename: str='/data4/chuhan/github-code/chemical-metrics/train_nlp/saved_model/qa_model_210729.bin',
        device: str='cuda:0'
):

    @fastNLP.cache_results(f'{data_set_filename}')
    def load_data_set():
        raise NotImplementedError

    @fastNLP.cache_results(f'/data4/chuhan/github-code/chemical-metrics/saved_pickle/title_id_new.pkl')
    def load_id_with_title():
        raise NotImplementedError

    has_answer_qa_data_set, no_answer_qa_data_set, title_selected_paper_list = load_data_set()
    has_answer_qa_data_set.apply(lambda x: len(x['words']), new_field_name='seq_len')
    no_answer_qa_data_set.apply(lambda x: len(x['words']), new_field_name='seq_len')

    qa_data_set = fastNLP.DataSet()
    for instance in has_answer_qa_data_set:
        qa_data_set.append(instance)
        qa_data_set.append(instance)
        qa_data_set.append(instance)
        qa_data_set.append(instance)
        qa_data_set.append(instance)
    for instance in no_answer_qa_data_set:
        qa_data_set.append(instance)

    source_vocab = fastNLP.Vocabulary()
    source_vocab.from_dataset(qa_data_set, field_name='words', no_create_entry_dataset=None)
    source_vocab.index_dataset(qa_data_set, field_name='words', new_field_name='words')
    qa_data_set.set_input('words')
    qa_data_set.set_target('start_span_idx', 'end_span_idx')

    id_with_title_dict = load_id_with_title()
    assert isinstance(id_with_title_dict, dict)

    static_dict = torch.load(model_filename, map_location='cpu')

    embed = fastNLP.embeddings.BertEmbedding(
        source_vocab,
        '/data4/chuhan/github-code/chemical-metrics/nlp-pre-trained-weight/bert-base-uncased',
        auto_truncate=True
    )

    model = fastNLP.models.BertForQuestionAnswering(embed)
    model.load_state_dict(static_dict)
    model.eval()
    model.to(device)

    with open('/data4/chuhan/github-code/chemical-metrics/files/nlp_data/MedChemPaperData(2).tsv', 'r') as f:
        lines = f.readlines()
        headers = [s.strip() for s in lines[0].strip().split('\t')][5:]

    result_dict = {
        'headers': headers,
        'model': model,
        'id_with_title_dict': id_with_title_dict,
        'source_vocab': source_vocab,
        'qa_data_set': qa_data_set,
        'device': device
    }

    return result_dict


def get_nlp_results(table_parser: Union[ACSTableParser, ScienceDirectTableParser], **kwargs) -> dict:
    assert all([k in kwargs for k in ['headers', 'model', 'id_with_title_dict',
                                      'source_vocab', 'qa_data_set', 'device']])

    def get_query_str(prompt_label: str, prompt_target: str = '<unk>', prompt_compound: str = '<unk>'):
        return f'what is the {prompt_label.lower()} of target ' \
               f'{prompt_target.lower()} and compound {prompt_compound.lower()}?'

    headers = kwargs.pop('headers')
    model = kwargs.pop('model')
    # id_with_title_dict = kwargs.pop('id_with_title_dict')
    source_vocab = kwargs.pop('source_vocab')
    # qa_data_set = kwargs.pop('qa_data_set')
    device = kwargs.pop('device')

    tokenizer = def_tokenizer
    title = table_parser.title.lower()
    abstract_text = table_parser.abstractBoldText.lower()
    body_text = table_parser.bodyText

    query_target = get_query_str('target')
    query_compound = get_query_str('compound')

    tokenize_title = tokenizer(title)
    tokenize_abstract = tokenizer(abstract_text)
    tokenize_query_target = tokenizer(query_target)
    tokenize_query_compound = tokenizer(query_compound)

    target_words = ['[CLS]'] + tokenize_query_target + ['[SEP]'] + tokenize_title + tokenize_abstract + ['[SEP]']
    compound_words = ['[CLS]'] + tokenize_query_compound + ['[SEP]'] + tokenize_title + tokenize_abstract + ['[SEP]']

    # print(' '.join(target_words))
    # print(len(target_words))

    target_inputs = torch.tensor([[source_vocab.to_index(w) for w in target_words]]).to(device)
    compound_inputs = torch.tensor([[source_vocab.to_index(w) for w in compound_words]]).to(device)

    # print(target_inputs.size())
    target_results = model(target_inputs)
    compound_results = model(compound_inputs)

    target_start_span = target_results['pred_start'].argmax(dim=-1).item()
    target_end_span = target_results['pred_end'].argmax(dim=-1).item()
    compound_start_span = compound_results['pred_start'].argmax(dim=-1).item()
    compound_end_span = compound_results['pred_end'].argmax(dim=-1).item()

    # if target_start_span == 0 and target_end_span == 1:
    if target_start_span == 0:
        target = '<unk>'
    else:
        target = ' '.join(target_words[target_start_span: target_end_span])
        if len(target) == 0:
            target = '<unk>'
    #  if compound_start_span == 0 and compound_end_span == 1:
    if compound_start_span == 0:
        compound = '<unk>'
    else:
        compound = ' '.join(compound_words[compound_start_span: compound_end_span])
        if len(compound) == 0:
            compound = '<unk>'

    label_result = {'target': [target], 'compound': [compound]}
    for section in body_text.sections:
        required = ['result']
        if any([r in section.title.lower() for r in required]):
            for p in section.paragraphs:
                for c in p.contents:
                    paper_content = section.title.lower() + ' ' + p.header.lower() + ' ' + c.lower()
                    tokenize_paper_content = tokenizer(paper_content)

                    for label in headers:
                        query = get_query_str(label.lower(), target, compound)
                        tokenize_query = tokenizer(query)
                        query_words = ['[CLS]'] + tokenize_query + ['[SEP]'] + tokenize_paper_content + ['[SEP]']
                        query_inputs = torch.tensor([[source_vocab.to_index(w) for w in query_words]]).to(device)

                        query_results = model(query_inputs)
                        query_start_span = query_results['pred_start'].argmax(dim=-1).item()
                        query_end_span = query_results['pred_end'].argmax(dim=-1).item()

                        if query_start_span != 0:
                            query_result = ' '.join(query_words[query_start_span: query_end_span])
                        else:
                            query_result = ''

                        if len(query_result) > 0:
                            if label not in label_result:
                                label_result[label] = []
                            label_result[label].append(query_result)

    # label_result = {k: list(set(v)) for k, v in label_result.items()}
    label_result_counter = {k: Counter() for k in label_result.keys()}
    for k, v in label_result.items():
        for vv in v:
            label_result_counter[k].update([vv])
    label_result = {k: label_result_counter[k].most_common()[0][0] for k in label_result.keys()}

    return label_result


def get_nlp_results_test(table_parser: Union[ACSTableParser, ScienceDirectTableParser], **kwargs) -> dict:
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


