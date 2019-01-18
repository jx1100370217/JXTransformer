#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import print_function
from hyperparams import Hyperparams as hp
import tensorflow as tf
import numpy as np
import codecs
import os
import regex
from collections import Counter

def make_vocab(fpath, fname):
    '''构造词典
    
    Args:
      fpath: A string. 输入文件的路径.
      fname: A string. 输出文件的名字.
    
    Writes vocabulary line by line to `vocab/fname`
    '''  
    text = codecs.open(fpath, 'r', 'utf-8').read()
    #text = regex.sub("[^\s\p{Latin}']", "", text)
    words = text.split()
    word2cnt = Counter(words)
    if not os.path.exists('vocab'): os.mkdir('vocab')
    with codecs.open('vocab/{}'.format(fname), 'w', 'utf-8') as fout:
        fout.write("{}\t1000000000\n{}\t1000000000\n{}\t1000000000\n{}\t1000000000\n".format("<PAD>", "<UNK>", "<S>", "</S>"))
        for word, cnt in word2cnt.most_common(len(word2cnt)):
            fout.write(u"{}\t{}\n".format(word, cnt))

if __name__ == '__main__':
    make_vocab("data/news/all.en", "vocab.en")
    make_vocab("data/news/all.zh", "vocab.zh")
    print("Done")
