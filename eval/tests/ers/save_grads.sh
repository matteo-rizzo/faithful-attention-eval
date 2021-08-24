#!/bin/bash

# This script saves to file the gradients w.r.t. to spatial, temporal or spatiotemporal saliency

pwd
source venv/bin/activate
export PYTHONPATH=$PYTHONPATH:/home/matteo/Projects/faithful-attention-eval/

declare path_to_script="tests/erasure/save_grads_tccnet.py"

# Values: "att_tccnet" "conf_tccnet" "conf_att_tccnet"
declare -a model_types=("conf_tccnet")

# Values: "tcc_split" "fold_0" "fold_1" "fold_2"
declare -a dirs=("tcc_split" "fold_0" "fold_1" "fold_2")

# Values: "spatiotemp" "spat" "temp"
declare -a modes=("spat" "temp")

for model_type in "${model_types[@]}"; do
  for dir in "${dirs[@]}"; do
    for mode in "${modes[@]}"; do
      python3 "$path_to_script" --model_type "$model_type" --data_folder "$dir" --sal_type "$mode" --infer_path || exit
      python3 "$path_to_script" --model_type "$model_type" --data_folder "$dir" --sal_type "$mode" --infer_path --use_train_set || exit
    done
  done
done
