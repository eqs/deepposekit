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

import numpy as np
from keras import Input, Model
from .layers.util import ImageNormalization, Float
from ..utils.image import n_downsample
from .layers.densenet import DenseNet
from .engine import BaseModel


class StackedDenseNet(BaseModel):

    def __init__(self, data_generator, n_stacks=1,
                 n_transitions=-2, n_layers=1,
                 growth_rate=48, bottleneck_factor=1, compression_factor=0.5,
                 batchnorm=False, use_bias=True, activation='selu', pooling='max',
                 interpolation='subpixel', subpixel=True,
                 initializer='glorot_uniform', separable=False, squeeze_excite=False,
                 **kwargs):
        """
        Define a Stacked Fully-Convolutional DenseNet model
        for pose estimation.
        See `References` for details on the model architecture.

        Parameters
        ----------
        data_generator : class pose.DataGenerator
            A pose.DataGenerator class for generating
            images and confidence maps.
        n_stacks : int, default = 1
            The number of encoder-decoder networks to stack
            with intermediate supervision between stacks
        n_transitions : int, default = -1
            The number of transition layers (downsampling and upsampling)
            in each encoder-decoder stack. If value is <0
            the number of transitions will be automatically set
            based on image size as the maximum number of possible
            transitions minus n_transitions plus 1, or:
            n_transitions = max_transitions - n_transitions + 1.
            The default is -1, which uses the maximum number of
            transitions possible.
        n_layers : int, default = 3
            The number of convolutional blocks per dense block
            in the model architecture.
        growth_rate : int, default = 12
            The number of channels to output from each convolutional
            block.
        bottleneck_factor : int, default = 4
            The factor for determining the number of input channels
            to 3x3 convolutional layer in each convolutional block.
            Inputs are first passed through a 1x1 convolutional layer to
            reduce the number of channels to:
            growth_rate * bottleneck_factor
        compression_factor : int, default = 1
            The factor for determining the number of channels passed
            through a transition layer (downsampling or upsampling).
            Inputs are first passed through a 1x1 convolutional layer
            to reduce the number of channels to
            n_input_channels * compression_factor
        batchnorm : bool, default = True
            Whether to use batch normalization in each convolutional block.
            If activation is 'selu' then batchnorm is automatically set to
            False, as the network is already self-normalizing.
        activation: str or callable, default = 'relu'
            The activation function to use for each convolutional layer.
        pooling: str, default = 'average'
            The type of pooling to use during downsampling.
            Must be either 'max' or 'average'.
        interpolation: str, default = 'nearest'
            The type of interpolation to use when upsampling.
            Must be 'nearest', 'bilinear', or 'bicubic'.
            The default is 'nearest', which is the most efficient.
        subpixel: bool, default = True
            Whether to use subpixel maxima for calculating
            keypoint coordinates in the prediction model.
        initializer: str or callable, default='glorot_uniform'
            The initializer for the convolutional kernels.
            Default is 'glorot_uniform' which is the keras default.
            If activation is 'selu', the initializer is automatically
            changed to 'lecun_normal', which is the recommended initializer
            for that activation function [4].

        Attributes
        -------
        train_model: keras.Model
            A model for training the network to produce confidence maps with
            one input layer for images and `n_outputs` output layers for training
            with intermediate supervision
        predict_model: keras.Model
            A model for predicting keypoint coordinates with one input and one output
            using with Maxima2D or SubpixelMaxima2D layers at the output of the network.

        Both of these models share the same computational graph, so training train_model
        updates the weights of predict_model

        References
        ----------
        [1] Jégou, S., Drozdzal, M., Vazquez, D., Romero, A., & Bengio, Y. (2017).
            The one hundred layers tiramisu: Fully convolutional densenets for
            semantic segmentation. In Computer Vision and Pattern Recognition
            Workshops (CVPRW), 2017 IEEE Conference on (pp. 1175-1183). IEEE.
        [2] Newell, A., Yang, K., & Deng, J. (2016). Stacked hourglass networks
            for human pose estimation. In European Conference on Computer
            Vision (pp. 483-499). Springer, Cham.
        [3] Huang, G., Liu, Z., Weinberger, K. Q., & van der Maaten, L. (2017).
            Densely connected convolutional networks. In Proceedings of the IEEE
            conference on computer vision and pattern recognition
            (Vol. 1, No. 2, p. 3).
        [4] Klambauer, G., Unterthiner, T., Mayr, A., & Hochreiter, S. (2017).
            Self-normalizing neural networks. In Advances in Neural Information
            Processing Systems (pp. 972-981).
        """

        self.n_stacks = n_stacks
        self.n_layers = n_layers
        self.growth_rate = growth_rate
        self.bottleneck_factor = bottleneck_factor
        self.compression_factor = compression_factor
        self.batchnorm = batchnorm if activation is not 'selu' else False
        self.use_bias = use_bias
        self.activation = activation
        self.pooling = pooling
        self.interpolation = interpolation
        self.initializer = initializer if activation is not 'selu' else 'lecun_normal'
        self.separable = separable
        self.squeeze_excite = squeeze_excite
        self.n_transitions = n_transitions
        super(StackedDenseNet, self).__init__(data_generator, subpixel, **kwargs)

    def __init_model__(self):
        max_transitions = np.min([n_downsample(self.data_generator.height),
                                  n_downsample(self.data_generator.width)])

        n_transitions = self.n_transitions
        if isinstance(n_transitions, (int, np.integer)):
            if n_transitions == 0:
                raise ValueError('n_transitions cannot equal zero')
            if n_transitions < 0:
                n_transitions += 1
                n_transitions = max_transitions - np.abs(n_transitions)
                self.n_transitions = n_transitions
            elif 0 < n_transitions <= max_transitions:
                self.n_transitions = n_transitions
            else:
                raise ValueError('n_transitions must be in range {0} '
                                 '< n_transitions <= '
                                 '{1}'.format(-max_transitions + 1,
                                              max_transitions))
        else:
            raise TypeError('n_transitions must be integer in range '
                            '{0} < n_transitions <= '
                            '{1}'.format(-max_transitions + 1,
                                         max_transitions))


        batch_shape = (None,
                       self.data_generator.height,
                       self.data_generator.width,
                       self.data_generator.n_channels)

        input_layer = Input(batch_shape=batch_shape,
                            dtype='uint8')
        to_float = Float()(input_layer)
        normalized = ImageNormalization()(to_float)
        concat_list, output0 = DenseNet(n_output_channels=self.data_generator.n_output_channels,
                                        n_downsample=self.n_transitions,
                                        n_upsample=self.n_transitions - self.data_generator.downsample_factor,
                                        n_layers=self.n_layers, growth_rate=self.growth_rate,
                                        bottleneck_factor=self.bottleneck_factor,
                                        compression_factor=self.compression_factor,
                                        activation=self.activation, pooling=self.pooling, interpolation=self.interpolation, batchnorm=self.batchnorm,
                                        use_bias=self.use_bias, separable=self.separable, squeeze_excite=self.squeeze_excite,
                                        stack_idx=0, multiplier=1)([normalized])
        outputs = [output0]
        multiplier = self.n_transitions - self.data_generator.downsample_factor
        for idx in range(self.n_stacks - 1):
            concat_list, output = DenseNet(n_output_channels=self.data_generator.n_output_channels,
                                           n_downsample=self.n_transitions - self.data_generator.downsample_factor,
                                           n_upsample=self.n_transitions - self.data_generator.downsample_factor,
                                           n_layers=self.n_layers, growth_rate=self.growth_rate,
                                           bottleneck_factor=self.bottleneck_factor,
                                           compression_factor=self.compression_factor,
                                           activation=self.activation, pooling=self.pooling, interpolation=self.interpolation, batchnorm=self.batchnorm,
                                           use_bias=self.use_bias, separable=self.separable, squeeze_excite=self.squeeze_excite,
                                           stack_idx=idx+1, multiplier=multiplier)(concat_list)
            outputs.append(output)

        self.train_model = Model(input_layer, outputs,
                                 name=self.__class__.__name__)

    def get_config(self):
        config = {
            'name': self.__class__.__name__,
            'n_stacks': self.n_stacks,
            'n_layers': self.n_layers,
            'n_transitions': self.n_transitions,
            'growth_rate': self.growth_rate,
            'bottleneck_factor': self.bottleneck_factor,
            'compression_factor': self.compression_factor,
            'batchnorm': self.batchnorm,
            'use_bias': self.use_bias,
            'activation': self.activation,
            'pooling': self.pooling,
            'interpolation': self.interpolation,
            'subpixel': self.subpixel,
            'initializer': self.initializer,
            'separable': self.separable,
            'squeeze_excite': self.squeeze_excite
        }
        base_config = super(StackedDenseNet, self).get_config()
        return dict(list(config.items()) + list(base_config.items()))
