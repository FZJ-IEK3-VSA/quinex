# Experiments

As we train many different models that sometimes depend on each other, we use a workflow manager (snakemake) to manage the experiments. The experiments are defined in the `experiments_definition.py` file. We use a SLURM cluster and defined the slurm profile in the `slurm/config.yaml` file. 

If your compute nodes are not connected to the internet, you should first run `snakefile_online_rules` to download the necessary files using the headnode.
```bash
snakemake --snakefile experiments/<task>/snakefile_online_rules --cores 1 
```
`<task>` is either `quantity_extraction` or `generative_context_extraction`. 

To run the experiments execute the `snakefile` with snakemake.
```bash	
snakemake --profile experiments/slurm --snakefile experiments/<task>/snakefile --rerun-incomplete
```
You can use --dry-run to see what will executed without actually running the commands. You can use --rerun-triggers mtime to not rerun the rules that have already been executed. 
Per default, the models are trained on the training set and evaluated only on the development set. The `evaluate_on_test_set.sh` script can be used to evaluate the models on the test set or you change the bash command in the `snakefile` to also evaluate the models on the test set directly.

To monitor the training start TensorBoard
```bash
tensorboard --logdir="./path/to/model_checkpoints/defined/in/experiments_definition/"
```

## Debug
Get information about GPU usage

```bash
nvidia-smi
```

If you get an `CUDA out of memory` error, try

- reduce per_device_train_batch_size (e.g., 16 instead of 32)
- reduce max_seq_length (e.g., 128 instead of 384)
- use a smaller model (e.g., roberta-base instead of roberta-large)
- if everything runs fine with Trainer(...compute_metrics=None) check eval_accumulation_steps and preprocess_logits_for_metrics

If you get an `CUDA out of memory` error only when doing hyperparameter optimzation, chances are high that the `hyperparameter_space` includes batch sizes that are too large for your GPU. Try to reduce the batch sizes in the hyperparameter space in the training script.