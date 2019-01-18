#!/usr/bin/env python3
# -*- coding: utf-8 -*-

inputs_en = open('data/big_data/corpus.en','r',encoding='UTF-8')
inputs_zh = open('data/big_data/corpus.zh','r',encoding='UTF-8')
outputs_train_en = open('data/big_data/train.en','w',encoding='UTF-8')
outputs_train_zh = open('data/big_data/train.zh','w',encoding='UTF-8')
outputs_val_en = open('data/big_data/val.en','w',encoding='UTF-8')
outputs_val_zh = open('data/big_data/val.zh','w',encoding='UTF-8')
outputs_test_en = open('data/big_data/test.en','w',encoding='UTF-8')
outputs_test_zh = open('data/big_data/test.zh','w',encoding='UTF-8')
inputs_list_en = []
inputs_list_zh = []
# 将英文语料分成训练集train,验证集val和测试集test
for line in inputs_en:
    inputs_list_en.append(line.strip())

print(len(inputs_list_en))

for line in inputs_list_en[:20000000]:
    outputs_train_en.write(line+"\n")
for line in inputs_list_en[20000000:22500000]:
	outputs_val_en.write(line+"\n")
for line in inputs_list_en[22500000:]:
    outputs_test_en.write(line+"\n")
# 将中文语料分成训练集train和测试集test
for line in inputs_zh:
    inputs_list_zh.append(line.strip())

print(len(inputs_list_zh))

for line in inputs_list_zh[:20000000]:
    outputs_train_zh.write(line+"\n")
for line in inputs_list_zh[20000000:22500000]:
	outputs_val_zh.write(line+"\n")
for line in inputs_list_zh[22500000:]:
    outputs_test_zh.write(line+"\n")

inputs_en.close()
inputs_zh.close()
outputs_train_en.close()
outputs_train_zh.close()
outputs_test_en.close()
outputs_test_zh.close()
print("Done")
