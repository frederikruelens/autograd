from __future__ import absolute_import
from __future__ import print_function
import matplotlib.pyplot as plt

import autograd.numpy as np
import autograd.numpy.random as npr
import autograd.scipy.stats.norm as norm

from black_box_svi import black_box_variational_inference
from autograd.optimizers import adam


def make_nn_funs(layer_sizes, L2_reg, noise_variance, nonlinearity=np.tanh):
    """These functions implement a standard multi-layer perceptron,
    vectorized over both training examples and weight samples."""
    shapes = list(zip(layer_sizes[:-1], layer_sizes[1:]))
    num_weights = sum((m+1)*n for m, n in shapes)

    def unpack_layers(weights):
        num_weight_sets = len(weights)
        for m, n in shapes:
            yield weights[:, :m*n]     .reshape((num_weight_sets, m, n)),\
                  weights[:, m*n:m*n+n].reshape((num_weight_sets, 1, n))
            weights = weights[:, (m+1)*n:]

    def predictions(weights, inputs):
        """weights is shape (num_weight_samples x num_weights)
           inputs  is shape (num_datapoints x D)"""
        inputs = np.expand_dims(inputs, 0)
        for W, b in unpack_layers(weights):
            outputs = np.einsum('mnd,mdo->mno', inputs, W) + b
            inputs = nonlinearity(outputs)
        return outputs

    def logprob(weights, inputs, targets):
        log_prior = -L2_reg * np.sum(weights**2, axis=1)
        preds = predictions(weights, inputs)
        log_lik = -np.sum((preds - targets)**2, axis=1)[:, 0] / noise_variance
        return log_prior + log_lik

    return num_weights, predictions, logprob


def build_toy_dataset(n_data=100, noise_std=0.1, toy_example='blackbox'):
    print(toy_example)
    if toy_example == "blackbox":
        D = 1
        rs = npr.RandomState(0)
        inputs  = np.concatenate([np.linspace(0, 2, num=n_data/2),
                                  np.linspace(6, 8, num=n_data/2)])
        targets = np.cos(inputs) + rs.randn(n_data) * noise_std
        inputs = (inputs - 4.0) / 4.0
        inputs  = inputs.reshape((len(inputs), D))
        targets = targets.reshape((len(targets), D))
    if toy_example == "Wierstra":
        noise_std = 0.02
        inputs = np.linspace(0, 0.5, n_data).reshape(-1,1)
        n_traces = 1
        noise1 = noise_std * np.random.randn(n_data, n_traces)
        noise2 = noise_std * np.random.randn(n_data, n_traces)
        noise3 = noise_std * np.random.randn(n_data, n_traces)
        x1 = np.tile(input, n_traces).reshape(n_traces, -1)
        term1 = 0.3 * np.sin(2 * np.pi * (inputs + noise1))
        term2 = 0.3 * np.sin(4 * np.pi * (inputs + noise2))
        targets = inputs + term1 + term2 + noise3
        x_real = np.linspace(-0.2, 1.2, n_traces)
        y_real = x_real + 0.3 * np.sin(2 * np.pi * (x_real)) + 0.3 * np.sin(4 * np.pi * (x_real))
        targets = targets.reshape(-1,1)

    return inputs, targets


if __name__ == '__main__':

    toy_example = "Wierstra" # blackbox or Wierstra

    # Specify inference problem by its unnormalized log-posterior.
    rbf = lambda x: np.exp(-x**2)
    relu = lambda x: np.maximum(x, 0.)
    num_weights, predictions, logprob = \
        make_nn_funs(layer_sizes=[1, 20, 20, 1], L2_reg=0.1,
                     noise_variance=0.01, nonlinearity=rbf)

    inputs, targets = build_toy_dataset(n_data = 100, noise_std=0.1, toy_example=toy_example)
    log_posterior = lambda weights, t: logprob(weights, inputs, targets)

    # Build variational objective.
    objective, gradient, unpack_params = \
        black_box_variational_inference(log_posterior, num_weights,
                                        num_samples=20)

    # Set up figure.
    fig = plt.figure(figsize=(12, 8), facecolor='white')
    ax = fig.add_subplot(111, frameon=False)
    plt.ion()
    plt.show(block=False)


    def callback(params, t, g):
        print("Iteration {} lower bound {}".format(t, -objective(params, t)))

        # Sample functions from posterior.
        rs = npr.RandomState(0)
        mean, log_std = unpack_params(params)
        #rs = npr.RandomState(0)
        sample_weights = rs.randn(10, num_weights) * np.exp(log_std) + mean
        if toy_example == "blackbox":
            plot_inputs = np.linspace(-8, 8, num=400)
            y_lim = [-2, 3]
        elif toy_example == "Wierstra":
            plot_inputs = np.linspace(-0.2, 1.2, num=400)
            y_lim = [-0.6, 1.2]


        outputs = predictions(sample_weights, np.expand_dims(plot_inputs, 1))

        # Plot data and functions.
        plt.cla()
        plt.title(toy_example)
        ax.plot(inputs.ravel(), targets.ravel(), 'bx')
        ax.plot(plot_inputs, outputs[:, :, 0].T)
        ax.set_ylim(y_lim)
        plt.draw()
        plt.pause(1.0/60.0)

    # Initialize variational parameters
    rs = npr.RandomState(0)
    init_mean    = rs.randn(num_weights)
    init_log_std = -5 * np.ones(num_weights)
    init_var_params = np.concatenate([init_mean, init_log_std])

    print("Optimizing variational parameters...")
    variational_params = adam(gradient, init_var_params,
                              step_size=0.1, num_iters=1000, callback=callback)
