import os
from typing import Dict, Tuple

import numpy as np
import torch
from torch import Tensor
from torch.utils.data import DataLoader

from classes.eval.adv.core.AdvModel import AdvModel
from classes.tasks.ccc.core.EvaluatorCCC import EvaluatorCCC
from classes.tasks.ccc.core.TrainerCCC import TrainerCCC


class TrainerAdvSaliencyTCCNet(TrainerCCC):
    def __init__(self, sal_type: str, path_to_log: str, path_to_pred: str, path_to_att: str, val_frequency: int = 5):
        super().__init__(path_to_log, val_frequency)

        self.__sal_type = sal_type
        self.__path_to_pred = path_to_pred
        self.__path_to_spat_att = os.path.join(path_to_att, "spat")
        self.__path_to_temp_att = os.path.join(path_to_att, "temp")

        self.__path_to_vis = os.path.join(path_to_log, "vis")
        os.makedirs(self.__path_to_vis)

        self._evaluator_base = EvaluatorCCC()

    def __load_from_file(self, path_to_item: str) -> Tensor:
        item = np.load(os.path.join(path_to_item), allow_pickle=True)
        return torch.from_numpy(item).squeeze(0).to(self._device)

    def __load_ground_truths(self, file_name: str) -> Tuple:
        pred_base = self.__load_from_file(os.path.join(self.__path_to_pred, file_name)).unsqueeze(0)
        spat_att_base, temp_att_base = Tensor(), Tensor()
        if self.__sal_type in ["spat", "spatiotemp"]:
            spat_att_base = self.__load_from_file(os.path.join(self.__path_to_spat_att, file_name))
        if self.__sal_type in ["temp", "spatiotemp"]:
            temp_att_base = self.__load_from_file(os.path.join(self.__path_to_temp_att, file_name))
        return pred_base, spat_att_base, temp_att_base

    def __compute_pred(self, x: Tensor, path_to_x: str, model: AdvModel) -> Tuple:
        file_name = path_to_x[0].split(os.sep)[-1]
        pred_base, spat_att_base, temp_att_base = self.__load_ground_truths(file_name)

        pred_adv, spat_att_adv, temp_att_adv = model.predict(x)
        att_base, att_adv = (spat_att_base, temp_att_base), (spat_att_adv, temp_att_adv)

        return pred_base, pred_adv, att_base, att_adv

    def _train_epoch(self, model: AdvModel, data: DataLoader, epoch: int, *args, **kwargs):
        for i, (x, _, y, path_to_x) in enumerate(data):
            x, y = x.to(self._device), y.to(self._device)
            pred_base, pred_adv, att_base, att_adv = self.__compute_pred(x, path_to_x, model)
            tl, losses = model.optimize(pred_base, pred_adv, att_base, att_adv)
            self._train_loss.update(tl)

            err_base = model.get_loss(pred_base, y).item()
            err_adv = model.get_loss(pred_adv, y).item()

            if i % 5 == 0:
                loss_log = " - ".join(["{}: {:.4f}".format(lt, lv.item()) for lt, lv in losses.items()])
                print("[ Epoch: {} - Batch: {} ] | Loss: [ train: {:.4f} - {} ] | AE: [ base: {:.4f} - adv: {:.4f} ]"
                      .format(epoch + 1, i, tl, loss_log, err_base, err_adv))

            if i == 0 and epoch % 50 == 0:
                path_to_save = os.path.join(self.__path_to_vis, "epoch_{}".format(epoch))
                print("\n Saving vis at: {} \n".format(path_to_save))
                model.save_vis(x, att_base, att_adv, path_to_save)

    def _eval_epoch(self, model: AdvModel, data: DataLoader, *args, **kwargs):
        for i, (x, _, y, path_to_x) in enumerate(data):
            x, y = x.to(self._device), y.to(self._device)
            pred_base, pred_adv, att_base, att_adv = self.__compute_pred(x, path_to_x, model)
            vl, losses = model.get_adv_loss(pred_base, pred_adv, att_base, att_adv)
            vl = vl.item()
            self._val_loss.update(vl)

            err_adv = model.get_loss(pred_adv, y).item()
            err_base = model.get_loss(pred_base, y).item()

            self._evaluator.add_error(err_adv)
            self._evaluator_base.add_error(err_base)

            if i % 5 == 0:
                loss_log = " - ".join(["{}: {:.4f}".format(lt, lv.item()) for lt, lv in losses.items()])
                print("[ Batch: {} ] | Loss: [ val: {:.4f} - {} ] | Ang Err: [ base: {:.4f} - adv: {:.4f} ]"
                      .format(i, vl, loss_log, err_base, err_adv))

    def _reset_evaluator(self):
        self._evaluator.reset_errors()
        self._evaluator_base.reset_errors()

    def _check_metrics(self):
        metrics_adv, metrics_base = self._evaluator.compute_metrics(), self._evaluator_base.compute_metrics()
        self._print_metrics(metrics_base=metrics_base, metrics_adv=metrics_adv)
        self._log_metrics(metrics_adv)

    def _print_metrics(self, metrics_base: Dict, *args, **kwargs):
        for mn, mv in kwargs["metrics_adv"].items():
            print((" {} " + "".join(["."] * (15 - len(mn))) + " : {:.4f} (Best: {:.4f} - Base: {:.4f})")
                  .format(mn.capitalize(), mv, self._best_metrics[mn], metrics_base[mn]))
