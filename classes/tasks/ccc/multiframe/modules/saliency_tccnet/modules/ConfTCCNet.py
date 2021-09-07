from abc import ABC
from typing import Tuple

import torch
import torch.nn.functional as F
from torch import Tensor
from torch.nn.functional import normalize

from auxiliary.utils import overloads
from classes.tasks.ccc.multiframe.modules.saliency_tccnet.core.SaliencyTCCNet import SaliencyTCCNet
from classes.tasks.ccc.singleframe.fc4.FC4 import FC4
from functional.image_processing import scale

""" Confidence as spatial attention + Confidence as temporal attention """


class ConfTCCNet(SaliencyTCCNet, ABC):

    def __init__(self, hidden_size: int = 128, kernel_size: int = 5, sal_dim: str = "spatiotemp"):
        super().__init__(hidden_size, kernel_size, sal_dim, rnn_input_size=3)
        self.fcn = FC4()

    @overloads(SaliencyTCCNet._weight_spat)
    def _weight_spat(self, x: Tensor, spat_conf: Tensor, *args, **kwargs) -> Tensor:
        if not self._is_saliency_active("spat"):
            return scale(x).clone()
        spat_conf = self._spat_save_grad_check(self._spat_we_check(spat_conf))
        return self._apply_spat_weights(x, spat_conf)

    @staticmethod
    def __spat_conf_to_temp_conf(spat_conf: Tensor) -> Tensor:
        return F.softmax(torch.mean(torch.mean(spat_conf.squeeze(1), dim=1), dim=1), dim=0).unsqueeze(1)

    @overloads(SaliencyTCCNet._weight_temp)
    def _weight_temp(self, x: Tensor, conf: Tensor, *args, **kwargs) -> Tuple:
        if not self._is_saliency_active("temp"):
            return x, Tensor()
        temp_conf = self._temp_save_grad_check(self._temp_we_check(self.__spat_conf_to_temp_conf(conf)))
        temp_weighted_x = self._apply_temp_weights(x, temp_conf)
        return temp_weighted_x, temp_conf

    def _spat_comp(self, x: Tensor, *args, **kwargs) -> Tuple:
        _, rgb, spat_conf = self.fcn(x)
        spat_weighted_x = self._weight_spat(rgb, spat_conf)
        return spat_weighted_x, spat_conf

    @overloads(SaliencyTCCNet._temp_comp)
    def _temp_comp(self, x: Tensor, batch_size: int, spat_mask: Tensor, *args, **kwargs) -> Tuple:
        time_steps, _, h, w = x.shape
        self.conv_lstm.init_hidden(self._hidden_size, (h, w))
        hidden, cell = self._init_hidden(batch_size, h, w)

        temp_weighted_x, temp_mask = self._weight_temp(x, spat_mask)

        hidden_states = []
        for t in range(time_steps):
            hidden, cell = self.conv_lstm(temp_weighted_x[t, :, :, :].unsqueeze(0), hidden, cell)
            hidden_states.append(hidden)

        out = torch.mean(torch.stack(hidden_states), dim=0)

        return out, temp_mask

    def forward(self, x: Tensor) -> Tuple:
        batch_size, time_steps, num_channels, h, w = x.shape
        x = x.view(batch_size * time_steps, num_channels, h, w)

        spat_weighted_x, spat_mask = self._spat_comp(x)
        out, temp_mask = self._temp_comp(spat_weighted_x, batch_size, spat_mask)

        y = self.fc(out)
        pred = normalize(torch.sum(torch.sum(y, 2), 2), dim=1)

        return pred, spat_mask if self._is_saliency_active("spat") else Tensor(), temp_mask
