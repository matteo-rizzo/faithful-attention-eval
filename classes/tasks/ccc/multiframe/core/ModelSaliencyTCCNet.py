from typing import Union, Tuple

from torch import Tensor

from classes.tasks.ccc.core.ModelCCC import ModelCCC


class ModelSaliencyTCCNet(ModelCCC):

    def __init__(self):
        super().__init__()

    def predict(self, x: Tensor, m: Tensor = None, return_steps: bool = False) -> Union[Tuple, Tensor]:
        pred, spat_mask, temp_mask = self._network(x)
        if return_steps:
            return pred, spat_mask, temp_mask
        return pred

    def optimize(self, x: Tensor, y: Tensor, m: Tensor = None) -> float:
        self._optimizer.zero_grad()
        pred = self.predict(x, m)
        loss = self.get_loss(pred, y)
        loss.backward()
        self._optimizer.step()
        return loss.item()
