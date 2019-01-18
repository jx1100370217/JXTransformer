#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# author: JX
# data: 20181213

import jieba

inputs = open('data/news-commentary.en','r',encoding='UTF-8')
outputs = open('tokenized/tokenized.en','w',encoding='UTF-8')
for line in inputs:
    line_seg = jieba.cut(line,cut_all=False)
    res = " ".join(line_seg)
    outputs.write(res+'\n')

outputs.close()
inputs.close()