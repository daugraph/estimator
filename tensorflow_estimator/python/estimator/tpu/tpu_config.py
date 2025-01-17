# Copyright 2017 The TensorFlow Authors. All Rights Reserved.
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
# ===================================================================
"""A RunConfig subclass with TPU support."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections
import json
import os
import tensorflow as tf
from tensorflow.python.util.tf_export import estimator_export
from tensorflow_estimator.python.estimator import run_config as run_config_lib
from tensorflow_estimator.python.estimator.tpu import util as util_lib

# pylint: disable=protected-access
_TF_CONFIG_ENV = run_config_lib._TF_CONFIG_ENV
_SERVICE_KEY = run_config_lib._SERVICE_KEY
_TPU_WORKER_JOB_NAME = 'tpu_worker_job_name'
# pylint: enable=protected-access


@estimator_export(v1=['estimator.tpu.InputPipelineConfig'])
class InputPipelineConfig(object):
  r"""Please see the definition of these values in TPUConfig."""
  PER_SHARD_V1 = 1
  PER_HOST_V1 = 2
  PER_HOST_V2 = 3
  BROADCAST = 4
  SLICED = 5


@estimator_export(v1=['estimator.tpu.TPUConfig'])
class TPUConfig(
    collections.namedtuple('TPUConfig', [
        'iterations_per_loop',
        'num_shards',
        'num_cores_per_replica',
        'per_host_input_for_training',
        'tpu_job_name',
        'initial_infeed_sleep_secs',
        'input_partition_dims',
        'eval_training_input_configuration',
        'experimental_host_call_every_n_steps',
        'experimental_allow_per_host_v2_parallel_get_next',
        'experimental_feed_hook',
    ])):
  r"""TPU related configuration required by `TPUEstimator`.

  Args:
    iterations_per_loop: This is the number of train steps running in TPU system
      before returning to CPU host for each `Session.run`. This means global
      step is increased `iterations_per_loop` times in one `Session.run`. It is
      recommended to be set as number of global steps for next checkpoint. Note
      that in evaluation don't use this value, instead we run total eval `steps`
      on TPU for a single `Session.run`.
      [Experimental]: `iterations_per_loop` can be specified as a time interval.
        To specify N seconds in one `Session.run`, one can specify it as `Ns`
        and substitute the N with the N with the number of desired seconds.
        Alternatively, the unit of time can also be specified in minutes or
        hours, e.g. `3600s` or `60m` or `1h`.
    num_shards: (Deprecated, ignored by TPUEstimator). The number of model
      replicas in the system. For non-model-parallelism case, this number equals
      the total number of TPU cores. For model-parallelism, the total number of
      TPU cores equals num_cores_per_replica * num_shards.
    num_cores_per_replica: Defaults to `None`, which disables model parallelism.
      An integer which describes the number of TPU cores per model replica. This
      is required by model-parallelism which enables partitioning the model to
      multiple cores. Currently num_cores_per_replica must be 1, 2, 4, or 8.
    per_host_input_for_training: If `True`, for `PER_HOST_V1`, the `input_fn` is
      invoked once on each host, and the number of hosts must be smaller or
      equal to the number of replicas. For PER_HOST_V2, the `input_fn` is
      invoked once for each host (if the number of hosts is less than the number
      of replicas) or replica (if the number of replicas is less than the number
      of hosts. With the per-core input pipeline configuration, it is invoked
      once for each core. With a global batch size `train_batch_size` in
      `TPUEstimator` constructor, the batch size for each shard is
      `train_batch_size` // #hosts in the `True` or `PER_HOST_V1` mode. In
      `PER_HOST_V2` mode, it is `train_batch_size` // #cores. In `BROADCAST`
      mode, `input_fn` is only invoked once on host 0 and the tensors are
      broadcasted to all other replicas. The batch size equals to
      `train_batch_size`. With the per-core input pipeline configuration, the
      shard batch size is also `train_batch_size` // #cores.
      Note: per_host_input_for_training==PER_SHARD_V1 only supports mode.TRAIN.
    tpu_job_name: The name of the TPU job. Typically, this name is auto-inferred
      within TPUEstimator, however when using ClusterSpec propagation in more
      esoteric cluster configurations, you may need to specify the job name as a
      string.
    initial_infeed_sleep_secs: The number of seconds the infeed thread should
      wait before enqueueing the first batch. This helps avoid timeouts for
      models that require a long compilation time.
    input_partition_dims: A nested list to describe the partition dims for all
      the tensors from input_fn(). The structure of input_partition_dims must
      match the structure of `features` and `labels` from input_fn(). The total
      number of partitions must match
      `num_cores_per_replica`. For example, if input_fn() returns two tensors:
        images with shape [N, H, W, C] and labels [N]. input_partition_dims =
        [[1, 2, 2, 1], None] will split the images to 4 pieces and feed into 4
        TPU cores. labels tensor are directly broadcasted to all the TPU cores
        since the partition dims is `None`.
      Current limitations: This feature is only supported with the PER_HOST_V2
        input mode.
    eval_training_input_configuration: If `SLICED`, `input_fn` is only invoked
      once on host 0 and the tensors are broadcasted to all other replicas.
      Unlike per_host_input_for_training=BROADCAST, each replica will only get a
      slice of the data instead of a whole copy. If `PER_HOST_V1`, the behaviour
      is determined by per_host_input_for_training.
    experimental_host_call_every_n_steps: Within a training loop, this argument
      sets how often host calls are performed during training. Host calls will
      be evaluated every n steps within a training loop where n is the value of
      this argument.
    experimental_allow_per_host_v2_parallel_get_next: When enabled, allows
      concurrent execution of dataset get next calls when using PER_HOST_V2
      input. May result in a performance increase for models with a small step
      time, but as a consequence TPUEstimator may non-deterministically
      distribute batches to different cores, rather than guaranteeing round
      robin behavior.
    experimental_feed_hook: This is a class which user can provide to the TPU
      estimator to override the default TPUInfeedOutfeedSessionHook implementation
      and add customized implementatioin to handle infeed outfeed logic. If
      given class is None, TPU estimator uses default TPUInfeedOutfeedSessionHook
      implementation in tpu_estimator.py. If not None, TPU estimator uses this
      customized tpu infeed outfeed session hook class rather to override the
      default one.

  Raises:
      ValueError: If `num_cores_per_replica` is not 1, 2, 4, 8, ..., 128.
  """

  def __new__(cls,
              iterations_per_loop=2,
              num_shards=None,
              num_cores_per_replica=None,
              per_host_input_for_training=True,
              tpu_job_name=None,
              initial_infeed_sleep_secs=None,
              input_partition_dims=None,
              eval_training_input_configuration=InputPipelineConfig.PER_HOST_V1,
              experimental_host_call_every_n_steps=1,
              experimental_allow_per_host_v2_parallel_get_next=False,
              experimental_feed_hook=None):

    # Check iterations_per_loop.
    util_lib.parse_iterations_per_loop(iterations_per_loop)

    # Check num_shards.
    if num_shards is not None:
      util_lib.check_positive_integer(num_shards, 'TPUConfig num_shards')

    if input_partition_dims is not None:
      if len(input_partition_dims) != 1 and len(input_partition_dims) != 2:
        raise ValueError(
            'input_partition_dims must be a list/tuple with one or two'
            ' elements.')

      if per_host_input_for_training is not InputPipelineConfig.PER_HOST_V2:
        raise ValueError(
            'input_partition_dims is only supported in PER_HOST_V2 mode.')

      if num_cores_per_replica is None:
        raise ValueError(
            'input_partition_dims requires setting num_cores_per_replica.')

    # Check num_cores_per_replica
    if num_cores_per_replica is not None:
      if num_cores_per_replica not in ([1, 2, 4, 8, 16, 32, 64, 128]):
        raise ValueError(
            'num_cores_per_replica must be 1, 2, 4, 8, 16, 32, 64, 128; '
            'got {}'.format(str(num_cores_per_replica)))

    if eval_training_input_configuration not in [
        InputPipelineConfig.PER_HOST_V1, InputPipelineConfig.SLICED
    ]:
      raise ValueError(
          'eval_training_input_configuration must be PER_HOST_V1 or SLICED;'
          ' got {}'.format(str(eval_training_input_configuration)))

    # per_host_input_for_training may be True, False, or integer in [1..3].
    # Map legacy values (True, False) to numeric values.
    if per_host_input_for_training is False:
      per_host_input_for_training = InputPipelineConfig.PER_SHARD_V1
    elif per_host_input_for_training is True:
      per_host_input_for_training = InputPipelineConfig.PER_HOST_V1

    # Check initial_infeed_sleep_secs.
    if initial_infeed_sleep_secs:
      util_lib.check_positive_integer(initial_infeed_sleep_secs,
                                      'TPUConfig initial_infeed_sleep_secs')

    tpu_job_name = tpu_job_name or _get_tpu_job_name_from_tf_config()

    return super(TPUConfig, cls).__new__(
        cls,
        iterations_per_loop=iterations_per_loop,
        num_shards=num_shards,
        num_cores_per_replica=num_cores_per_replica,
        per_host_input_for_training=per_host_input_for_training,
        tpu_job_name=tpu_job_name,
        initial_infeed_sleep_secs=initial_infeed_sleep_secs,
        input_partition_dims=input_partition_dims,
        eval_training_input_configuration=eval_training_input_configuration,
        experimental_host_call_every_n_steps=(
            experimental_host_call_every_n_steps),
        experimental_allow_per_host_v2_parallel_get_next=(
            experimental_allow_per_host_v2_parallel_get_next),
        experimental_feed_hook=(experimental_feed_hook))


@estimator_export(v1=['estimator.tpu.RunConfig'])
class RunConfig(run_config_lib.RunConfig):
  """RunConfig with TPU support."""

  def __init__(self,
               tpu_config=None,
               evaluation_master=None,
               master=None,
               cluster=None,
               **kwargs):
    """Constructs a RunConfig.

    Args:
      tpu_config: the TPUConfig that specifies TPU-specific configuration.
      evaluation_master: a string. The address of the master to use for eval.
        Defaults to master if not set.
      master: a string. The address of the master to use for training.
      cluster: a ClusterResolver
      **kwargs: keyword config parameters.

    Raises:
      ValueError: if cluster is not None and the provided session_config has a
        cluster_def already.
    """
    super(RunConfig, self).__init__(**kwargs)
    self._tpu_config = tpu_config or TPUConfig()
    self._cluster = cluster

    # If user sets master and/or evaluation_master explicitly, including empty
    # string '', take it. Otherwise, take the values set by parent class.
    if master is not None:
      if cluster is not None:
        raise ValueError('Both master and cluster are set.')
      self._master = master
    else:
      if cluster:
        self._master = cluster.master()

    if evaluation_master is not None:
      self._evaluation_master = evaluation_master
    elif (not self._evaluation_master and
          self.task_type != run_config_lib.TaskType.EVALUATOR):
      # If the task type is EVALUATOR, it means some cluster manager sets the
      # TF_CONFIG. In that case, we respect the configuration in TF_CONFIG.
      #
      # Otherwise, it means user executes the code without external cluster
      # manager. For that, we optimize the user experience by setting
      # evaluation_master to master, unless user overwrites it.
      self._evaluation_master = self._master

    # Set the ClusterSpec to use
    if cluster:
      self._cluster_spec = cluster.cluster_spec()

      # Merge the cluster_def into the ConfigProto.
      if self._session_config is None:  # pylint: disable=access-member-before-definition
        self._session_config = tf.compat.v1.ConfigProto(
            allow_soft_placement=True, isolate_session_state=True)
      if self._session_config.HasField('cluster_def'):
        raise ValueError('You cannot provide a ClusterResolver and '
                         'session_config.cluster_def.')
      if self._cluster_spec:
        self._session_config.cluster_def.CopyFrom(
            self._cluster_spec.as_cluster_def())

  def _maybe_overwrite_session_config_for_distributed_training(self):
    # Overrides the parent class session_config overwrite for between-graph. TPU
    # runs with in-graph, which should not have device filter. Doing nothing
    # ("pass") basically disables it.
    pass

  @property
  def evaluation_master(self):
    return self._evaluation_master

  @property
  def master(self):
    return self._master

  @property
  def tpu_config(self):
    return self._tpu_config

  @property
  def cluster(self):
    return self._cluster

  def replace(self, **kwargs):
    if 'tpu_config' not in kwargs:
      return super(RunConfig, self).replace(**kwargs)

    tpu_config = kwargs.pop('tpu_config')
    new_instance = super(RunConfig, self).replace(**kwargs)
    new_instance._tpu_config = tpu_config  # pylint: disable=protected-access
    return new_instance


def _get_tpu_job_name_from_tf_config():
  """Extracts the TPU job name from TF_CONFIG env variable."""
  # TODO(xiejw): Extends this to support both TF_CONFIG env variable and cluster
  # spec propagation.
  tf_config = json.loads(os.environ.get(_TF_CONFIG_ENV, '{}'))
  tpu_job_name = tf_config.get(_SERVICE_KEY, {}).get(_TPU_WORKER_JOB_NAME)
  if tpu_job_name:
    tf.compat.v1.logging.info('Load TPU job name from TF_CONFIG: %s',
                              tpu_job_name)
  return tpu_job_name
