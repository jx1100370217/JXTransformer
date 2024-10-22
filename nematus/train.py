#!/usr/bin/env python
'''
Build a neural machine translation model with soft attention
'''
import collections
from datetime import datetime
import json
import os
import locale
import logging
import subprocess
import sys
import tempfile
import time

import numpy
import tensorflow as tf

from config import read_config_from_cmdline
from data_iterator import TextIterator
import inference
from learning_schedule import ConstantSchedule, TransformerSchedule
import model_loader
from model_updater import ModelUpdater
import rnn_model
from transformer import Transformer as TransformerModel
import util


def load_data(config):
    logging.info('Reading data...')
    text_iterator = TextIterator(
                        source=config.source_dataset,
                        target=config.target_dataset,
                        source_dicts=config.source_dicts,
                        target_dict=config.target_dict,
                        model_type=config.model_type,
                        batch_size=config.batch_size,
                        maxlen=config.maxlen,
                        source_vocab_sizes=config.source_vocab_sizes,
                        target_vocab_size=config.target_vocab_size,
                        skip_empty=True,
                        shuffle_each_epoch=config.shuffle_each_epoch,
                        sort_by_length=config.sort_by_length,
                        use_factor=(config.factors > 1),
                        maxibatch_size=config.maxibatch_size,
                        token_batch_size=config.token_batch_size,
                        keep_data_in_memory=config.keep_train_set_in_memory)

    if config.valid_freq and config.valid_source_dataset and config.valid_target_dataset:
        valid_text_iterator = TextIterator(
                            source=config.valid_source_dataset,
                            target=config.valid_target_dataset,
                            source_dicts=config.source_dicts,
                            target_dict=config.target_dict,
                            model_type=config.model_type,
                            batch_size=config.valid_batch_size,
                            maxlen=config.maxlen,
                            source_vocab_sizes=config.source_vocab_sizes,
                            target_vocab_size=config.target_vocab_size,
                            shuffle_each_epoch=False,
                            sort_by_length=True,
                            use_factor=(config.factors > 1),
                            maxibatch_size=config.maxibatch_size,
                            token_batch_size=config.valid_token_batch_size)
    else:
        logging.info('no validation set loaded')
        valid_text_iterator = None
    logging.info('Done')
    return text_iterator, valid_text_iterator


def train(config, sess):
    assert (config.prior_model != None and (tf.train.checkpoint_exists(os.path.abspath(config.prior_model))) or (config.map_decay_c==0.0)), \
    "MAP training requires a prior model file: Use command-line option --prior_model"

    # Construct the graph, with one model replica per GPU

    num_gpus = len(util.get_available_gpus())
    num_replicas = max(1, num_gpus)

    logging.info('Building model...')
    replicas = []
    for i in range(num_replicas):
        device_type = "GPU" if num_gpus > 0 else "CPU"
        device_spec = tf.DeviceSpec(device_type=device_type, device_index=i)
        with tf.device(device_spec):
            with tf.variable_scope(tf.get_variable_scope(), reuse=(i>0)):
                if config.model_type == "transformer":
                    print('model is transformer')
                    model = TransformerModel(config)
                else:
                    print('model is rnn') 
                    model = rnn_model.RNNModel(config)
                replicas.append(model)

    init = tf.zeros_initializer(dtype=tf.int32)
    global_step = tf.get_variable('time', [], initializer=init, trainable=False)

    if config.learning_schedule == "constant":
        schedule = ConstantSchedule(config.learning_rate)
    elif config.learning_schedule == "transformer":
        schedule = TransformerSchedule(global_step=global_step,
                                       dim=config.state_size,
                                       warmup_steps=config.warmup_steps)
    else:
        logging.error('Learning schedule type is not valid: {}'.format(
            config.learning_schedule))
        sys.exit(1)

    if config.optimizer == 'adam':
        optimizer = tf.train.AdamOptimizer(learning_rate=schedule.learning_rate,
                                           beta1=config.adam_beta1,
                                           beta2=config.adam_beta2,
                                           epsilon=config.adam_epsilon)
    else:
        logging.error('No valid optimizer defined: {}'.format(config.optimizer))
        sys.exit(1)

    if config.summary_freq:
        summary_dir = (config.summary_dir if config.summary_dir is not None
                       else os.path.abspath(os.path.dirname(config.saveto)))
        writer = tf.summary.FileWriter(summary_dir, sess.graph)
    else:
        writer = None

    updater = ModelUpdater(config, num_gpus, replicas, optimizer, global_step,
                           writer)

    saver, progress = model_loader.init_or_restore_variables(
        config, sess, train=True)

    global_step.load(progress.uidx, sess)

    # Use an InferenceModelSet to abstract over model types for sampling and
    # beam search. Multi-GPU sampling and beam search are not currently
    # supported, so we just use the first replica.
    model_set = inference.InferenceModelSet([replicas[0]], [config])

    #save model options
    config_as_dict = collections.OrderedDict(sorted(vars(config).items()))
    json.dump(config_as_dict, open('%s.json' % config.saveto, 'w'), indent=2)

    text_iterator, valid_text_iterator = load_data(config)
    _, _, num_to_source, num_to_target = util.load_dictionaries(config)
    total_loss = 0.
    n_sents, n_words = 0, 0
    last_time = time.time()
    logging.info("Initial uidx={}".format(progress.uidx))
    for progress.eidx in range(progress.eidx, config.max_epochs):
        logging.info('Starting epoch {0}'.format(progress.eidx))
        for source_sents, target_sents in text_iterator:
            if len(source_sents[0][0]) != config.factors:
                logging.error('Mismatch between number of factors in settings ({0}), and number in training corpus ({1})\n'.format(config.factors, len(source_sents[0][0])))
                sys.exit(1)
            x_in, x_mask_in, y_in, y_mask_in = util.prepare_data(
                source_sents, target_sents, config.factors, maxlen=None)
            if x_in is None:
                logging.info('Minibatch with zero sample under length {0}'.format(config.maxlen))
                continue
            write_summary_for_this_batch = config.summary_freq and ((progress.uidx % config.summary_freq == 0) or (config.finish_after and progress.uidx % config.finish_after == 0))
            (factors, seqLen, batch_size) = x_in.shape

            loss = updater.update(sess, x_in, x_mask_in, y_in, y_mask_in,
                                  write_summary_for_this_batch)
            total_loss += loss
            n_sents += batch_size
            n_words += int(numpy.sum(y_mask_in))
            progress.uidx += 1

            if config.disp_freq and progress.uidx % config.disp_freq == 0:
                duration = time.time() - last_time
                disp_time = datetime.now().strftime('[%Y-%m-%d %H:%M:%S]')
                logging.info('{0} Epoch: {1} Update: {2} Loss/word: {3} Words/sec: {4} Sents/sec: {5}'.format(disp_time, progress.eidx, progress.uidx, total_loss/n_words, n_words/duration, n_sents/duration))
                last_time = time.time()
                total_loss = 0.
                n_sents = 0
                n_words = 0

            if config.sample_freq and progress.uidx % config.sample_freq == 0:
                x_small, x_mask_small, y_small = x_in[:, :, :10], x_mask_in[:, :10], y_in[:, :10]
                samples = model_set.sample(sess, x_small, x_mask_small)
                assert len(samples) == len(x_small.T) == len(y_small.T), (len(samples), x_small.shape, y_small.shape)
                for xx, yy, ss in zip(x_small.T, y_small.T, samples):
                    source = util.factoredseq2words(xx, num_to_source)
                    target = util.seq2words(yy, num_to_target)
                    sample = util.seq2words(ss, num_to_target)
                    logging.info('SOURCE: {}'.format(source))
                    logging.info('TARGET: {}'.format(target))
                    logging.info('SAMPLE: {}'.format(sample))

            if config.beam_freq and progress.uidx % config.beam_freq == 0:
                x_small, x_mask_small, y_small = x_in[:, :, :10], x_mask_in[:, :10], y_in[:,:10]
                samples = model_set.beam_search(sess, x_small, x_mask_small,
                                               config.beam_size,
                                               normalization_alpha=0.0)
                # samples is a list with shape batch x beam x len
                assert len(samples) == len(x_small.T) == len(y_small.T), (len(samples), x_small.shape, y_small.shape)
                for xx, yy, ss in zip(x_small.T, y_small.T, samples):
                    source = util.factoredseq2words(xx, num_to_source)
                    target = util.seq2words(yy, num_to_target)
                    logging.info('SOURCE: {}'.format(source))
                    logging.info('TARGET: {}'.format(target))
                    for i, (sample_seq, cost) in enumerate(ss):
                        sample = util.seq2words(sample_seq, num_to_target)
                        msg = 'SAMPLE {}: {} Cost/Len/Avg {}/{}/{}'.format(
                            i, sample, cost, len(sample), cost/len(sample))
                        logging.info(msg)

            if config.valid_freq and progress.uidx % config.valid_freq == 0:
                valid_ce = validate(sess, replicas[0], config,
                                    valid_text_iterator)
                if (len(progress.history_errs) == 0 or
                    valid_ce < min(progress.history_errs)):
                    progress.history_errs.append(valid_ce)
                    progress.bad_counter = 0
                    saver.save(sess, save_path=config.saveto)
                    progress_path = '{0}.progress.json'.format(config.saveto)
                    progress.save_to_json(progress_path)
                else:
                    progress.history_errs.append(valid_ce)
                    progress.bad_counter += 1
                    if progress.bad_counter > config.patience:
                        logging.info('Early Stop!')
                        progress.estop = True
                        break
                if config.valid_script is not None:
                    score = validate_with_script(sess, replicas[0], config)
                    need_to_save = (score is not None and
                        (len(progress.valid_script_scores) == 0 or
                         score > max(progress.valid_script_scores)))
                    if score is None:
                        score = 0.0  # ensure a valid value is written
                    progress.valid_script_scores.append(score)
                    if need_to_save:
                        save_path = config.saveto + ".best-valid-script"
                        saver.save(sess, save_path=save_path)
                        progress_path = '{}.progress.json'.format(save_path)
                        progress.save_to_json(progress_path)

            if config.save_freq and progress.uidx % config.save_freq == 0:
                saver.save(sess, save_path=config.saveto, global_step=progress.uidx)
                progress_path = '{0}-{1}.progress.json'.format(config.saveto, progress.uidx)
                progress.save_to_json(progress_path)

            if config.finish_after and progress.uidx % config.finish_after == 0:
                logging.info("Maximum number of updates reached")
                saver.save(sess, save_path=config.saveto, global_step=progress.uidx)
                progress.estop=True
                progress_path = '{0}-{1}.progress.json'.format(config.saveto, progress.uidx)
                progress.save_to_json(progress_path)
                break
        if progress.estop:
            break


def validate(session, model, config, text_iterator):
    ce_vals, token_counts = calc_cross_entropy_per_sentence(
        session, model, config, text_iterator, normalization_alpha=0.0)
    num_sents = len(ce_vals)
    num_tokens = sum(token_counts)
    sum_ce = sum(ce_vals)
    avg_ce = sum_ce / num_sents
    logging.info('Validation cross entropy (AVG/SUM/N_SENTS/N_TOKENS): {0} ' \
                 '{1} {2} {3}'.format(avg_ce, sum_ce, num_sents, num_tokens))
    return avg_ce


def validate_with_script(session, model, config):
    if config.valid_script == None:
        return None
    logging.info('Starting external validation.')
    out = tempfile.NamedTemporaryFile(mode='w')
    inference.translate_file(input_file=open(config.valid_source_dataset),
                             output_file=out,
                             session=session,
                             models=[model],
                             configs=[config],
                             beam_size=config.beam_size,
                             minibatch_size=config.valid_batch_size,
                             normalization_alpha=1.0)
    out.flush()
    args = [config.valid_script, out.name]
    proc = subprocess.Popen(args, stdin=None, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    stdout_bytes, stderr_bytes = proc.communicate()
    encoding = locale.getpreferredencoding()
    stdout = stdout_bytes.decode(encoding=encoding)
    stderr = stderr_bytes.decode(encoding=encoding)
    if len(stderr) > 0:
        logging.info("Validation script wrote the following to standard "
                     "error:\n" + stderr)
    if proc.returncode != 0:
        logging.warning("Validation script failed (returned exit status of "
                        "{}).".format(proc.returncode))
        return None
    try:
        score = float(stdout.split()[0])
    except:
        logging.warning("Validation script output does not look like a score: "
                        "{}".format(stdout))
        return None
    logging.info("Validation script score: {}".format(score))
    return score


def calc_cross_entropy_per_sentence(session, model, config, text_iterator,
                                    normalization_alpha=0.0):
    """Calculates cross entropy values for a parallel corpus.

    By default (when normalization_alpha is 0.0), the sentence-level cross
    entropy is calculated. If normalization_alpha is 1.0 then the per-token
    cross entropy is calculated. Other values of normalization_alpha may be
    useful if the cross entropy value will be used as a score for selecting
    between translation candidates (e.g. in reranking an n-nbest list). Using
    a different (empirically determined) alpha value can help correct a model
    bias toward too-short / too-long sentences.

    TODO Support for multiple GPUs

    Args:
        session: TensorFlow session.
        model: a RNNModel object.
        config: model config.
        text_iterator: TextIterator.
        normalization_alpha: length normalization hyperparameter.

    Returns:
        A pair of lists. The first contains the (possibly normalized) cross
        entropy value for each sentence pair. The second contains the
        target-side token count for each pair (including the terminating
        <EOS> symbol).
    """
    ce_vals, token_counts = [], []
    for xx, yy in text_iterator:
        if len(xx[0][0]) != config.factors:
            logging.error('Mismatch between number of factors in settings ' \
                          '({0}) and number present in data ({1})'.format(
                          config.factors, len(xx[0][0])))
            sys.exit(1)
        x, x_mask, y, y_mask = util.prepare_data(xx, yy, config.factors,
                                                 maxlen=None)

        # Run the minibatch through the model to get the sentence-level cross
        # entropy values.
        feeds = {model.inputs.x: x,
                 model.inputs.x_mask: x_mask,
                 model.inputs.y: y,
                 model.inputs.y_mask: y_mask,
                 model.inputs.training: False}
        batch_ce_vals = session.run(model.loss_per_sentence, feed_dict=feeds)

        # Optionally, do length normalization.
        batch_token_counts = [numpy.count_nonzero(s) for s in y_mask.T]
        if normalization_alpha:
            adjusted_lens = [n**normalization_alpha for n in batch_token_counts]
            batch_ce_vals /= numpy.array(adjusted_lens)

        ce_vals += list(batch_ce_vals)
        token_counts += batch_token_counts
        logging.info("Seen {}".format(len(ce_vals)))

    assert len(ce_vals) == len(token_counts)
    return ce_vals, token_counts


if __name__ == "__main__":
    # Start logging.
    level = logging.INFO
    logging.basicConfig(level=level, format='%(levelname)s: %(message)s')

    # Parse command-line arguments.
    config = read_config_from_cmdline()
    logging.info(config)

    # Create the TensorFlow session.
    tf_config = tf.ConfigProto()
    tf_config.allow_soft_placement = True

    # Train.
    with tf.Session(config=tf_config) as sess:
        train(config, sess)
