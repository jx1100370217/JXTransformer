#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tensorflow as tf

def generate_tfrecords(tfrecod_filename):
    sequences = [[1], [2, 2], [3, 3, 3], [4, 4, 4, 4], [5, 5, 5, 5, 5],
                 [1], [2, 2], [3, 3, 3], [4, 4, 4, 4]]
    labels = [1, 2, 3, 4, 5, 1, 2, 3, 4]

    with tf.python_io.TFRecordWriter(tfrecod_filename) as f:
        for feature, label in zip(sequences, labels):
            frame_feature = list(map(lambda id: tf.train.Feature(int64_list=tf.train.Int64List(value=[id])), feature))

            example = tf.train.SequenceExample(
                context=tf.train.Features(feature={
                    'label': tf.train.Feature(int64_list=tf.train.Int64List(value=[label]))}),
                feature_lists=tf.train.FeatureLists(feature_list={
                    'sequence': tf.train.FeatureList(feature=frame_feature)
                })
            )
            f.write(example.SerializeToString())



def single_example_parser(serialized_example):
    context_features = {
        "label": tf.FixedLenFeature([], dtype=tf.int64)
    }
    sequence_features = {
        "sequence": tf.FixedLenSequenceFeature([], dtype=tf.int64)
    }

    context_parsed, sequence_parsed = tf.parse_single_sequence_example(
        serialized=serialized_example,
        context_features=context_features,
        sequence_features=sequence_features
    )

    labels = context_parsed['label']
    sequences = sequence_parsed['sequence']
    return sequences, labels

def batched_data(tfrecord_filename, single_example_parser, batch_size, padded_shapes, num_epochs=1, buffer_size=1000):
    dataset = tf.data.TFRecordDataset(tfrecord_filename)\
        .map(single_example_parser)\
        .padded_batch(batch_size, padded_shapes=padded_shapes)\
        .shuffle(buffer_size)\
        .repeat(num_epochs)
    return dataset.make_one_shot_iterator().get_next()


if __name__ == "__main__":
    def model(features, labels):
        return features, labels


    tfrecord_filename = 'test.tfrecord'
    generate_tfrecords(tfrecord_filename)
    out = model(*batched_data(tfrecord_filename, single_example_parser, 2, ([None], [])))

    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    with tf.Session(config=config) as sess:
        init_op = tf.group(tf.global_variables_initializer(),
                           tf.local_variables_initializer())
        sess.run(init_op)
        coord = tf.train.Coordinator()
        threads = tf.train.start_queue_runners(sess=sess, coord=coord)
        try:
            while not coord.should_stop():
                print(sess.run(out))

        except tf.errors.OutOfRangeError:
            print("done training")
        finally:
            coord.request_stop()
        coord.join(threads)