from stable_baselines3_copy import DQN, PPO
from stable_baselines3_copy.common.monitor import Monitor
from stable_baselines3_copy.common.vec_env.vec_safe import VecSafe
from stable_baselines3_copy.common.vec_env import DummyVecEnv
import math
import json
import numpy as np
import os
import gym
import torch
from torch import nn as nn
from torch.nn.functional import relu
import argparse
from offline_reversibility import learn_rev_classifier, learn_rev_action

# Training settings
parser = argparse.ArgumentParser()

# Training parameter
parser.add_argument('--no_cuda', action='store_true', default=False,
                    help='Disables CUDA training.')
parser.add_argument('--seed', type=int, default=42, help='Random seed.')
parser.add_argument('--time_steps', type=int, default=10 ** 6,
                    help='Number of epochs to train.')
parser.add_argument('--max_steps', type=int, default=200,
                    help='Max number of env steps.')
parser.add_argument('--lr', type=float, default=0.01,
                    help='Initial learning rate.')
parser.add_argument('--debug', action='store_true',
                    default=False, help="Enable the detialed training output.")
parser.add_argument('--verbose', type=float, default=0, help="Print training metrics for phi and psi")
parser.add_argument("--log_directory", default="cartpoleRAC",
                    help="The log directory")
parser.add_argument("--model_act", default="None",
                    help="Reversibility model path")
parser.add_argument('--save_models', action='store_true', default=False,
                    help='saving the models at the end of the training.')
parser.add_argument('--threshold', type=float, default=0.7)
parser.add_argument('--lr_classifier', type=float, default=0.01,
                    help='Initial learning rate.')
parser.add_argument('--n_traj_classifier', type=int, default=5000,
                    help="number of train steps of the action model")
parser.add_argument('--dataset_classifier', type=int, default=10 ** 4,
                    help="number of pairs in the classifier dataset")
parser.add_argument('--epoch_classifier', type=int, default=100,
                    help="number of train steps of the action model")
parser.add_argument('--steps_action_model', type=int, default=10 ** 5,
                    help="number of train steps of the classifier model")

parser.add_argument('--gamma', type=float, default=0.99,
                    help='Initial learning rate.')

args = parser.parse_args()

if args.debug:
    print(args)

seed = args.seed
np.random.seed(seed)
torch.manual_seed(seed)

use_gpu = torch.cuda.is_available() and not args.no_cuda

p_thresh = args.threshold

log_dir = args.log_directory
os.makedirs(log_dir, exist_ok=True)

if args.model_act == "None":
    print("Training psi")
    model, buffer = learn_rev_classifier(n_traj=args.n_traj_classifier,
                                         dataset_size=args.dataset_classifier,
                                         epochs=args.epoch_classifier,
                                         lr=args.lr_classifier,
                                         no_cuda=args.no_cuda,
                                         verbose=args.verbose)
    print("Done!")
    print("Training phi")
    model_act = learn_rev_action(model=model,
                                 buffer=buffer,
                                 epochs=args.steps_action_model,
                                 lr=args.lr_classifier,
                                 no_cuda=args.no_cuda,
                                 verbose=args.verbose)
    print("Done!")

    torch.save(model_act, os.path.join(log_dir, 'model_act.pt'))
    torch.save(model, os.path.join(log_dir, 'model_rev.pt'))

else:
    model_act = CartpoleARev()
    dic = torch.load(args.model_act)
    model_act.load_state_dict(dic)

model_act.cuda()
model_act.device = "cuda"

env = gym.make('CartPole-v0')
env.seed(seed)
env._max_episode_steps = args.max_steps

env = Monitor(env, os.path.join(log_dir, 'exp_{}'.format(seed)))
env = DummyVecEnv([lambda: env])

if p_thresh < 1:
    threshold = math.log(p_thresh / (1 - p_thresh))
    env = VecSafe(env, model_act, threshold=threshold)

model = PPO('MlpPolicy', env, verbose=1,
            tensorboard_log=log_dir,
            gamma=args.gamma)

model.learn(total_timesteps=args.time_steps)

if args.save_models:
    model.save(os.path.join(log_dir, 'model.pt'))
