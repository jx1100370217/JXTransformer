#!/usr/bin/env python3
# -*- coding: utf-8 -*-

inputs_en = open('train.en','r',encoding='UTF-8')
inputs_zh = open('train.zh','r',encoding='UTF-8')
split_nums = 10
inputs_list_en = []
inputs_list_zh = []
# 将英文语料train.en分成train_1.en,train_2.en,...,train_split_nums.en
for line in inputs_en:
    inputs_list_en.append(line.strip())

print(len(inputs_list_en))
nums_per_split = int(len(inputs_list_en)/split_nums)

for i in range(split_nums): 
	for line in inputs_list_en[i*nums_per_split:(i+1)*nums_per_split]:
		with open('train_split/train_'+ str(i) +'.en','a',encoding='UTF-8') as f:
			f.write(line+"\n")
# 将中文语料train.zh分成train_1.zh,train_2.zh,...,train_split_nums.zh
for line in inputs_zh:
    inputs_list_zh.append(line.strip())

print(len(inputs_list_zh))
nums_per_split = int(len(inputs_list_zh)/split_nums)

for i in range(split_nums):
	for line in inputs_list_zh[i*nums_per_split:(i+1)*nums_per_split]:
		with open('train_split/train_'+ str(i) +'.zh','a',encoding='UTF-8') as f:
			f.write(line+"\n")


inputs_en.close()
inputs_zh.close()
print("Done")
