from six.moves import xrange
from util import log
from pprint import pprint

import tensorflow.contrib.slim as slim

from preprocessing import create_input_ops

import os
import time
import tensorflow as tf 
import h5py

class Trainer(object):
    @staticmethod
    def get_model_class():
        from model import Model 
        return Model

    def __init__(self, config, dataset, dataset_test):
        self.config =config
        hyper_parameter_str = config.dataset+'_lr_'+str(config.learning_rate)+'_update_G'+str(config.update_rate)+'_D'+str(1)
        self.train_dir = './train_dir/%s-%s-%s'%(config.prefix, hyper_parameter_str, time.strftime("%Y%m%d-%H%M%S"))

        if not os.path.exists(self.train_dir): os.makedirs(self.train_dir)
        
        log.infov("Train Dir: %s", self.train_dir)

        self.batch_size = config.batch_size

        _, self.batch_train = create_input_ops(dataset, self.batch_size, is_training=True)
        _, self.batch_test = create_input_ops(dataset_test, self.batch_size, is_training=False)

        Model = self.get_model_class()
        log.infov("Using Model Class : %s", Model)
        self.model = Model(config)

        self.global_step = tf.contrib.framework.get_or_create_global_step(graph=None)
        self.learning_rate=config.learning_rate
        if config.lr_weight_decay:
            self.learning_rate = tf.train.exponential_decay(self.learning_rate,
                global_step=self.global_step,
                decay_steps=10000,
                decay_rate=0.5,
                staircase=True,
                name='decaying_learning_rate')

        self.check_op = tf.no_op()


        all_vars = tf.trainable_variables()

        d_var = [v for v in all_vars if v.name.startswith('Discriminator')]
        log.warn("********* d_var *********");slim.model_analyzer.analyze_vars(d_var, print_info=True)

        g_var = [v for v in all_vars if v.name.startswith('Generator')]
        log.warn("********* g_var *********"); slim.model_analyzer.analyze_vars(g_var, print_info=True)

        rem_var = (set(all_vars)- set(d_var)-set(g_var))
        print([v.name for v in rem_var]); assert not rem_var


        self.d_optimizer = tf.contrib.layers.optimize_loss(loss=self.model.d_loss, global_step=self.global_step, learning_rate = self.learning_rate*0.5, optimizer = tf.train.AdamOptimizer(beta1=0.5), clip_gradients=20.0, name='d_optimize_loss', variables=d_var)

        self.g_optimizer = tf.contrib.layers.optimize_loss(
            loss=self.model.g_loss,
            global_step=self.global_step,
            learning_rate=self.learning_rate,
            optimizer=tf.train.AdamOptimizer(beta1=0.5),
            clip_gradients=20.0,
            name='g_optimize_loss',
            variables=g_var
        )
        self.summary_op = tf.summary.merge_all()

        self.saver = tf.train.Saver(max_to_keep=100)
        self.pretrain_saver = tf.train.Saver(var_list=all_vars, max_to_keep=1)
        self.summary_writer = tf.summary.FileWriter(self.train_dir)

        self.checkpoint_secs = 600

        self.supervisor = tf.train.Supervisor(logdir = self.train_dir, is_chief = True, saver = None, summary_op=None, summary_writer = self.summary_writer, save_summaries_secs = 300, save_model_secs = self.checkpoint_secs, global_step = self.global_step)

        session_config = tf.ConfigProto(
            allow_soft_placement=True,
            gpu_options=tf.GPUOptions(allow_growth=True),
            device_count={'GPU': 1},
        )
        self.session = self.supervisor.prepare_or_wait_for_session(config=session_config)

        self.ckpt_path = config.checkpoint 
        if self.ckpt_path is not None:
            log.info("Checkpoint path : %s", self.ckpt_path)
            self.saver.restore(self.session, self.ckpt_path)
            log.info("Loaded the pretrain params from given checkpoint")


    def train(self):
        log.infov("training starts")
        pprint(self.batch_train)

        max_steps = 100000

        output_save_step = 1000

        for s in xrange(max_steps):
            step, summary, d_loss, g_loss, step_time, prediction_train, gt_train = self.run_single_step(self.batch_train, step = s, is_train = True)

            if s%10 ==0:
                self.log_step_message(step, d_loss, g_loss, step_time)

            self.summary_writer.add_summary(summary, global_step = step)

            if s % output_save_step == 0:
                log.infov("Saved checkpoint at %d", s)
                save_path = self.saver.save(self.session, os.path.join(self.train_dir, 'model'), global_step=step)
                f = h5py.File(os.path.join(self.train_dir, 'generated_'+str(s)+'.hy'), 'w')
                f['image'] = prediction_train
                f.close()

    def run_single_step(self, batch, step = None, is_train=True):
        _start_time = time.time()

        batch_chunk = self.session.run(batch)

        fetch = [self.global_step, self.summary_op, self.model.d_loss, self.model.g_loss,
                 self.model.all_preds, self.model.all_targets, self.check_op]

        if step % (self.config.update_rate+1)>0:
            fetch.append(self.g_optimizer)

        else:
            fetch.append(self.d_optimizer)

        fetch_values = self.session.run(fetch, feed_dict = self.model.get_feed_dict(batch_chunk, step = step))
        [step, summary, d_loss, g_loss, all_preds, all_targets] = fetch_values[:6]

        _end_time = time.time()

        return step, summary, d_loss, g_loss, (_end_time - _start_time), all_preds, all_targets

    def run_test(self, batch, is_train=False, repeat_times = 8):
        batch_chunk = self.session.run(batch)

        [step, loss, all_preds, all_targets] = self.session.run([self.global_step, self.model.all_preds, aelf.model.all_targets], feed_dict=self.model.get_feed_dict(batch_chunk, is_training=False))

        return loss, all_preds, all_targets

    def log_step_message(self, step, d_loss, g_loss, step_time, is_train=True):
        if step_time==0:step_time=0.001
        log_fn = (is_train and log.info or log.infov)
        log_fn(("[{split_mode:5s} step{step:4d}] "+"D loss: {d_loss:.5f} " +
                "G loss: {g_loss:.5f} " +
                "({sec_per_batch:.3f} sec/batch, {instance_per_sec:.3f} instances/sec)").format(split_mode=(is_train and 'train' or 'val'),
                         step=step,
                         d_loss=d_loss,
                         g_loss=g_loss,
                         sec_per_batch=step_time,
                         instance_per_sec=self.batch_size / step_time))
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch_size', type=int, default=64)
    parser.add_argument('--prefix', type=str, default='default')
    parser.add_argument('--checkpoint', type=str, default=None)
    parser.add_argument('--dataset', type=str, default='CIFAR10',
                        choices=['Fashion', 'CIFAR10'])
    parser.add_argument('--learning_rate', type=float, default=1e-4)
    parser.add_argument('--update_rate', type=int, default=5)
    parser.add_argument('--lr_weight_decay', action='store_true', default=False)
    config = parser.parse_args()

    if config.dataset == 'Fashion':
        import datasets.fashion_mnist as dataset
    elif config.dataset == 'CIFAR10':
        import datasets.cifar10 as dataset
    else:
        raise ValueError(config.dataset)

    config.data_info = dataset.get_data_info()
    config.conv_info = dataset.get_conv_info()
    config.deconv_info = dataset.get_deconv_info()
    dataset_train, dataset_test = dataset.create_default_splits()

    trainer = Trainer(config,
                      dataset_train, dataset_test)

    log.warning("dataset: %s, learning_rate: %f", config.dataset, config.learning_rate)
    trainer.train()

if __name__ == '__main__':
    main()