# !/usr/bin/python3.8
# -*- coding: utf-8 -*-
# @Author: qixitan
# @Email: qixitan@qq.com
# @FileName: trainer.py
# @Time: 2022/4/19 16:22

import os
import datetime
from loguru import logger
import torch.backends.cudnn as cudnn

import torch
from torch import nn


class Trainer:
    def __init__(self, exp, args):
        self.exp = exp
        self.args = args

        self.eval_epoch = exp.eval_interval
        self.output_dir = exp.output_dir + "/" + args.exp

        self.best_acc = 0
        self.max_epoch = exp.max_epoch
        self.lr = exp.basic_lr
        self.batch_size = args.batch_size

        self.model = exp.get_model()

        self.loss_func = exp.get_loss_func()
        self.optimizer = exp.get_optimizer(self.lr)
        self.scheduler = exp.get_lr_scheduler()

        self.train_loader = exp.get_data_loader(self.batch_size)
        self.val_loader = exp.get_val_loader(self.batch_size)

    def train(self):
        print("args:{}".format(self.args))
        self.model = nn.DataParallel(self.model)
        cudnn.benchmark = True
        for epoch in range(self.max_epoch):
            self.model.train()
            train_loss, train_corrent, val_corrent = 0, 0, 0
            start_time = datetime.datetime.now()
            for i, data in enumerate(self.train_loader):
                img, label = data
                img, label = img.cuda(), label.cuda()
                self.optimizer.zero_grad()
                outputs = self.model(img)
                loss = self.loss_func(outputs, label)
                loss.backward()
                self.optimizer.step()
                train_loss += loss.item()
                _, pred = torch.max(outputs, 1)
                train_corrent += (pred == label).sum()
            end_time = datetime.datetime.now()
            train_batch_time = (end_time - start_time).seconds / len(
                self.train_loader.dataset) * self.batch_size  # 每个batch_size训练时间
            train_acc = train_corrent / len(self.train_loader.dataset) * 100.
            lr = self.optimizer.state_dict()['param_groups'][0]['lr']
            print("Train: epoch:{}|{}; loss:{:.3f}, acc:{:.3f}, batch_time:{:.3f}, lr:{}".format(epoch+1, self.max_epoch, train_loss, train_acc, train_batch_time, lr))
            self.scheduler.step()

            if (epoch+1) % self.eval_epoch == 0:
                self.model.eval()
                start_time = datetime.datetime.now()
                for i, data in enumerate(self.val_loader):
                    img, label = data
                    img, label = img.cuda(), label.cuda()
                    outputs = self.model(img)
                    _, pred = torch.max(outputs, 1)
                    val_corrent += (pred == label).sum()
                end_time = datetime.datetime.now()
                val_batch_time = (end_time - start_time).seconds / len(self.val_loader.dataset) * self.batch_size
                val_acc = val_corrent / len(self.val_loader.dataset) * 100.
                if val_acc >= self.best_acc:
                    print("Save Model")
                    self.best_acc = val_acc
                    state = {
                        "best_acc": val_acc,
                        "epoch": epoch + 1,
                        "model": self.model.state_dict(),
                        "optimizer": self.optimizer.state_dict(),
                    }
                    if not os.path.isdir(self.output_dir):
                        os.mkdir(self.output_dir)
                    torch.save(state, self.output_dir + "/best_ckpt.pth")
                print("Eval:  epoch:{}|{},acc:{:.3f}, batch_time:{:.3f}".format(epoch+1, self.max_epoch, val_acc, val_batch_time))