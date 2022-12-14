# -*- coding: utf-8 -*-

import os
import argparse

import torch
import torch.nn as nn
from torch.autograd import Variable

from torchvision import datasets
from torchvision import transforms

import PIL
from PIL import Image

from tqdm import tqdm

from models import MnistCNN, CifarCNN, Generator
from utils import fgsm, accuracy, noise_attack, si_ni_fgsm

def load_dataset(args):
    if args.data == "mnist":
        test_loader = torch.utils.data.DataLoader(
            datasets.MNIST(os.path.expanduser("~/.torch/data/mnist"), train=False, download=False,
                           transform=transforms.Compose([
                               transforms.ToTensor()])),
            batch_size=128, shuffle=False)
    elif args.data == "cifar":
        test_loader = torch.utils.data.DataLoader(
            datasets.CIFAR10(os.path.expanduser("~/.torch/data/cifar10"), train=False, download=False,
                             transform=transforms.Compose([
                                 transforms.ToTensor()])),
            batch_size=128, shuffle=False)
    return test_loader


def load_cnn(args):
    if args.data == "mnist":
        return MnistCNN
    elif args.data == "cifar":
        return CifarCNN


def main(args):
    attacktype = args.attack #noise_attack or fgsm

    eps = args.eps
    test_loader = load_dataset(args)

    model_point = torch.load("cnn.tar")
    gan_point = torch.load(args.gan_path)

    CNN = load_cnn(args)

    model = CNN().cuda()
    model.load_state_dict(model_point["state_dict"])

    in_ch = 1 if args.data == "mnist" else 3

    G = Generator(in_ch).cuda()
    G.load_state_dict(gan_point["generator"])
    loss_cre = nn.CrossEntropyLoss().cuda()

    model.eval(), G.eval()
    normal_acc, adv_acc, ape_acc, n = 0, 0, 0, 0
    for x, t in tqdm(test_loader, total=len(test_loader), leave=False):
        x, t = Variable(x.cuda()), Variable(t.cuda())

        y = model(x)
        normal_acc += accuracy(y, t)

        if attacktype == "fgsm": #FGSM attack
          x_adv = fgsm(model, x, t, loss_cre, eps)
        elif attacktype == 'noise_attack': #noise_attack
          x_adv = noise_attack(model, x, t, loss_cre, eps)
        else: #si_ni_fgsm attack
          x_adv = si_ni_fgsm(model, x, t, loss_cre, eps)

            

        # x_adv = fgsm(model, x, t, loss_cre, eps)
        y_adv = model(x_adv)
        adv_acc += accuracy(y_adv, t)

        x_ape = G(x_adv)
        y_ape = model(x_ape)
        ape_acc += accuracy(y_ape, t)
        n += t.size(0)
    print("Accuracy: normal {:.6f}, {} {:.6f}, ape {:.6f}".format(
        normal_acc / n * 100, 
        attacktype, adv_acc / n * 100, 
        ape_acc / n * 100))
    
#     print("Accuracy: normal {:.6f}, fgsm {:.6f}, ape {:.6f}".format(
#         normal_acc / n * 100,
#         adv_acc / n * 100,
#         ape_acc / n * 100))
    if args.adv_path != None:
        img = Image.open(args.adv_path)
        convert_tensor = transforms.Compose([transforms.ToTensor()])
        x_adv = convert_tensor(img).cuda()
        x_ape = G(x_adv.unsqueeze(0))
        y_ape = model(x_adv)
        _, pred = torch.max(y_ape, 1)
        print("predicted label: " + str(pred.item()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default="mnist")
    parser.add_argument("--eps", type=float, default=0.15)
    parser.add_argument("--gan_path", type=str, default="./checkpoint/test/3.tar")
    parser.add_argument("--attack", type=str, default="fgsm") #either fgsm, noise_attack or si_ni_fgsm
    parser.add_argument("--adv_path", type=str, default=None) #define addversarial image path

    args = parser.parse_args()
    main(args)
