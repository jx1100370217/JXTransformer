#!/usr/bin/env python3

def delblankline(infile, outfile):
    infopen = open(infile, 'r',encoding='UTF-8')
    outfopen = open(outfile, 'w',encoding='UTF-8')
    lines = infopen.readlines()
    for i in range(len(lines)):
        if i % 2 == 0:
            outfopen.writelines(lines[i])
    infopen.close()
    outfopen.close()

delblankline("tokenized/tokenized.en", "tokenized/all.en")
