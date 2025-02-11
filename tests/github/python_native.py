# Copyright (C) 2020-2021 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Python native tests."""

import numpy as np
import json

import openfl.native as fx


def one_hot(labels, classes):
    """One-hot encode `labels` using `classes` classes."""
    return np.eye(classes)[labels]


fx.init('torch_cnn_mnist')

if __name__ == '__main__':
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import torch.optim as optim
    from torchvision import datasets, transforms

    from openfl.federated import FederatedModel, FederatedDataSet

    # TODO: Remove after update to torchvision==0.9.1
    # See https://github.com/pytorch/vision/issues/3549
    datasets.MNIST.resources = [
        ('https://ossci-datasets.s3.amazonaws.com/mnist/train-images-idx3-ubyte.gz',
            'f68b3c2dcbeaaa9fbdd348bbdeb94873'),
        ('https://ossci-datasets.s3.amazonaws.com/mnist/train-labels-idx1-ubyte.gz',
            'd53e105ee54ea40749a09fcbcd1e9432'),
        ('https://ossci-datasets.s3.amazonaws.com/mnist/t10k-images-idx3-ubyte.gz',
            '9fb629c4189551a2d022fa330f9573f3'),
        ('https://ossci-datasets.s3.amazonaws.com/mnist/t10k-labels-idx1-ubyte.gz',
            'ec29112dd5afa0611ce80d1b7f02629c')
    ]

    def cross_entropy(output, target):
        """Binary cross-entropy metric."""
        return F.binary_cross_entropy_with_logits(input=output, target=target)

    class Net(nn.Module):
        """PyTorch Neural Network."""

        def __init__(self):
            """Initialize."""
            super(Net, self).__init__()
            self.conv1 = nn.Conv2d(1, 16, 3)
            self.pool = nn.MaxPool2d(2, 2)
            self.conv2 = nn.Conv2d(16, 32, 3)
            self.fc1 = nn.Linear(32 * 5 * 5, 32)
            self.fc2 = nn.Linear(32, 84)
            self.fc3 = nn.Linear(84, 10)

        def forward(self, x):
            """Forward pass of the network."""
            x = self.pool(F.relu(self.conv1(x)))
            x = self.pool(F.relu(self.conv2(x)))
            x = x.view(x.size(0), -1)
            x = F.relu(self.fc1(x))
            x = F.relu(self.fc2(x))
            x = self.fc3(x)
            return F.log_softmax(x, dim=1)

    transform = transforms.Compose([transforms.ToTensor(),
                                    transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))])

    trainset = datasets.MNIST(root='./data', train=True,
                              download=True, transform=transform)

    train_images, train_labels = trainset.train_data, np.array(trainset.train_labels)
    train_images = torch.from_numpy(np.expand_dims(train_images, axis=1)).float()
    train_labels = one_hot(train_labels, 10)

    validset = datasets.MNIST(root='./data', train=False,
                              download=True, transform=transform)

    valid_images, valid_labels = validset.test_data, np.array(validset.test_labels)
    valid_images = torch.from_numpy(np.expand_dims(valid_images, axis=1)).float()
    valid_labels = one_hot(valid_labels, 10)
    feature_shape = train_images.shape[1]
    classes = 10

    fl_data = FederatedDataSet(train_images, train_labels, valid_images, valid_labels,
                               batch_size=32, num_classes=classes)
    fl_model = FederatedModel(build_model=Net, optimizer=lambda x: optim.Adam(x, lr=1e-4),
                              loss_fn=cross_entropy, data_loader=fl_data)
    collaborator_models = fl_model.setup(num_collaborators=2)
    collaborators = {'one': collaborator_models[0], 'two': collaborator_models[1]}
    print(f'Original training data size: {len(train_images)}')
    print(f'Original validation data size: {len(valid_images)}\n')

    # Collaborator one's data
    print(f'Collaborator one\'s training data size: \
            {len(collaborator_models[0].data_loader.X_train)}')
    print(f'Collaborator one\'s validation data size: \
            {len(collaborator_models[0].data_loader.X_valid)}\n')

    # Collaborator two's data
    print(f'Collaborator two\'s training data size: \
            {len(collaborator_models[1].data_loader.X_train)}')
    print(f'Collaborator two\'s validation data size: \
            {len(collaborator_models[1].data_loader.X_valid)}\n')

    print(json.dumps(fx.get_plan(), indent=4, sort_keys=True))
    final_fl_model = fx.run_experiment(collaborators, {'aggregator.settings.rounds_to_train': 5})
    final_fl_model.save_native('final_pytorch_model')
