#!/bin/bash

epochs=1
file_num=10

for ((i=0; i<$epochs; i++))
do

	for ((j=0; j<$file_num; j++)) 
	do
		python nematus/train.py --source_dataset data/big_data/train_split/train_${j}.en --target_dataset data/big_data/train_split/train_${j}.zh --dictionaries data/big_data/vocab_en.json data/big_data/vocab_zh.json --valid_source_dataset data/big_data/dev.en --valid_target_dataset data/big_data/dev.zh --batch_size 160 --patience 1000 --disp_freq 100 --model model/big_model/transformer_20190114 
	done

done
