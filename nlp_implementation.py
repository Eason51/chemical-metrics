
import os
import warnings
from typing import Union
from collections import Counter

import fastNLP
import torch

from table import ACSTableParser, ScienceDirectTableParser
from tener import TransformerCharEmbed, TENER


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


def load_ner_model(source_vocab, target_vocab, device,
                   file_name='/data4/chuhan/github-code/chemical-metrics/train_nlp_new/saved/model/tener_model.bin'):
    n_heads = 12
    head_dims = 128
    num_layers = 2
    lr = 0.0001
    attn_type = 'adatrans'
    optim_type = 'adam'
    trans_dropout = 0.45  # 有可能是0.4
    batch_size = 24

    char_type = 'adatrans'

    pos_embed = None

    model_type = 'elmo'
    warmup_steps = 0.01
    after_norm = 1
    fc_dropout = 0.4
    normalize_embed = True

    encoding_type = 'bio'
    d_model = n_heads * head_dims
    dim_feedforward = int(2 * d_model)

    char_embed = TransformerCharEmbed(
        vocab=source_vocab, embed_size=30, char_emb_size=30, word_dropout=0,
        dropout=0.3, pool_method='max', activation='relu',
        min_char_freq=2, requires_grad=True, include_word_start_end=False,
        char_attn_type=attn_type, char_n_head=3, char_dim_ffn=60, char_scale=False,
        char_dropout=0.15, char_after_norm=True
    )

    word_embed = fastNLP.embeddings.StaticEmbedding(
        vocab=source_vocab, model_dir_or_name='en-glove-6b-100d',
        requires_grad=True, lower=True, word_dropout=0, dropout=0.5,
        only_norm_found_vector=True)

    embed = fastNLP.embeddings.ElmoEmbedding(vocab=source_vocab, model_dir_or_name='en-original', layers='mix',
                                             requires_grad=False, word_dropout=0.0, dropout=0.5, cache_word_reprs=False)

    embed = fastNLP.embeddings.StackEmbedding([embed, word_embed, char_embed], dropout=0, word_dropout=0.02)

    model = TENER(tag_vocab=target_vocab, embed=embed, num_layers=num_layers,
                  d_model=d_model, n_head=n_heads,
                  feedforward_dim=dim_feedforward, dropout=trans_dropout,
                  after_norm=after_norm, attn_type=attn_type,
                  bi_embed=None,
                  fc_dropout=fc_dropout,
                  pos_embed=pos_embed,
                  scale=attn_type == 'naive')

    static_dict = torch.load(file_name, map_location='cpu')

    if model.transformer.layers[0].self_attn.pos_embed.weights.size() != \
            static_dict['transformer.layers.0.self_attn.pos_embed.weights'].size():
        model.transformer.layers[0].self_attn.pos_embed.weights = \
            torch.randn(static_dict['transformer.layers.0.self_attn.pos_embed.weights'].size())
    if model.transformer.layers[1].self_attn.pos_embed.weights.size() != \
            static_dict['transformer.layers.1.self_attn.pos_embed.weights'].size():
        model.transformer.layers[1].self_attn.pos_embed.weights = \
            torch.randn(static_dict['transformer.layers.1.self_attn.pos_embed.weights'].size())

    model.load_state_dict(static_dict)
    model.eval()
    model.to(device)

    return model


def load_pre_trained_nlp_model(
        data_set_filename: str='/data4/chuhan/github-code/chemical-metrics/saved_pickle/train_data_set_qa_split.pkl',
        model_dir: str='/data4/chuhan/github-code/chemical-metrics/train_nlp_new/saved/model',
        device: str='cuda:0'
):

    # @fastNLP.cache_results(f'{data_set_filename}')
    # def load_data_set():
    #     raise NotImplementedError
    #
    @fastNLP.cache_results(f'/data4/chuhan/github-code/chemical-metrics/saved_pickle/title_id_new.pkl')
    def load_id_with_title():
        raise NotImplementedError
    #
    # split_data_set, title_selected_paper_list = load_data_set()
    # split_data_set.pop('train-ki_ce')
    #
    # source_vocab = fastNLP.Vocabulary()
    # source_vocab.from_dataset(*split_data_set.values(), field_name='words')
    # source_vocab.index_dataset(*split_data_set.values(), field_name='words')
    #
    id_with_title_dict = load_id_with_title()
    assert isinstance(id_with_title_dict, dict)

    @fastNLP.cache_results('/data4/chuhan/github-code/chemical-metrics/train_nlp_new/saved/data_set.pkl')
    def load_and_process_data():
        raise NotImplementedError

    final_data_set_dict, source_vocab = load_and_process_data()

    embed = fastNLP.embeddings.BertEmbedding(
        source_vocab,
        '/data4/chuhan/github-code/chemical-metrics/nlp-pre-trained-weight/bert-base-uncased',
        auto_truncate=True
    )

    model = fastNLP.models.BertForQuestionAnswering(embed)

    with open('/data4/chuhan/github-code/chemical-metrics/files/nlp_data/MedChemPaperData(2).tsv', 'r') as f:
        lines = f.readlines()
        headers = [s.strip() for s in lines[0].strip().split('\t')][5:]
        headers.append('compound_drug')

    data_set = fastNLP.DataSet()

    for data_set_name, data_set_value in final_data_set_dict.items():
        assert isinstance(data_set_name, str)

        # if 'no-ans' in data_set_name:
        #     continue
        if len(data_set_value) == 0:
            continue

        label_name = data_set_name[6: -8]

        def get_target(instance):
            target = ['O'] * len(instance['words'])
            if instance['start_span_idx'] == 0 or instance['end_span_idx'] == 1:
                return target
            target[instance['start_span_idx']] = f'B-{label_name}'
            target[instance['start_span_idx'] + 1: instance['end_span_idx']] = \
                [f'I-{label_name}'] * max(instance['end_span_idx'] - instance['start_span_idx'] - 1, 0)
            return target

        assert isinstance(data_set_value, fastNLP.DataSet)
        data_set_value.apply(get_target, new_field_name='target')
        data_set_value.apply(lambda x: len(x['words']), new_field_name='seq_len')
        for ins in data_set_value:
            data_set.append(ins)

    target_vocab = fastNLP.Vocabulary(unknown=None, padding=None)
    target_vocab.from_dataset(data_set, field_name='target')
    target_vocab.index_dataset(data_set, field_name='target', new_field_name='target')

    ner_model = load_ner_model(source_vocab, target_vocab, device)

    result_dict = {
        'headers': headers,
        'model': model,
        'ner_model': ner_model,
        'id_with_title_dict': id_with_title_dict,
        'source_vocab': source_vocab,
        'device': device,
        'model_dir': model_dir,
        'target_vocab': target_vocab
    }

    return result_dict


def get_nlp_results(table_parser: Union[ACSTableParser, ScienceDirectTableParser], **kwargs) -> dict:
    assert all([k in kwargs for k in ['headers', 'model', 'id_with_title_dict',
                                      'source_vocab', 'device',
                                      'model_dir', 'ner_model', 'target_vocab']])

    def get_query_str(label: str, title: str, compound: str = '<unk>'):
        q_st = f'this paper is about {title}.' \
               f'the main compound is {compound}.' \
               f'in this paragraph, can you find out the result of {label.lower()}?'
        return q_st

    def get_compound_query_str():
        q_st = 'what is the compound in this paper?'
        return q_st

    headers = kwargs.pop('headers')
    model = kwargs.pop('model')
    ner_model = kwargs.pop('ner_model')
    target_vocab = kwargs.pop('target_vocab')
    # id_with_title_dict = kwargs.pop('id_with_title_dict')
    source_vocab = kwargs.pop('source_vocab')
    # qa_data_set = kwargs.pop('qa_data_set')
    device = kwargs.pop('device')
    model_dir = kwargs.pop('model_dir')

    tokenizer = def_tokenizer

    abstract_text = table_parser.abstractBoldText.lower()
    body_text = table_parser.bodyText
    title_text = table_parser.title.lower()

    tokenize_abstract_text = tokenizer(abstract_text)
    tokenize_title_text = tokenizer(title_text)

    compound_str = '<unk>'

    tokenize_title_with_abstract = ['[CLS]'] + tokenizer(get_compound_query_str()) + \
                                   ['[SEP]'] + tokenize_title_text + tokenize_abstract_text + ['[SEP]']

    compound_model_file_name = '/data4/chuhan/github-code/chemical-metrics/train_nlp_new/saved' \
                               '/model/compound_model_210811_new.bin'
    compound_state_dict = torch.load(compound_model_file_name, map_location='cpu')
    model.load_state_dict(compound_state_dict)
    model.eval()
    model.to(device)

    words = [source_vocab.to_index(w) for w in tokenize_title_with_abstract]
    pred_dict = model.predict(torch.tensor([words]).to(device))
    start_span_idx = pred_dict['pred_start'].argmax(dim=-1).item()
    end_span_idx = pred_dict['pred_end'].argmax(dim=-1).item()

    if start_span_idx != 0 and end_span_idx != 1:
        predict_compound = ' '.join(tokenize_title_with_abstract[start_span_idx: end_span_idx])
    else:
        predict_compound = '<unk>'

    result_dict = {'compound': predict_compound}

    tokenize_content_list = [tokenize_title_with_abstract]
    for section in body_text.sections:
        required = ['result']
        if any([r in section.title.lower() for r in required]):
            for p in section.paragraphs:
                for c in p.contents:
                    paper_content = section.title.lower() + ' ' + p.header.lower() + ' ' + c.lower()
                    tokenize_paper_content = tokenizer(paper_content)
                    content_idx = 0
                    while True:
                        tokenize_content_list.append(
                            tokenize_paper_content[content_idx: content_idx + 250])
                        content_idx += 200
                        if content_idx >= len(tokenize_paper_content):
                            break

    o_idx = target_vocab.to_index('O')
    decode_result = {k.lower(): Counter() for k in headers}
    decode_result['compound'] = Counter()
    decode_result['compound'].update([predict_compound] * (1 if predict_compound == '<unk>' else 10))
    for tokenize_content in tokenize_content_list:
        last_label = None

        words = torch.tensor([[source_vocab.to_index(w) for w in tokenize_content]]).to('cuda:0')
        output_logit = ner_model.predict(words)['pred'][0]
        counts = (output_logit == o_idx).float().sum().item()

        if counts != len(tokenize_content):
            # print(f'{idx + 1}' + '=' * 20)
            predictions = output_logit.tolist()
            whole_prediction = []
            for idxx, p in enumerate(predictions):
                if p != o_idx:
                    prediction = target_vocab.to_word(p)
                    current_word = tokenize_content[idxx]
                    assert isinstance(prediction, str) and isinstance(current_word, str)
                    if prediction.startswith('B'):
                        if last_label is not None:
                            decode_result[last_label].update([' '.join(whole_prediction)])
                        whole_prediction = [current_word]
                        last_label = prediction[2:].lower()
                    else:
                        if last_label is None or prediction[2:] != last_label:
                            raise RuntimeError
                        whole_prediction.append(current_word)
                else:
                    if len(whole_prediction) > 0:
                        decode_result[last_label].update([' '.join(whole_prediction)])
                    whole_prediction = []
                    last_label = None

            if last_label is not None:
                decode_result[last_label].update([' '.join(whole_prediction)])

    for u_metric in headers:
        metric = u_metric.lower()
        if metric == 'compound':
            continue

        metric_vote = Counter()

        try:
            metric_model_file_name = f'/data4/chuhan/github-code/chemical-metrics/train_nlp_new/saved' \
                                     f'/model/{metric.lower()}_model_210811_new2.bin'
            metric_state_dict = torch.load(metric_model_file_name, map_location='cpu')
        except FileNotFoundError:
            warnings.warn(f'{metric} not found!')
            continue

        model.load_state_dict(metric_state_dict)
        model.eval()
        model.to(device)

        for idx, tokenize_content in enumerate(tokenize_content_list):
            tokenize_query = tokenizer(get_query_str(metric.lower(), title_text, compound_str))
            new_tokenize_content = ['[CLS]'] + tokenize_query + ['[SEP]'] + tokenize_content + ['[SEP]']

            words = [source_vocab.to_index(w) for w in new_tokenize_content]
            pred_dict = model.predict(torch.tensor([words]).to(device))
            start_span_idx = pred_dict['pred_start'].argmax(dim=-1).item()
            end_span_idx = pred_dict['pred_end'].argmax(dim=-1).item()

            if start_span_idx != 0 and end_span_idx != 1:
                predict_metric = ' '.join(new_tokenize_content[start_span_idx: end_span_idx])
            else:
                predict_metric = '<unk>'

            if predict_metric != '<unk>' and predict_metric != predict_compound:
                metric_vote.update([predict_metric] * (1 if idx == 0 else 2))

        if len(metric_vote) > 0:
            metric_result = metric_vote.most_common(1)[0][0]
        else:
            metric_result = ''

        if len(metric_result) > 0:
            decode_result[metric].update([metric_result])

    for k, v in decode_result.items():
        if len(decode_result[k]) == 0:
            continue
        if k == 'compound':
            continue
        rank_list = decode_result[k].most_common()
        rank = 0
        while True:
            if rank >= len(rank_list):
                break
            if rank_list[rank][0] not in result_dict.values():
                break
            rank += 1
        if rank < len(rank_list):
            result_dict[k] = rank_list[rank][0]

    decode_result = {k: decode_result[k].most_common(1)[0][0] for k in decode_result.keys()
                     if len(decode_result[k]) > 0}

    return {'single_dict': result_dict, 'original_dict': decode_result}


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


