#!/usr/bin/python
# -*- coding: utf8 -*-

from data_util import env
#import gym
import numpy as np
import time
import os
import codecs
import math
import copy
#from env_trj import *
from env_trj.data_load import *
from env_trj.task_generator import *
from env_trj.state_generator import *

class env_trajectory(env):
    def __init__(self, name, config):
        env.__init__(self, name)
        #self.env = gym.make(name)
        self.inner_step = 0
        self.config = config
        # load data
        self.data_loader = DataLoader(
            self.config.task_data_path,self.config.trajectory_data_path)
        self.data_loader.load_task_static() # 读取yellow 数据
        self.data_loader.get_trajectories() # 读取uber数据
        self.data_loader.overall_position_normalization()
        self.data_loader.get_merge_task(self.config.aim_day_num) 
        print "task generation"
        self.task_generator = TaskGenerator()
        self.task_generator.gen_task_list(self.data_loader.zip_data) # 按分布采样生成task列表
        self.task_generator.set_poisson_distribution(self.config.poisson_lamda, self.config.poisson_episode_num)
        print "trajectory sampling size: %d" % len(self.data_loader.trajectory_data)
        # new simulator
        self.simulator = StateSimulator()
        # reset
        self.simulator.trajector.init_sampling( \
            self.data_loader.trajectory_data, self.config.trajector_sampling_size)  # 采样生成路线数据
        self.episode_task_num = self.config.episode_task_num
        self.speed_init()
        #self.task_sampling()
        #self.preprocess()
        # clear memeory
        # self.self.data_loader.reset() 
        # clear log
        self.log_file = codecs.open(self.config.log_file_path, "w", "utf8")
        self.log_file.close()

    def reset(self, is_test=False): # 重新采样
        self.inner_step = 0
        self.simulator.trajector.init_sampling( \
            self.data_loader.trajectory_data, self.config.trajector_sampling_size)  # 采样生成路线数据
        self.task_sampling()
        self.speed_tune()
        self.preprocess()
        self.simulator.output_state(self.config.log_file_path, self.inner_step)
        print "reset done"
        if is_test:
            return self.simulator
        else:
            return self.simulator.new_feature

    def preprocess(self):
        self.simulator.clear()
        self.simulator.init_participants(self.config.participant_num) # 初始化n个taxi
        #print "step:0, task_num:%s" % len(task_samples)
        self.simulator.update_state(self.task_samples, [])
        self.simulator.new_feature = self.pre_process_feature()

    def speed_init(self):
        if self.config.env_var:
            self.simulator.trajector.speed_tuner_init( \
                self.config.normal_mu, self.config.normal_sigma, self.config.normal_episode_num)
        self.speed_tune()

    def speed_tune(self):
        if self.config.env_var:
            self.simulator.trajector.speed_tuner(self.config.default_ave_speed, self.inner_step)
        else:
            self.simulator.trajector.set_ave_speed(self.config.default_ave_speed)
        #self.simulator.trajector.set_ave_speed(self.config.default_ave_speed)
        #print "ave speed: %s" % self.simulator.trajector.ave_speed

    def task_sampling(self):
        if self.config.env_var:
            self.task_generator.set_poisson_distribution(self.config.poisson_lamda, self.config.poisson_episode_num)
            self.task_samples = self.task_generator.task_sampling_poisson( \
                    self.inner_step, self.episode_task_num, self.config.max_task_size)
        else:
            # possion
            # self.task_generator.set_poisson_distribution(self.config.poisson_lamda, self.config.poisson_episode_num)
            # self.task_samples = self.task_generator.task_sampling_poisson( \
            #         self.inner_step, self.episode_task_num, self.config.max_task_size)

            #fix
            self.task_samples = self.task_generator.task_sampling_fix(self.inner_step, self.episode_task_num)
            
            #self.task_samples = self.task_generator.task_sampling_default_rand(self.episode_task_num)
            #self.task_samples = self.task_generator.task_sampling_random(self.episode_task_num)
        #self.task_samples = self.task_generator.task_sampling_default(self.episode_task_num)
        print "task sampling... new task num: %d" % len(self.task_samples)

    def render(self):
        return self.env.render()

    def step_raw(self, actions):
        self.inner_step += 1
        #actions = [action]
        self.speed_tune()
        self.task_sampling()
        self.simulator.update_state(self.task_samples, actions)
        #self.simulator.output_state(self.config.log_file_path, self.inner_step)
        done = False
        if self.inner_step == self.config.max_step:
            done = True
            reward = self.simulator.reward
        else:
            reward = self.simulator.reward
        info = None
        return self.simulator, reward, done, info

    def step(self, actions_pid_list, is_test=False):
        # init
        self.inner_step += 1
        print "INNER SETP:%s, last_reward:%s" % (self.inner_step, self.simulator.final_reward)
        reward = 0
        done = False
        print "ACTION:",
        print actions_pid_list
        self.speed_tune()
        self.task_sampling()
        actions = self.pre_process_action(actions_pid_list)
        #print actions
        self.simulator.update_state(self.task_samples, actions)
        
        ### rewarding
        #print self.simulator.reward
        dup_simulator = copy.deepcopy(self.simulator)
        is_finished = dup_simulator.update_state([], [])
        while_counter = 0
        while (not is_finished):
            while_counter += 1
            if while_counter > 1000:
                print "rewarding while overflow"
                break
            is_finished = dup_simulator.update_state([], [])

        # get feature
        self.simulator.new_feature = self.pre_process_feature()
        
        # dup reward
        self.simulator.final_reward = dup_simulator.reward

        # return result
        info = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        if self.inner_step == self.config.max_step:
            done = True
            reward = self.simulator.final_reward
        else:
            reward = 0

        # DONE
        std_fare_amount = 0.0
        if done:
            # self.simulator.pending_time = dup_simulator.pending_time
            # self.simulator.total_fare_amount = dup_simulator.total_fare_amount
            self.simulator.task_pending_time = copy.deepcopy(dup_simulator.task_pending_time)
            self.simulator.participant_fare = copy.deepcopy(dup_simulator.participant_fare)
            self.simulator.participant_finish_task = copy.deepcopy(dup_simulator.participant_finish_task)
            self.simulator.participant_dis_cost = copy.deepcopy(dup_simulator.participant_dis_cost)
            self.simulator.finished_task_num = dup_simulator.finished_task_num
            # if self.simulator.finished_task_num > 0:
            #     ave_pending_time = self.simulator.pending_time/self.simulator.finished_task_num
            # else:
            #     ave_pending_time = 0.0
            # ave_fare_amount = self.simulator.total_fare_amount/len(self.simulator.participants)
            # info = [ave_pending_time, ave_fare_amount]

            # print "EPISODE_REWARD:%s\tPENDING_TIME:%s\tFARE_AMOUNT:%s\tTOTAL_PENDING_TIME:%s\tFINISHED_TASK:%s\tTOTAL_FARE:%s\tPAR_NUM:%s" \
            #     % (reward, ave_pending_time, ave_fare_amount,\
            #         self.simulator.pending_time, self.simulator.finished_task_num, \
            #         self.simulator.total_fare_amount, len(self.simulator.participants))
            task_time_wait = []
            par_fare_amount = []
            par_finish = []
            par_dis_cost = []
            for tid in self.simulator.task_pending_time:
                print "TASK_time_wait %s,%s" % (tid, self.simulator.task_pending_time[tid])
                task_time_wait.append(self.simulator.task_pending_time[tid])
            for pid in self.simulator.participant_fare:
                print "PAR_fare %s,%s" % (pid, self.simulator.participant_fare[pid])
                par_fare_amount.append(self.simulator.participant_fare[pid])
            for pid in self.simulator.participant_finish_task:
                print "PAR_finish %s,%s" % (pid, self.simulator.participant_finish_task[pid])
                par_finish.append(self.simulator.participant_finish_task[pid])
            for pid in self.simulator.participant_dis_cost:
                print "PAR_dis_cost %s,%s" % (pid, self.simulator.participant_dis_cost[pid])
                par_dis_cost.append(self.simulator.participant_dis_cost[pid])
            
            mean_time_wait = np.mean(task_time_wait)
            std_time_wait = np.std(task_time_wait)
            mean_fare_amount = np.mean(par_fare_amount)
            std_fare_amount = np.var(par_fare_amount)
            mean_dis_cost = np.mean(par_dis_cost) 
            std_dis_cost = np.std(par_dis_cost)
            mean_finish = np.mean(par_finish)
            std_finish = np.std(par_finish)

            # fairness_n = 0.0
            # for p_fare in par_fare_amount:
            #     if p_fare < 0.02:
            #         fairness_n -= 1.0

            print "EPISODE_REWARD:%s\tFINISHED_NUM:%s\tTIME_MEAN:%s\tTIME_STD:%s\tFARE_MEAN:%s\tFARE_STD:%s\tDIS_MEAN:%s\tDIS_STD:%s\tFINISH_MEAN:%s\tFINISH_STD:%s" \
                % (reward, self.simulator.finished_task_num, mean_time_wait, \
                    std_time_wait, mean_fare_amount, std_fare_amount, mean_dis_cost, std_dis_cost, mean_finish, std_finish)

            print par_fare_amount
            print std_fare_amount
            reward_fare_std = (0.1 - std_fare_amount) * len(par_fare_amount) * self.config.max_step # fare std
            #reward_fare_std = pow(reward_fare_std, 0.5)
            reward_time_std = (0.05 - std_time_wait) * len(task_time_wait) # time waiting std
            reward = reward * 1.0
            info = [reward, reward_fare_std, reward_time_std, \
                    mean_time_wait, std_time_wait, mean_fare_amount, std_fare_amount, self.simulator.finished_task_num, \
                    mean_dis_cost, std_dis_cost, mean_finish, std_finish]
            print "#REWARD: R:%s, F_STD:%s, T_STD:%s" % (reward, reward_fare_std, reward_time_std)
            reward = reward + reward_fare_std + reward_time_std

        # output detail log
        self.simulator.output_state(self.config.log_file_path, self.inner_step)
        
        #reward = 1 - std_fare_amount
        del dup_simulator
        if is_test:
            return self.simulator, reward, done, info
        else:
            return self.simulator.new_feature, reward, done, info

    def pre_process_action(self, actions_pid_list):
        #[pid1,pid2,pid3,0,0,0,0,0,0,0]
        actions = []
        for index in range(len(self.simulator.new_task_list)):
            action_pid = actions_pid_list[index]
            if action_pid <= 0:
                continue
            action_taskid = self.simulator.new_task_list[index][0]
            action = ["pick", action_pid, action_taskid]
            actions.append(action)
        return actions

    def get_distance(self, x1, y1, x2, y2):
        # print x1
        # print y1
        # print x2
        # print y2
        # print pow((pow((x1 - x2), 2) + pow((y1 - y2), 2)), 0.5)
        return pow((pow((x1 - x2), 2) + pow((y1 - y2), 2)), 0.5)

    def pre_process_feature(self):
        tmp_par_feature = np.zeros((self.config.max_par_size, self.config.par_feature_size))
        tmp_task_feature = np.zeros((self.config.max_task_size, self.config.task_feature_size))
        par_feature = np.zeros((self.config.max_par_size, 15))
        task_feature = np.zeros((self.config.max_task_size, 15))

        assert len(self.simulator.participants) <= self.config.max_par_size
        assert len(self.simulator.new_task_list) <= self.config.max_task_size

        for index in range(len(self.simulator.participants)):
            feature_list = []
            item_id = 0
            for item in self.simulator.participants[index+1]: # pid==index
                if item_id == 0:
                    item_id += 1
                    continue
                if isinstance(item, list):
                    for it in item:
                        feature_list.append(it)
                else:
                    feature_list.append(item)
            for i in range(len(feature_list)):
                feat = feature_list[i]
                if isinstance(feat, Enum):
                    feat = int(feat)
                par_feature[index][i] = feat
                item_id += 1
            # print index
            # print len(par_feature[index])
            # print par_feature[index]
        

        for index in range(len(self.simulator.new_task_list)):
            feature_list = []
            item_id = 0
            for item in self.simulator.new_task_list[index]: # pid==index
                if item_id == 0:
                    item_id += 1
                    continue
                if isinstance(item, list):
                    for it in item:
                        feature_list.append(it)
                else:
                    feature_list.append(item)
            for i in range(len(feature_list)):
                feat = feature_list[i]
                if isinstance(feat, Enum):
                    feat = int(feat)
                task_feature[index][i] = feat
                item_id += 1
            # print index
            # print len(task_feature[index])
            # print task_feature[index]

        # print par_feature
        # print task_feature

        # distance matrix
        dis_feature = np.zeros((self.config.max_task_size, self.config.max_par_size))
        dis_position_par = []
        dis_position_t = []
        for i in range(len(par_feature)):
            p_pos_x = float(par_feature[i][4])
            p_pos_y = float(par_feature[i][5])
            dis_position_par.append([p_pos_x, p_pos_y])
        for i in range(len(task_feature)):
            t_pos_x = float(task_feature[i][4])
            t_pos_y = float(task_feature[i][5])
            dis_position_t.append([t_pos_x, t_pos_y])
        # print dis_position_par
        # print dis_position_t
        for t in range(len(dis_position_t)):
            for p in range(len(dis_position_par)):
                task_state = task_feature[t][1]
                par_state = par_feature[p][1]
                if task_state <= 0 and par_state == 0:
                    dis_feature[t][p] = self.get_distance(dis_position_t[t][0], dis_position_t[t][1], \
                        dis_position_par[p][0], dis_position_par[p][1])
        # print dis_feature

        #fare matrix
        fare_feature = np.zeros((self.config.max_task_size, self.config.max_par_size))
        for i in range(len(task_feature)):
            task_state = task_feature[i][1]
            if task_state <= 0:
                distance = self.get_distance(float(task_feature[i][4]), float(task_feature[i][5]), \
                        float(task_feature[i][6]), float(task_feature[i][7]))
            else:
                distance = 0.0
            for j in range(len(par_feature)):
                par_state = par_feature[j][1]
                if par_state == 0:
                    fare_feature[i][j] = distance
            # print "@@"
            #     print task_state
            #     print par_state
        #print task_feature
        # print fare_feature

        if self.config.task_mask == 1:
            tmp_par_feature = par_feature[:,2:4]
            tmp_task_feature = task_feature[:,2:4]
            feature = [tmp_par_feature, tmp_task_feature]
        else:
            feature = [par_feature, task_feature]
        return feature

