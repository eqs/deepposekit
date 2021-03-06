# -*- coding: utf-8 -*-
"""
Copyright 2018 Jacob M. Graving <jgraving@gmail.com>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from keras.engine import saving
import h5py
import json
import inspect

from .layers.util import ImageNormalization, Float
from .layers.convolutional import (UpSampling2D,
                                   SubPixelDownscaling,
                                   SubPixelUpscaling)
from .layers.deeplabcut import ResNetPreprocess

from ..io import TrainingGenerator
from .LEAP import LEAP
from .StackedDenseNet import StackedDenseNet
from .StackedHourglass import StackedHourglass
from .DeepLabCut import DeepLabCut

MODELS = {'LEAP': LEAP,
          'StackedDenseNet': StackedDenseNet,
          'StackedHourglass': StackedHourglass,
          'DeepLabCut': DeepLabCut}


CUSTOM_LAYERS = {'Float': Float,
                 'ImageNormalization': ImageNormalization,
                 'UpSampling2D': UpSampling2D,
                 'SubPixelDownscaling': SubPixelDownscaling,
                 'SubPixelUpscaling': SubPixelUpscaling,
                 'ResNetPreprocess': ResNetPreprocess}


def load_model(path, augmenter=None, custom_objects=None, datapath=None):
    '''
    Load the model

    Example
    -------
    model = load_model('model.h5', augmenter)

    '''
    if custom_objects:
        if isinstance(custom_objects, dict):
            base_objects = CUSTOM_LAYERS
            custom_objects = dict(list(base_objects.items()) +
                                  list(custom_objects.items()))
    else:
        custom_objects = CUSTOM_LAYERS

    if isinstance(path, str):
        if path.endswith('.h5') or path.endswith('.hdf5'):
            filepath = path
        else:
            raise ValueError('file must be .h5 file')
    else:
        raise TypeError('file must be type `str`')

    train_model = saving.load_model(filepath,
                                    custom_objects=custom_objects)

    with h5py.File(filepath, 'r') as h5file:
        data_generator_config = h5file.attrs.get('data_generator_config')
        if data_generator_config is None:
            raise ValueError('No data generator found in config file')
        data_generator_config = json.loads(data_generator_config.decode('utf-8'))['config']

        model_config = h5file.attrs.get('pose_model_config')
        if model_config is None:
            raise ValueError('No pose model found in config file')
        model_name = json.loads(model_config.decode('utf-8'))['class_name']
        model_config = json.loads(model_config.decode('utf-8'))['config']
        
    if datapath:
        signature = inspect.signature(TrainingGenerator.__init__)
        keys = [key for key in signature.parameters.keys()]
        keys.remove('self')
        keys.remove('augmenter')
        keys.remove('datapath')
        kwargs = {key: data_generator_config[key] for key in keys}
        kwargs['augmenter'] = augmenter
        kwargs['datapath'] = datapath
        data_generator = TrainingGenerator(**kwargs)
    else:
        data_generator = None

    Model = MODELS[model_name]
    signature = inspect.signature(Model.__init__)
    keys = [key for key in signature.parameters.keys()]
    keys.remove('self')
    keys.remove('data_generator')
    if 'kwargs' in keys:
        keys.remove('kwargs')
    kwargs = {key: model_config[key] for key in keys}
    kwargs['data_generator'] = data_generator
    kwargs['skip_init'] = True

    model = Model(**kwargs)
    model.train_model = train_model
    model.__init_train_model__()

    kwargs = {}
    kwargs['output_shape'] = model_config['output_shape']
    kwargs['n_keypoints'] = model_config['n_keypoints']
    kwargs['downsample_factor'] = model_config['downsample_factor']
    if model_config['sigma']:
        kwargs['output_sigma'] = model_config['sigma']
    else:
        kwargs['output_sigma'] = None
    model.__init_predict_model__(**kwargs)

    return model
