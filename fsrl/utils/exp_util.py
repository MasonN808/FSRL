# flake8: noqa

import json
import os
import os.path as osp
import random
import uuid
from typing import Dict, List, Optional, Sequence
import gymnasium as gym
import logging
from moviepy.editor import VideoFileClip # TODO: Fix runtime error (10/31)
logger = logging.getLogger(__name__)

import numpy as np
import torch
import yaml

from fsrl.utils.logger.logger_util import colorize


def seed_all(seed=1029, others: Optional[list] = None) -> None:
    """Fix the seeds of `random`, `numpy`, `torch` and the input `others` object.

    :param int seed: defaults to 1029
    :param Optional[list] others: other objects that want to be seeded, defaults to None
    """
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    # torch.use_deterministic_algorithms(True)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)  # if you are using multi-GPU.
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    if others is not None:
        if hasattr(others, "seed"):
            others.seed(seed)
            return True
        try:
            for item in others:
                if hasattr(item, "seed"):
                    item.seed(seed)
        except:
            pass


def get_cfg_value(config, key):
    if key in config:
        value = config[key]
        if isinstance(value, list):
            suffix = ""
            for i in value:
                suffix += str(i)
            return suffix
        return str(value)
    for k in config.keys():
        if isinstance(config[k], dict):
            res = get_cfg_value(config[k], key)
            if res is not None:
                return res
    return "None"


def load_config_and_model(path: str, best: bool = False, epoch_model_number: int = None):
    """
    Load the configuration and trained model from a specified directory.

    :param path: the directory path where the configuration and trained model are stored.
    :param best: whether to load the best-performing model or the most recent one.
        Defaults to False.

    :return: a tuple containing the configuration dictionary and the trained model.
    :raises ValueError: if the specified directory does not exist.
    """
    if osp.exists(path):
        config_file = osp.join(path, "config.yaml")
        print(f"load config from {config_file}")
        with open(config_file) as f:
            config = yaml.load(f.read(), Loader=yaml.FullLoader)
        model_file = f'model_epoch-{epoch_model_number}.pt' if epoch_model_number is not None else "model.pt"
        if best:
            model_file = "model_best.pt"
        model_path = osp.join(path, "checkpoint/" + model_file)
        print(f"load model from {model_path}")
        # model = torch.load(model_path)
        model = torch.load(model_path, map_location=torch.device('cpu'))
        return config, model
    else:
        raise ValueError(f"{path} doesn't exist!")


# naming utils


def to_string(values):
    """
    Recursively convert a sequence or dictionary of values to a string representation.

    :param values: the sequence or dictionary of values to be converted to a string.
    :return: a string representation of the input values.
    """
    name = ""
    if isinstance(values, Sequence) and not isinstance(values, str):
        for i, v in enumerate(values):
            prefix = "" if i == 0 else "_"
            name += prefix + to_string(v)
        return name
    elif isinstance(values, Dict):
        for i, k in enumerate(sorted(values.keys())):
            prefix = "" if i == 0 else "_"
            name += prefix + to_string(values[k])
        return name
    else:
        return str(values)


DEFAULT_SKIP_KEY = [
    "task", "reward_threshold", "logdir", "worker", "project", "group", "name", "prefix",
    "suffix", "save_interval", "render", "verbose", "save_ckpt", "training_num",
    "testing_num", "epoch", "device", "thread"
]

DEFAULT_KEY_ABBRE = {
    "cost_limit": "cost",
    "mstep_iter_num": "mnum",
    "estep_iter_num": "enum",
    "estep_kl": "ekl",
    "mstep_kl_mu": "kl_mu",
    "mstep_kl_std": "kl_std",
    "mstep_dual_lr": "mlr",
    "estep_dual_lr": "elr",
    "update_per_step": "update"
}


def auto_name(
    default_cfg: dict,
    current_cfg: dict,
    prefix: str = "",
    suffix: str = "",
    skip_keys: list = DEFAULT_SKIP_KEY,
    key_abbre: dict = DEFAULT_KEY_ABBRE
) -> str:
    """Automatic generate the name by comparing the current config with the default one.

    :param dict default_cfg: a dictionary containing the default configuration values.
    :param dict current_cfg: a dictionary containing the current configuration values.
    :param str prefix: (optional) a string to be added at the beginning of the generated
        name.
    :param str suffix: (optional) a string to be added at the end of the generated name.
    :param list skip_keys: (optional) a list of keys to be skipped when generating the
        name.
    :param dict key_abbre: (optional) a dictionary containing abbreviations for keys in
        the generated name.

    :return str: a string representing the generated experiment name.
    """
    name = prefix
    for i, k in enumerate(sorted(default_cfg.keys())):
        if default_cfg[k] == current_cfg[k] or k in skip_keys:
            continue
        prefix = "_" if len(name) else ""
        value = to_string(current_cfg[k])
        # replace the name with abbreviation if key has abbreviation in key_abbre
        if k in key_abbre:
            k = key_abbre[k]
        # Add the key-value pair to the name variable with the prefix
        name += prefix + k + value
    if len(suffix):
        name = name + "_" + suffix if len(name) else suffix

    name = "default" if not len(name) else name
    name = f"{name}-{str(uuid.uuid4())[:4]}"
    return name

def dict_dims(mydict):
    d1 = len(mydict)
    d2 = 0
    for d in mydict:
        d2 = max(d2, len(d))
    return d1, d2


# From https://github.com/eleurent/rl-agents/blob/master/rl_agents/agents/common/factory.py
def load_environment(env_config, render_mode=None):
    """
        Load an environment from a configuration file.

    :param env_config: the configuration, or path to the environment configuration file
    :return: the environment
    """
    # Load the environment config from file
    if not isinstance(env_config, dict):
        with open(env_config) as f:
            env_config = json.loads(f.read())

    # Make the environment
    if env_config.get("import_module", None):
        __import__(env_config["import_module"])
    try:
        env = gym.make(env_config['id'], render_mode=render_mode)
        # Save env module in order to be able to import it again
        env.import_module = env_config.get("import_module", None)
    except KeyError:
        raise ValueError("The gym register-id of the environment must be provided")
    except gym.error.UnregisteredEnv:
        # The environment is unregistered.
        print("import_module", env_config["import_module"])
        raise gym.error.UnregisteredEnv('Environment {} not registered. The environment module should be specified by '
                                        'the "import_module" key of the environment configuration'.format(
                                            env_config['id']))

    # Configure the environment, if supported
    try:
        env.unwrapped.configure(env_config)
        # Reset the environment to ensure configuration is applied
        env.reset()
    except AttributeError as e:
        logger.info("This environment does not support configuration. {}".format(e))
    return env

def mp4_to_gif(mp4_path: str, gif_path: str):
    videoClip = VideoFileClip(mp4_path)
    videoClip.write_gif(gif_path, fps=60, opt="OptimizePlus", fuzz=10)

