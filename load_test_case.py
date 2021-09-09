
import random
import numpy as np
import torch
import fastNLP
from fastNLP import logger
import nlp_implementation as nlp

modelDict = nlp.load_pre_trained_nlp_model()


TOTAL_FOLD = 10
SEED = 41
TEST_FILE = '210902F'


def qa_loss_func(start_span_idx, end_span_idx, pred_start, pred_end):

    loss_func = torch.nn.CrossEntropyLoss()
    loss = (loss_func(pred_start, start_span_idx) + loss_func(pred_end, end_span_idx)) / 2
    return loss


@fastNLP.cache_results(f'/data4/chuhan/github-code/chemical-metrics/train_nlp_new/saved/data_set_test_{TEST_FILE}.pkl')
def load_test_data_set():
    raise NotImplementedError


@fastNLP.cache_results('/data4/chuhan/github-code/chemical-metrics/train_nlp_new/saved/data_set_final.pkl')
def load_and_process_data():
    raise NotImplementedError


test_data_set, test_parser_dict = load_test_data_set()
final_data_set_dict, source_vocab, final_parser_dict = load_and_process_data()

source_vocab.index_dataset(*(test_data_set.values()), field_name='raw_words', new_field_name='words')

total_final_result = {}
pre_total_final_result_str = []

key_list = ['train-Ki_MC-has-ans', 'train-Kd_MC-has-ans', 'train-IC50_MC-has-ans', 'train-selectivity_MC-has-ans',
            'train-Kd_Ce-has-ans', 'train-IC50_Ce-has-ans', 'train-EC50_Ce-has-ans', 'train-selectivity_Ce-has-ans',
            'train-hERG_Ce-has-ans', 'train-solubility_Ce-has-ans', 'train-ED50_An-has-ans', 'train-AUC_An-has-ans',
            'train-t_half_An-has-ans', 'train-bioavailability_An-has-ans', 'train-compound-has-ans',
            'train-compound_drug-has-ans']

fold = 0

data_set_name = 'train-hERG_Ce-has-ans'

logger.info(f'{[(k, len(final_data_set_dict[k])) for k in key_list]}')

assert isinstance(data_set_name, str)
logger.info(f'{data_set_name}: {len(final_data_set_dict[data_set_name])}')

log_file_name = f'./log-{TEST_FILE}/{data_set_name[6: -8]}-828B-{TOTAL_FOLD}.log'

logger.info(f'{data_set_name} has {len(final_data_set_dict[data_set_name])} instance. '
            f'start the {TOTAL_FOLD}-fold training')

five_fold = [fastNLP.DataSet() for _ in range(TOTAL_FOLD)]
five_fold_parser = [[] for _ in range(TOTAL_FOLD)]

for idx in range(len(final_data_set_dict[data_set_name])):
    five_fold[idx % TOTAL_FOLD].append(final_data_set_dict[data_set_name][idx])
    five_fold_parser[idx % TOTAL_FOLD].append(final_parser_dict[data_set_name[6: -8]][idx])
if data_set_name in test_data_set.keys():
    for idx in range(len(test_data_set[data_set_name])):
        five_fold[idx % TOTAL_FOLD].append(test_data_set[data_set_name][idx])
        five_fold_parser[idx % TOTAL_FOLD].append(test_parser_dict[data_set_name[6: -8]][idx])

five_fold[fold].apply(lambda x: ' '.join(x['raw_words']), new_field_name='content')
print(five_fold[fold][:20])
for i in range(len(five_fold[fold])):
    print(i, five_fold[fold][i]['content'])
    print(i, five_fold_parser[fold][i].title.lower())
    nlpDict = nlp.get_nlp_results(five_fold_parser[fold][i], **modelDict)
    print("nlpDict: ")
    print(f"single_dict: {nlpDict['single_dict']}")
    print()
    print(f"original_dict: {nlpDict['original_dict']}")
    print('=' * 20)

