'''
  copy from https://github.com/openai/gym/blob/master/examples/agents/cem.py
'''
import gym
from gym import wrappers, logger
import numpy as np
import pickle
import json, sys, os
from os import path
import argparse
import math

class BinaryActionLinearPolicy(object):
    def __init__(self, theta):
        self.w = theta[:-1]
        self.b = theta[-1]
    def act(self, ob):
        y = ob.dot(self.w) + self.b
        a = int(y < 0)
        return a

def cem(f, th_mean, batch_size, n_iter, elite_frac, initial_std=1.0):
    """
    Generic implementation of the cross-entropy method for maximizing a black-box function

    Args:
        f: a function mapping from vector -> scalar
        th_mean (np.array): initial mean over input distribution
        batch_size (int): number of samples of theta to evaluate per batch
        n_iter (int): number of batches
        elite_frac (float): each batch, select this fraction of the top-performing samples
        initial_std (float): initial standard deviation over parameter vectors

    returns:
        A generator of dicts. Subsequent dicts correspond to iterations of CEM algorithm.
        The dicts contain the following values:
        'ys' :  numpy array with values of function evaluated at current population
        'ys_mean': mean value of function over current population
        'theta_mean': mean value of the parameter vector over current population
    """
    n_elite = int(np.round(batch_size*elite_frac))
    #print ("n_elite = %s" % n_elite)    # 5
    th_std = np.ones_like(th_mean) * initial_std

    for _ in range(n_iter):
        # batch apply virtual policies around previous policies
        ths = np.array([th_mean + dth for dth in  th_std[None,:]*np.random.randn(batch_size, th_mean.size)])
        # get the rewards for those actions
        ys = np.array([f(th) for th in ths])
        # choose the best 20% actions
        elite_inds = ys.argsort()[::-1][:n_elite]
        elite_ths = ths[elite_inds]
        th_mean = elite_ths.mean(axis=0)
        th_std = elite_ths.std(axis=0)
        yield {'ys' : ys, 'theta_mean' : th_mean, 'y_mean' : ys.mean()}

def do_rollout(agent, env, num_steps, render=False):
    total_rew = 0
    ob = env.reset()

    # give a initial slope
    env.env.env.state[2] += 30 * 2 * math.pi / 360

    for t in range(num_steps):
        #temp = input()
        a = agent.act(ob)
        (ob, reward, done, _info) = env.step(a)
        #ob[2] += np.random.randint(10)

        # not use reward, but add x dimension
        total_rew += reward
        #total_rew += reward * (env.env.x_threshold - abs(ob[0]))
        if render: env.render()
        if done: break
    return total_rew, t+1

if __name__ == '__main__':
    logger.set_level(logger.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument('--display', action='store_true')
    parser.add_argument('target', nargs="?", default="CartPole-v0")
    args = parser.parse_args()

    env = gym.make(args.target)
    num_steps = 2000
    env._max_episode_steps = num_steps
    env.env.theta_threshold_radians = 90 * 2 * math.pi / 360
    env.seed(0)
    np.random.seed(0)
    params = dict(n_iter=10000, batch_size=250, elite_frac=0.02)

    # You provide the directory to write to (can be an existing
    # directory, but can't contain previous monitor results. You can
    # also dump to a tempdir if you'd like: tempfile.mkdtemp().
    outdir = '/tmp/cem-agent-results'
    env = wrappers.Monitor(env, outdir, force=True)

    # Prepare snapshotting
    # ----------------------------------------
    def writefile(fname, s):
        with open(path.join(outdir, fname), 'w') as fh: fh.write(s)
    info = {}
    info['params'] = params
    info['argv'] = sys.argv
    info['env_id'] = env.spec.id
    # ------------------------------------------

    def noisy_evaluation(theta):
        agent = BinaryActionLinearPolicy(theta)
        rew, T = do_rollout(agent, env, num_steps)
        return rew

    # Train the agent, and snapshot each stage
    for (i, iterdata) in enumerate(
        # noisy_evaluation is the trainer
        cem(noisy_evaluation, np.zeros(env.observation_space.shape[0]+1), **params)):
        print('Iteration %2i. Episode mean reward: %7.3f'%(i, iterdata['y_mean']))
        #print ("iterdata= %s" % iterdata)   
        '''{'ys': array([  9.,  15.,  23.,  15.,  11.,   9.,  62.,  26.,   9.,  59., 117.,
        30., 119.,  10.,  19.,  10.,  13.,  22.,  10.,   9.,   8.,   9.,
         9.,   9.,   9.]), 'theta_mean': array([-0.2845444 , -0.15615326, -0.22635498, -1.42718624, -0.15482994]), 'y_mean': 25.64}'''
        agent = BinaryActionLinearPolicy(iterdata['theta_mean'])
        if args.display: do_rollout(agent, env, num_steps, render=True)
        writefile('agent-%.4i.pkl'%i, str(pickle.dumps(agent, -1)))

    # Write out the env at the end so we store the parameters of this
    # environment.
    writefile('info.json', json.dumps(info))

    env.close()
