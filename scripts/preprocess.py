#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# author: JX
# data: 20181213

inputs = open('mydata/corpus','r',encoding='UTF-8')
outputs1 = open('data/corpus.zh','w',encoding='UTF-8')
outputs2 = open('data/corpus.en','w',encoding='UTF-8')
for line in inputs:
    content = line.split('\t')
    outputs1.writelines(content[0]+'\n')
    outputs2.writelines(content[1]+'\n')

inputs.close()
outputs1.close()
outputs2.close()
