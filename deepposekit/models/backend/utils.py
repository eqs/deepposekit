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

from keras.backend import tf
import numpy as np

__all__ = ['ndims', 'fix', 'fft2d', 'find_maxima',
           'fftshift1d', 'gaussian_kernel_1d', 'gaussian_kernel_2d',
           'degrees', 'radians', 'angle_mod']


def ndims(x):
    return tf.size(tf.shape(x))


def fix(x):
    x = tf.where(x >= 0, tf.floor(x), tf.ceil(x))
    return x


def fft2d(x):
    x = tf.cast(x, tf.complex64)
    x = tf.spectral.fft2d(x)
    return x


def find_maxima(x):

    col_max = tf.reduce_max(x, axis=1)
    row_max = tf.reduce_max(x, axis=2)

    cols = tf.cast(tf.argmax(col_max, 1), tf.float32)
    rows = tf.cast(tf.argmax(row_max, 1), tf.float32)
    cols = tf.reshape(cols, (-1, 1))
    rows = tf.reshape(rows, (-1, 1))

    maxima = tf.concat([rows, cols], -1)

    return maxima


def fftshift1d(x, axis=0):

    x_shape = tf.shape(x)
    x = tf.reshape(x, (-1, 1))
    n_samples = tf.cast(tf.shape(x)[0], tf.float32)
    even = n_samples / 2.
    even = tf.round(even)
    even = even * 2.
    even = tf.equal(n_samples, even)

    def true_fn():
        return x

    def false_fn():
        x_padded = tf.concat([x, tf.zeros((1, 1))], axis=0)
        return x_padded

    x = tf.cond(even, true_fn, false_fn)
    x1, x2 = tf.split(x, 2, axis=axis)

    def true_fn():
        return x2

    def false_fn():
        x2_unpadded = x2[:-1]
        return x2_unpadded

    x2 = tf.cond(even, true_fn, false_fn)
    x = tf.concat((x2, x1), axis=axis)
    x = tf.reshape(x, x_shape)

    return x


def gaussian_kernel_1d(size, sigma):
    size = tf.constant(size, dtype=tf.float32)
    sigma = tf.constant(sigma, dtype=tf.float32)
    x = tf.range(-(size // 2), (size // 2) + 1, dtype=tf.float32)
    kernel = 1 / (sigma * tf.sqrt(2 * np.pi))
    kernel *= tf.exp(-0.5 * (x / sigma)**2)
    return tf.expand_dims(kernel, axis=-1)


def gaussian_kernel_2d(size, sigma):
    kernel = gaussian_kernel_1d(size, sigma)
    kernel = tf.matmul(kernel, kernel, transpose_b=True)
    return kernel


def degrees(x):
    x = x * (180 / np.pi)
    return x


def radians(x):
    x = x * (np.pi / 180)
    return x


def angle_mod(x):
    x_test = fix(x / 360.)
    x = x - 360. * x_test
    x = tf.where(x < 0, x + 360, x)
    return x


def check_angles(x, rotation_guess):
    x = tf.reshape(x, (-1, 1))
    x = angle_mod(x)
    rA = radians(x)
    rA = tf.concat([tf.cos(rA), tf.sin(rA)], axis=-1)
    rI = tf.reshape(rotation_guess, (-1, 1))
    rI = radians(rI)
    rI = tf.concat([tf.cos(rI), tf.sin(rI)], axis=-1)
    guess_test = tf.matmul(rA, rI, transpose_b=True)
    x = tf.where(guess_test < 0, angle_mod(x - 180), x)
    return x
