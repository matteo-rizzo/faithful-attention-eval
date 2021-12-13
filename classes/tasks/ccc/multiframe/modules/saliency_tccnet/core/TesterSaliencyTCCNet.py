import os
from typing import Tuple, List

import numpy as np
from torch.utils.data import DataLoader

from classes.core.Model import Model
from classes.tasks.ccc.multiframe.core.TesterTCCNet import TesterTCCNet
from functional.error_handling import check_sal_dim_support


class TesterSaliencyTCCNet(TesterTCCNet):

    def __init__(self, sal_dim: str, path_to_log: str, log_frequency: int,
                 save_pred: bool = False, save_sal: bool = False, vis: List = None):
        super().__init__(path_to_log, log_frequency, save_pred)
        check_sal_dim_support(sal_dim)
        self._sal_dim, self._save_sal, self.__vis = sal_dim, save_sal, vis
        if save_sal:
            path_to_sal = os.path.join(path_to_log, "sal")
            print("\n Saving saliency weights at {}".format(path_to_sal))

            if self._sal_dim in ["spat", "spatiotemp"]:
                self._path_to_spat_sal = os.path.join(path_to_sal, "spat")
                os.makedirs(self._path_to_spat_sal)

            if self._sal_dim in ["temp", "spatiotemp"]:
                self._path_to_temp_sal = os.path.join(path_to_sal, "temp")
                os.makedirs(self._path_to_temp_sal)

    def _eval(self, model: Model, data: DataLoader, *args, **kwargs):
        for i, (x, _, y, path_to_x) in enumerate(data):
            file_name = path_to_x[0].split(os.sep)[-1]
            x, y = x.to(self._device), y.to(self._device)

            pred, spat_sal, temp_sal = model.predict(x, return_steps=True)
            tl = model.get_loss(pred, y).item()
            self._test_loss.update(tl)
            self._metrics_tracker.add_error(tl)

            if i % self._log_frequency == 0:
                print("[ Batch: {} - File: {} ] | Loss: {:.4f} ]".format(i, file_name, tl))

            if self._save_pred:
                self._save_pred2npy(pred, file_name)

            if self._save_sal:
                self._save_sal2npy((spat_sal, temp_sal), file_name)

    def _save_sal2npy(self, sal: Tuple, file_name: str):
        if self._sal_dim in ["spat", "spatiotemp"]:
            np.save(os.path.join(self._path_to_spat_sal, file_name), sal[0].cpu().numpy())
        if self._sal_dim in ["temp", "spatiotemp"]:
            np.save(os.path.join(self._path_to_temp_sal, file_name), sal[1].cpu().numpy())
