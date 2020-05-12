# Copyright 2020 Google Research. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Common utils."""

# gtype import
from __future__ import absolute_import, division, print_function

from typing import Text, Union

import tensorflow.compat.v1 as tf

# pylint: disable=logging-format-interpolation
from utils import BatchNormalization, TpuBatchNormalization


class ActivationFn(tf.keras.layers.Layer):
  def __init__(self, act_type: Text, name='activation_fn', **kwargs):

    super(ActivationFn, self).__init__()

    self.act_type = act_type

    if act_type == 'swish':
      self.act = tf.nn.swish
    elif act_type == 'swish_native':
      self.act = lambda x: x * tf.sigmoid(x)
    elif act_type == 'relu':
      self.act = tf.nn.relu
    elif act_type == 'relu6':
      self.act = tf.nn.relu6
    else:
      raise ValueError('Unsupported act_type {}'.format(act_type))

    self.layer = tf.keras.layers.Lambda(lambda x: self.act(x), name=name)

  def call(self, features: tf.Tensor):
    # return features
    return self.layer(features)

  def get_config(self):
    base_config = super(ActivationFn, self).get_config()

    return {
      **base_config,
      'act_type': self.act_type
    }


class BatchNormAct(tf.keras.layers.Layer):
  def __init__(self,
               is_training_bn: bool,
               act_type: Union[Text, None],
               init_zero: bool = False,
               data_format: Text = 'channels_last',
               momentum: float = 0.99,
               epsilon: float = 1e-3,
               use_tpu: bool = False,
               name: Text = None,
               parent_name: Text = None
               ):

    super(BatchNormAct, self).__init__(name=parent_name)

    self.act_type = act_type
    self.training = is_training_bn

    if init_zero:
      self.gamma_initializer = tf.zeros_initializer()
    else:
      self.gamma_initializer = tf.ones_initializer()

    if data_format == 'channels_first':
      self.axis = 1
    else:
      self.axis = 3

    if is_training_bn and use_tpu:
      self.layer = TpuBatchNormalization(axis=self.axis,
                                         momentum=momentum,
                                         epsilon=epsilon,
                                         center=True,
                                         scale=True,
                                         gamma_initializer=self.gamma_initializer,
                                         name=f'{parent_name}/{name}')
    else:
      self.layer = BatchNormalization(axis=self.axis,
                                      momentum=momentum,
                                      epsilon=epsilon,
                                      center=True,
                                      scale=True,
                                      gamma_initializer=self.gamma_initializer,
                                      name=f'{parent_name}/{name}')

    self.act = ActivationFn(act_type, name=parent_name)

  def call(self, inputs, **kwargs):
    x = self.layer.apply(inputs, training=self.training)
    x = self.act.call(x)
    return x


class DropConnect(tf.keras.layers.Layer):
  def __init__(self, survival_prob, name='drop_connect'):
    super(DropConnect, self).__init__(name=name)
    self.survival_prob = survival_prob

    def call(self, inputs: tf.Tensor):
      # Compute tensor.
      batch_size = tf.shape(inputs)[0]
      random_tensor = self.survival_prob
      random_tensor += tf.random_uniform([batch_size, 1, 1, 1], dtype=inputs.dtype)
      binary_tensor = tf.floor(random_tensor)
      # Unlike conventional way that multiply survival_prob at test time, here we
      # divide survival_prob at training time, such that no addition compute is
      # needed at test time.
      output = tf.div(inputs, self.survival_prob) * binary_tensor
      return output
