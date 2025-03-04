import torch
import torch.nn as nn
from torch.distributions.normal import Normal
import torch.utils.data as data
import numpy as np
import matplotlib.pyplot as plt
from torch.distributions.uniform import Uniform


class Flow1d(nn.Module):
    def __init__(self, n_components):
        super(Flow1d, self).__init__()
        self.mus = nn.Parameter(torch.randn(n_components), requires_grad=True)
        self.log_sigmas = nn.Parameter(
            torch.zeros(n_components), requires_grad=True)
        self.weight_logits = nn.Parameter(
            torch.ones(n_components), requires_grad=True)

    def forward(self, x):
        x = x.view(-1, 1)
        weights = self.weight_logits.softmax(dim=0).view(1, -1)
        distribution = Normal(self.mus, self.log_sigmas.exp())
        z = (distribution.cdf(x) * weights).sum(dim=1)
        log_dz_by_dx = (distribution.log_prob(
            x).exp() * weights).sum(dim=1).log()
        return z, log_dz_by_dx


class LogitTransform(nn.Module):
    def __init__(self, alpha):
        super(LogitTransform, self).__init__()
        self.alpha = alpha

    def forward(self, x):
        x_new = self.alpha/2 + (1-self.alpha)*x
        z = torch.log(x_new) - torch.log(1-x_new)
        log_dz_by_dx = torch.log(torch.FloatTensor(
            [1-self.alpha])) - torch.log(x_new) - torch.log(1-x_new)
        return z, log_dz_by_dx


class FlowComposable1d(nn.Module):
    def __init__(self, flow_models_list):
        super(FlowComposable1d, self).__init__()
        self.flow_models_list = nn.ModuleList(flow_models_list)

    def forward(self, x):
        z, sum_log_dz_by_dx = x, 0
        for flow in self.flow_models_list:
            z, log_dz_by_dx = flow(z)
            sum_log_dz_by_dx += log_dz_by_dx
        return z, sum_log_dz_by_dx


def loss_function(target_distribution, z, log_dz_by_dx):
    log_likelihood = target_distribution.log_prob(z) + log_dz_by_dx
    return -log_likelihood.mean()


def train(model, train_loader, optimizer, target_distribution):
    model.train()
    for x in train_loader:
        z, log_dz_by_dx = model(x)
        loss = loss_function(target_distribution, z, log_dz_by_dx)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()


def eval_loss(model, data_loader, target_distribution):
    model.eval()
    total_loss = 0
    for x in data_loader:
        z, log_dz_by_dx = model(x)
        loss = loss_function(target_distribution, z, log_dz_by_dx)
        total_loss += loss * x.size(0)
    return (total_loss / len(data_loader.dataset)).item()


def train_and_eval(epochs, lr, train_loader, test_loader, target_distribution):
    flow_models_list = [Flow1d(2), LogitTransform(
        0.1), Flow1d(2), LogitTransform(0.1), Flow1d(2)]
    flow = FlowComposable1d(flow_models_list)
    optimizer = torch.optim.Adam(flow.parameters(), lr=lr)
    train_losses, test_losses = [], []
    for epoch in range(epochs):
        train(flow, train_loader, optimizer, target_distribution)
        train_losses.append(eval_loss(flow, train_loader, target_distribution))
        test_losses.append(eval_loss(flow, test_loader, target_distribution))
    return flow, train_losses, test_losses


def generate_mixture_of_gaussians(num_of_points):
    n = num_of_points // 3
    gaussian1 = np.random.normal(loc=-1, scale=0.25, size=(n,))
    gaussian2 = np.random.normal(loc=1.5, scale=0.35, size=(n,))
    gaussian3 = np.random.normal(loc=0.0, scale=0.2, size=(num_of_points-2*n,))
    return np.concatenate([gaussian1, gaussian2, gaussian3])


class NumpyDataset(data.Dataset):
    def __init__(self, array):
        super().__init__()
        self.array = array

    def __len__(self):
        return len(self.array)

    def __getitem__(self, index):
        return self.array[index]


if __name__ == '__main__':
    n_train, n_test = 2000, 1000
    train_data = generate_mixture_of_gaussians(n_train)
    test_data = generate_mixture_of_gaussians(n_test)

    train_loader = data.DataLoader(NumpyDataset(
        train_data), batch_size=128, shuffle=True)
    test_loader = data.DataLoader(NumpyDataset(
        test_data), batch_size=128, shuffle=True)

    _, axes = plt.subplots(1, 2, figsize=(12, 4))
    _ = axes[0].hist(train_loader.dataset.array, bins=50)
    _ = axes[1].hist(test_loader.dataset.array, bins=50)
    _ = axes[0].set_title('Training data')
    _ = axes[1].set_title('Testing data')
    plt.show()

    target_distribution = Uniform(0.0, 1.0)
    flow, train_losses, test_losses = train_and_eval(
        150, 1e-2, train_loader, test_loader, target_distribution)

    _ = plt.plot(train_losses, label='train_loss')
    _ = plt.plot(test_losses, label='test_loss')
    plt.legend()
    plt.show()

    x = np.linspace(-3, 3, 1000)
    with torch.no_grad():
        z, log_dz_by_dx = flow(torch.FloatTensor(x))
        px = (target_distribution.log_prob(z) + log_dz_by_dx).exp()

    _, axes = plt.subplots(1, 2, figsize=(12, 4))
    _ = axes[0].grid(), axes[1].grid()
    _ = axes[0].plot(x, px)
    _ = axes[0].set_title('Learned probability distribution')

    _ = axes[1].plot(x, z)
    _ = axes[1].set_title('x -> z')
    plt.show()
